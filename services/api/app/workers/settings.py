from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.workers.tasks import (
    followup_chat_task,
    pregenerate_hot_matches,
    refresh_market_snapshots,
    resume_discussion_task,
    run_deliberation_task,
)

settings = get_settings()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        run_deliberation_task,
        resume_discussion_task,
        followup_chat_task,
        refresh_market_snapshots,
        pregenerate_hot_matches,
    ]
    cron_jobs = [
        cron(refresh_market_snapshots, minute={0, 15, 30, 45}),
        cron(pregenerate_hot_matches, hour={0, 6, 12, 18}, minute=0),
    ]
    queue_name = "arq:queue"
    max_jobs = 2
    job_timeout = settings.deliberation_timeout_seconds
