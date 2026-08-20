from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import History, User
from app.models.schemas import HistoryOut

router = APIRouter(prefix="/history", tags=["history"])


def _to_out(row: History, username: str) -> HistoryOut:
    request = json.loads(row.request_json) if row.request_json else {}
    blob = json.loads(row.result_json) if row.result_json else {}
    return HistoryOut(
        id=row.id,
        created_at=row.created_at,
        username=username,
        success=row.success,
        error_message=row.error_message,
        coal_gangue=row.coal_gangue,
        fly_ash=row.fly_ash,
        limestone=row.limestone,
        gypsum=row.gypsum,
        carbide_slag=row.carbide_slag,
        al_so3_ratio=row.al_so3_ratio,
        ca_ratio=row.ca_ratio,
        xy_ratio=row.xy_ratio,
        request=request,
        result=blob.get("result"),
    )


@router.get("", response_model=list[HistoryOut])
def list_history(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[HistoryOut]:
    query = db.query(History, User.username).join(User, History.user_id == User.id)
    if user.role != "admin":
        query = query.filter(History.user_id == user.id)
    rows = query.order_by(History.created_at.desc()).limit(limit).all()
    return [_to_out(row, username) for row, username in rows]


@router.delete("", status_code=204)
def clear_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    query = db.query(History)
    if user.role != "admin":
        query = query.filter(History.user_id == user.id)
    query.delete(synchronize_session=False)
    db.commit()


@router.delete("/{history_id}", status_code=204)
def delete_history(
    history_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    row = db.get(History, history_id)
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    if user.role != "admin" and row.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权删除该记录")
    db.delete(row)
    db.commit()
