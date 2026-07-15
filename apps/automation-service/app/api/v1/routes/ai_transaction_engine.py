from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.deps import get_db, get_current_user
from app.core.response import ResultObject

router = APIRouter(prefix="/ai-transaction", tags=["AI交易引擎"])

@router.post("/run", response_model=ResultObject)
async def run_engine(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return ResultObject.failed(
        "AI 交易引擎目前仅有规则骨架，未执行任何交易策略",
        503,
    )
