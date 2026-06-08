"""Delete all deliberation data for a match so analysis can be restarted from the UI."""

import sys

import psycopg2

from app.config import get_settings

settings = get_settings()


def reset_match_discussion(match_id: str) -> dict:
    conn = psycopg2.connect(settings.database_url_sync)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text FROM discussions WHERE match_id = %s",
                (match_id,),
            )
            thread_ids = [row[0] for row in cur.fetchall()]

            if thread_ids:
                cur.execute(
                    "DELETE FROM discussion_messages WHERE discussion_id = ANY(%s::uuid[])",
                    (thread_ids,),
                )
                cur.execute(
                    "DELETE FROM consensus_artifacts WHERE discussion_id = ANY(%s::uuid[])",
                    (thread_ids,),
                )
                cur.execute(
                    "DELETE FROM discussions WHERE match_id = %s",
                    (match_id,),
                )
            else:
                cur.execute(
                    "DELETE FROM consensus_artifacts WHERE match_id = %s",
                    (match_id,),
                )

            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                cur.execute("SAVEPOINT ck_del")
                try:
                    cur.execute(
                        f"DELETE FROM {table} WHERE thread_id = ANY(%s)",
                        (thread_ids,),
                    )
                    cur.execute("RELEASE SAVEPOINT ck_del")
                except psycopg2.Error:
                    cur.execute("ROLLBACK TO SAVEPOINT ck_del")

        conn.commit()
        return {
            "match_id": match_id,
            "discussions_removed": len(thread_ids),
            "thread_ids": thread_ids,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    match_id = sys.argv[1] if len(sys.argv) > 1 else "fifa-400021443"
    info = reset_match_discussion(match_id)
    print(
        f"已重置 {info['match_id']}：删除 {info['discussions_removed']} 场合议记录"
        + (f"（{', '.join(info['thread_ids'])}）" if info["thread_ids"] else "（无历史合议）")
    )


if __name__ == "__main__":
    main()
