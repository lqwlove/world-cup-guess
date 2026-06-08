"""Sync match facts from football-data.org (v4 API)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import Match, MatchFact

settings = get_settings()

SOURCE = "football-data.org"
SEEDS_DIR = Path(__file__).resolve().parents[4] / "seeds"
TEAM_MAP_PATH = SEEDS_DIR / "football_data_team_map.json"

# Extra aliases returned by the API (normalized key -> canonical API name)
_NAME_ALIASES: dict[str, str] = {
    "korea republic": "Korea Republic",
    "south korea": "Korea Republic",
    "united states": "United States",
    "usa": "United States",
    "czechia": "Czech Republic",
    "czech republic": "Czech Republic",
    "bosnia and herzegovina": "Bosnia-Herzegovina",
    "bosnia-herzegovina": "Bosnia-Herzegovina",
    "ivory coast": "Ivory Coast",
    "cote divoire": "Ivory Coast",
    "cape verde islands": "Cape Verde Islands",
    "cape verde": "Cape Verde Islands",
    "dr congo": "DR Congo",
    "congo dr": "DR Congo",
    "curacao": "Curaçao",
    "curaçao": "Curaçao",
}


def _norm(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _load_cn_to_api_names() -> dict[str, str]:
    if not TEAM_MAP_PATH.exists():
        return {}
    return json.loads(TEAM_MAP_PATH.read_text(encoding="utf-8"))


def _is_placeholder_team(name: str) -> bool:
    return any(x in name for x in ("组", "胜者", "第", "待定", "TBD", "Winner"))


class FootballDataClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        headers = {"X-Auth-Token": self._api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._base_url}{path}",
                headers=headers,
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def competition_teams(self, code: str) -> list[dict[str, Any]]:
        data = await self._get(f"/competitions/{code}/teams")
        return list(data.get("teams") or [])

    async def competition_matches(
        self, code: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        data = await self._get(
            f"/competitions/{code}/matches",
            {"dateFrom": date_from, "dateTo": date_to},
        )
        return list(data.get("matches") or [])

    async def team_finished_matches(self, team_id: int, limit: int = 5) -> list[dict[str, Any]]:
        data = await self._get(
            f"/teams/{team_id}/matches",
            {"status": "FINISHED", "limit": limit},
        )
        return list(data.get("matches") or [])

    async def match_head2head(self, match_id: int, limit: int = 10) -> dict[str, Any]:
        return await self._get(f"/matches/{match_id}/head2head", {"limit": limit})

    async def competition_standings(self, code: str) -> list[dict[str, Any]]:
        data = await self._get(f"/competitions/{code}/standings")
        rows: list[dict[str, Any]] = []
        for block in data.get("standings") or []:
            for row in block.get("table") or []:
                rows.append(row)
        return rows


def _build_team_index(teams: list[dict[str, Any]]) -> dict[str, int]:
    index: dict[str, int] = {}
    for team in teams:
        tid = team.get("id")
        if tid is None:
            continue
        for field in ("name", "shortName", "tla"):
            val = team.get(field)
            if val:
                index[_norm(str(val))] = int(tid)
    for alias, canonical in _NAME_ALIASES.items():
        key = _norm(canonical)
        for team in teams:
            if _norm(str(team.get("name", ""))) == key:
                index[alias] = int(team["id"])
                break
    return index


def _resolve_team_id(
    cn_name: str, cn_map: dict[str, str], team_index: dict[str, int]
) -> Optional[int]:
    api_name = cn_map.get(cn_name)
    if not api_name:
        return team_index.get(_norm(cn_name))
    tid = team_index.get(_norm(api_name))
    if tid:
        return tid
    return team_index.get(_norm(api_name.replace("ç", "c")))


def _names_match(api_name: str, expected: str) -> bool:
    a, b = _norm(api_name), _norm(expected)
    if a == b:
        return True
    alias = _NAME_ALIASES.get(a)
    return alias is not None and _norm(alias) == b


def _parse_utc_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _find_fd_match(
    fd_matches: list[dict[str, Any]],
    home_api: str,
    away_api: str,
    kickoff_at: datetime,
) -> Optional[dict[str, Any]]:
    target_day = kickoff_at.date()
    for m in fd_matches:
        utc = _parse_utc_date(m["utcDate"])
        if utc.date() != target_day:
            continue
        home = m.get("homeTeam") or {}
        away = m.get("awayTeam") or {}
        h_name = str(home.get("name") or home.get("shortName") or "")
        a_name = str(away.get("name") or away.get("shortName") or "")
        if _names_match(h_name, home_api) and _names_match(a_name, away_api):
            return m
        if _names_match(h_name, away_api) and _names_match(a_name, home_api):
            return m
    return None


def _form_from_matches(
    team_id: int, matches: list[dict[str, Any]], team_label: str
) -> dict[str, Any]:
    last5: list[str] = []
    goals_for = 0
    goals_against = 0
    for m in matches:
        if m.get("status") != "FINISHED":
            continue
        score = (m.get("score") or {}).get("fullTime") or {}
        if score.get("home") is None or score.get("away") is None:
            continue
        home_id = (m.get("homeTeam") or {}).get("id")
        is_home = home_id == team_id
        gf = int(score["home"] if is_home else score["away"])
        ga = int(score["away"] if is_home else score["home"])
        goals_for += gf
        goals_against += ga
        if gf > ga:
            last5.append("W")
        elif gf < ga:
            last5.append("L")
        else:
            last5.append("D")
        if len(last5) >= 5:
            break
    return {
        "team": team_label,
        "last5": last5,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "sample_size": len(last5),
    }


def _h2h_payload(h2h: dict[str, Any], home_label: str, away_label: str) -> dict[str, Any]:
    agg = h2h.get("aggregates") or h2h.get("aggregate") or {}
    home_agg = agg.get("homeTeam") or {}
    away_agg = agg.get("awayTeam") or {}
    meetings = agg.get("numberOfMatches") or h2h.get("numberOfMatches") or len(
        h2h.get("matches") or []
    )
    return {
        "meetings": meetings,
        "home_team": home_label,
        "away_team": away_label,
        "home_wins": home_agg.get("wins", 0),
        "away_wins": away_agg.get("wins", 0),
        "draws": agg.get("draws", 0),
    }


def _standing_payload(
    tables: list[dict[str, Any]], team_id: int, team_label: str
) -> Optional[dict[str, Any]]:
    for row in tables:
        team = row.get("team") or {}
        if team.get("id") != team_id:
            continue
        return {
            "team": team_label,
            "position": row.get("position"),
            "played": row.get("playedGames"),
            "won": row.get("won"),
            "draw": row.get("draw"),
            "lost": row.get("lost"),
            "points": row.get("points"),
            "goals_for": row.get("goalsFor"),
            "goals_against": row.get("goalsAgainst"),
            "goal_difference": row.get("goalDifference"),
        }
    return None


async def sync_match_facts(
    session: AsyncSession,
    match_id: str,
    *,
    client: Optional[FootballDataClient] = None,
    fd_matches: Optional[list[dict[str, Any]]] = None,
    team_index: Optional[dict[str, int]] = None,
    standings_table: Optional[list[dict[str, Any]]] = None,
    cn_map: Optional[dict[str, str]] = None,
) -> int:
    if not settings.football_data_api_key:
        raise ValueError("FOOTBALL_DATA_API_KEY is not set")

    match = await session.get(Match, match_id)
    if not match:
        raise ValueError(f"Match not found: {match_id}")

    if _is_placeholder_team(match.home_team) or _is_placeholder_team(match.away_team):
        return 0

    cn_map = cn_map or _load_cn_to_api_names()
    client = client or FootballDataClient(
        settings.football_data_api_key, settings.football_data_base_url
    )
    code = settings.football_data_competition

    home_api = cn_map.get(match.home_team, match.home_team)
    away_api = cn_map.get(match.away_team, match.away_team)

    if team_index is None:
        teams = await client.competition_teams(code)
        team_index = _build_team_index(teams)

    home_id = _resolve_team_id(match.home_team, cn_map, team_index)
    away_id = _resolve_team_id(match.away_team, cn_map, team_index)
    if not home_id or not away_id:
        return 0

    if fd_matches is None:
        start = (match.kickoff_at - timedelta(days=2)).strftime("%Y-%m-%d")
        end = (match.kickoff_at + timedelta(days=2)).strftime("%Y-%m-%d")
        fd_matches = await client.competition_matches(code, start, end)

    fd_match = _find_fd_match(fd_matches, home_api, away_api, match.kickoff_at)

    if standings_table is None:
        standings_table = await client.competition_standings(code)

    await session.execute(
        delete(MatchFact).where(
            MatchFact.match_id == match_id,
            MatchFact.source == SOURCE,
        )
    )

    facts: list[MatchFact] = []
    data_version = f"football-data-{datetime.utcnow():%Y%m%d}"

    home_matches = await client.team_finished_matches(home_id, limit=5)
    facts.append(
        MatchFact(
            match_id=match_id,
            fact_type="recent_form",
            evidence_id=f"EV-fd-{match_id}-home-form",
            source=SOURCE,
            payload=_form_from_matches(home_id, home_matches, match.home_team),
            data_version=data_version,
        )
    )

    away_matches = await client.team_finished_matches(away_id, limit=5)
    facts.append(
        MatchFact(
            match_id=match_id,
            fact_type="recent_form",
            evidence_id=f"EV-fd-{match_id}-away-form",
            source=SOURCE,
            payload=_form_from_matches(away_id, away_matches, match.away_team),
            data_version=data_version,
        )
    )

    if fd_match and fd_match.get("id"):
        h2h = await client.match_head2head(int(fd_match["id"]), limit=10)
        facts.append(
            MatchFact(
                match_id=match_id,
                fact_type="head_to_head",
                evidence_id=f"EV-fd-{match_id}-h2h",
                source=SOURCE,
                payload=_h2h_payload(h2h, match.home_team, match.away_team),
                data_version=data_version,
            )
        )

    home_standing = _standing_payload(standings_table, home_id, match.home_team)
    if home_standing:
        facts.append(
            MatchFact(
                match_id=match_id,
                fact_type="standing",
                evidence_id=f"EV-fd-{match_id}-home-standing",
                source=SOURCE,
                payload=home_standing,
                data_version=data_version,
            )
        )

    away_standing = _standing_payload(standings_table, away_id, match.away_team)
    if away_standing:
        facts.append(
            MatchFact(
                match_id=match_id,
                fact_type="standing",
                evidence_id=f"EV-fd-{match_id}-away-standing",
                source=SOURCE,
                payload=away_standing,
                data_version=data_version,
            )
        )

    for fact in facts:
        session.add(fact)

    if match.data_version.startswith("fifa") or match.data_version == "v1":
        match.data_version = data_version

    await session.commit()
    return len(facts)


async def sync_all_match_facts(session: AsyncSession) -> dict[str, int]:
    if not settings.football_data_api_key:
        raise ValueError("FOOTBALL_DATA_API_KEY is not set")

    client = FootballDataClient(
        settings.football_data_api_key, settings.football_data_base_url
    )
    code = settings.football_data_competition
    cn_map = _load_cn_to_api_names()

    result = await session.execute(select(Match).order_by(Match.kickoff_at))
    matches = list(result.scalars().all())
    if not matches:
        return {"synced": 0, "skipped": 0, "facts": 0}

    min_ko = min(m.kickoff_at for m in matches)
    max_ko = max(m.kickoff_at for m in matches)
    date_from = (min_ko - timedelta(days=3)).strftime("%Y-%m-%d")
    date_to = (max_ko + timedelta(days=3)).strftime("%Y-%m-%d")

    teams = await client.competition_teams(code)
    team_index = _build_team_index(teams)
    fd_matches = await client.competition_matches(code, date_from, date_to)
    standings_table = await client.competition_standings(code)

    synced = 0
    skipped = 0
    total_facts = 0

    for match in matches:
        if _is_placeholder_team(match.home_team) or _is_placeholder_team(match.away_team):
            skipped += 1
            continue
        count = await sync_match_facts(
            session,
            match.id,
            client=client,
            fd_matches=fd_matches,
            team_index=team_index,
            standings_table=standings_table,
            cn_map=cn_map,
        )
        if count > 0:
            synced += 1
            total_facts += count
        else:
            skipped += 1

    return {"synced": synced, "skipped": skipped, "facts": total_facts}
