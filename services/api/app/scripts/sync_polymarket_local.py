"""Fetch Polymarket locally (VPN) and push snapshots to remote API or local DB."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.db import async_session_factory
from app.services.market_service import fetch_gamma_for_mapping, import_market_snapshot

settings = get_settings()

DEFAULT_SEEDS = Path(__file__).resolve().parents[4] / "seeds" / "market_mappings.json"


def load_mappings(seeds_path: Path, match_id: str | None) -> list[dict[str, Any]]:
    if not seeds_path.is_file():
        raise FileNotFoundError(f"Mappings file not found: {seeds_path}")
    rows = json.loads(seeds_path.read_text(encoding="utf-8"))
    if match_id:
        rows = [r for r in rows if r.get("match_id") == match_id]
    return [r for r in rows if r.get("platform") == "polymarket"]


def fetch_one(row: dict[str, Any], gamma_url: str | None) -> tuple[dict[str, float], dict[str, Any]] | None:
    slug = row["event_slug"]
    outcome_map = row.get("outcome_map") or {}
    parsed = fetch_gamma_for_mapping(slug, outcome_map, gamma_url=gamma_url)
    if not parsed:
        return None
    probs, meta = parsed
    meta["event_slug"] = slug
    meta["source"] = "local_gamma_sync"
    return probs, meta


async def push_remote(
    api_url: str,
    match_id: str,
    probabilities: dict[str, float],
    raw: dict[str, Any],
) -> None:
    url = f"{api_url.rstrip('/')}/api/matches/{match_id}/market/import"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "probabilities": probabilities,
                "raw": raw,
                "platform": "polymarket",
                "source": "local_gamma_sync",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"{match_id} push failed {resp.status_code}: {resp.text[:300]}")


async def import_local(match_id: str, probabilities: dict[str, float], raw: dict[str, Any]) -> None:
    async with async_session_factory() as session:
        await import_market_snapshot(session, match_id, probabilities, raw=raw)


async def run(args: argparse.Namespace) -> int:
    mappings = load_mappings(Path(args.seeds), args.match_id)
    if not mappings:
        print("No polymarket mappings to sync.", file=sys.stderr)
        return 1

    ok, fail = 0, 0
    for row in mappings:
        mid = row["match_id"]
        slug = row["event_slug"]
        print(f"[fetch] {mid} ← {slug}")
        fetched = fetch_one(row, args.gamma_url)
        if not fetched:
            print(f"  ✗ Gamma fetch failed", file=sys.stderr)
            fail += 1
            continue
        probs, meta = fetched
        print(f"  ✓ home={probs.get('home')} draw={probs.get('draw')} away={probs.get('away')}")

        try:
            if args.api_url:
                await push_remote(args.api_url, mid, probs, meta)
                print(f"  → pushed to {args.api_url}")
            else:
                await import_local(mid, probs, meta)
                print("  → saved to local DATABASE_URL")
            ok += 1
        except Exception as exc:
            print(f"  ✗ import failed: {exc}", file=sys.stderr)
            fail += 1

    print(f"\nDone: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync Polymarket snapshots locally and push to server or local DB",
    )
    parser.add_argument("--match-id", help="Only sync one match (e.g. fifa-400021443)")
    parser.add_argument(
        "--seeds",
        default=str(DEFAULT_SEEDS),
        help="Path to market_mappings.json",
    )
    parser.add_argument(
        "--api-url",
        help="Remote site base URL, e.g. http://106.54.42.172:8081 (push mode)",
    )
    parser.add_argument(
        "--gamma-url",
        default=None,
        help=f"Gamma API base (default: {settings.polymarket_gamma_url})",
    )
    args = parser.parse_args()
    if not args.api_url and not args.match_id:
        pass  # local DB mode sync all from seeds
    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
