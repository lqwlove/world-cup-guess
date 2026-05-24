import json
from pathlib import Path
from typing import Any, Optional

import jsonschema
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ConsensusArtifact
from app.schemas.consensus import ConsensusArtifactOut

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "consensus_v1.json"
CONSENSUS_SCHEMA = json.loads(SCHEMA_PATH.read_text())


def validate_consensus_artifact(data: dict[str, Any]) -> tuple[bool, Optional[str]]:
    try:
        jsonschema.validate(instance=data, schema=CONSENSUS_SCHEMA)
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e.message)


async def get_latest_consensus(
    session: AsyncSession, match_id: str
) -> Optional[ConsensusArtifactOut]:
    result = await session.execute(
        select(ConsensusArtifact)
        .where(ConsensusArtifact.match_id == match_id)
        .order_by(desc(ConsensusArtifact.created_at))
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return ConsensusArtifactOut(
        match_id=row.match_id,
        discussion_id=str(row.discussion_id),
        schema_version=row.schema_version,
        strength=row.strength,
        artifact=row.json_data,
        created_at=row.created_at,
    )
