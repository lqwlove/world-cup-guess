"""Pull match facts from football-data.org into match_facts."""

import argparse
import asyncio
import sys

from app.db import async_session_factory
from app.services.football_data_service import sync_all_match_facts, sync_match_facts


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sync match facts from football-data.org")
    parser.add_argument("--match-id", help="Sync a single match id (e.g. fifa-400021443)")
    args = parser.parse_args()

    async with async_session_factory() as session:
        try:
            if args.match_id:
                count = await sync_match_facts(session, args.match_id)
                print(f"Synced {count} facts for {args.match_id}")
            else:
                stats = await sync_all_match_facts(session)
                print(
                    f"Done: {stats['synced']} matches, {stats['facts']} facts, "
                    f"{stats['skipped']} skipped"
                )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"API error: {exc}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
