from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ConsensusArtifact, Discussion, Match
from app.schemas.match import MatchDetailOut, MatchListOut

# 日期筛选按北京时间自然日，再换算为 DB 中的 naive UTC
_CN_TZ = ZoneInfo("Asia/Shanghai")


def _deliberation_status(discussion: Optional[Discussion], artifact: Optional[ConsensusArtifact]) -> str:
    if not discussion:
        return "ready" if artifact else "none"
    if discussion.status in ("running", "pending"):
        return "generating"
    if discussion.status == "failed":
        return "failed"
    if discussion.status == "partial":
        return "partial"
    if discussion.status == "completed":
        return "ready"
    return "none"


async def list_matches(
    session: AsyncSession,
    *,
    date_filter: Optional[str] = None,
    stage: Optional[str] = None,
    group_code: Optional[str] = None,
) -> list[MatchListOut]:
    # 仅按开球时间正序，不按 is_hot 置顶
    stmt = select(Match).order_by(Match.kickoff_at.asc())
    if stage:
        stmt = stmt.where(Match.stage == stage)
    if group_code:
        stmt = stmt.where(Match.group_code == group_code)
    if date_filter:
        d = date.fromisoformat(date_filter)
        start_cn = datetime.combine(d, time.min, tzinfo=_CN_TZ)
        end_cn = datetime.combine(d, time.max, tzinfo=_CN_TZ)
        start = start_cn.astimezone(timezone.utc).replace(tzinfo=None)
        end = end_cn.astimezone(timezone.utc).replace(tzinfo=None)
        stmt = stmt.where(Match.kickoff_at >= start, Match.kickoff_at <= end)

    result = await session.execute(stmt)
    matches = result.scalars().all()
    out: list[MatchListOut] = []
    for m in matches:
        disc = await _latest_discussion(session, m.id)
        art = await _latest_artifact(session, m.id)
        out.append(
            MatchListOut(
                id=m.id,
                home_team=m.home_team,
                away_team=m.away_team,
                home_flag=m.home_flag,
                away_flag=m.away_flag,
                kickoff_at=m.kickoff_at,
                stage=m.stage,
                group_code=m.group_code,
                status=m.status,
                is_hot=m.is_hot,
                deliberation_status=_deliberation_status(disc, art),
            )
        )
    return out


async def get_match(session: AsyncSession, match_id: str) -> Optional[MatchDetailOut]:
    m = await session.get(Match, match_id)
    if not m:
        return None
    disc = await _latest_discussion(session, match_id)
    art = await _latest_artifact(session, match_id)
    return MatchDetailOut(
        id=m.id,
        home_team=m.home_team,
        away_team=m.away_team,
        home_flag=m.home_flag,
        away_flag=m.away_flag,
        kickoff_at=m.kickoff_at,
        stage=m.stage,
        group_code=m.group_code,
        status=m.status,
        is_hot=m.is_hot,
        data_version=m.data_version,
        deliberation_status=_deliberation_status(disc, art),
        latest_discussion_id=str(disc.id) if disc else None,
        deliberation_error=disc.error_reason if disc and disc.status == "failed" else None,
    )


async def _latest_discussion(session: AsyncSession, match_id: str) -> Optional[Discussion]:
    result = await session.execute(
        select(Discussion)
        .where(Discussion.match_id == match_id)
        .order_by(desc(Discussion.started_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_artifact(session: AsyncSession, match_id: str) -> Optional[ConsensusArtifact]:
    result = await session.execute(
        select(ConsensusArtifact)
        .where(ConsensusArtifact.match_id == match_id)
        .order_by(desc(ConsensusArtifact.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
