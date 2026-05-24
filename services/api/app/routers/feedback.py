from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.entities import Feedback
from app.schemas.discussion import FeedbackCreate

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("")
async def submit_feedback(body: FeedbackCreate, session: AsyncSession = Depends(get_session)):
    session.add(
        Feedback(
            match_id=body.match_id,
            session_id=body.session_id,
            vote=body.vote,
        )
    )
    await session.commit()
    return {"ok": True}
