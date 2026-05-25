from datetime import datetime, timezone


def serialize_utc_datetime(dt: datetime) -> str:
    """DB 存的是 naive UTC，序列化时显式带 Z，避免前端当本地时间解析。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
