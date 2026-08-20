from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.database import get_db
from app.db.models import History, User
from app.models.schemas import CalcRequest, CalcResponse, ProcessParams
from app.services.seed import load_process_params, save_process_params
from app.services.solver import SolverError, example_materials, solve_blend

router = APIRouter(prefix="/calc", tags=["calc"])


def _save_history(
    db: Session,
    user: User,
    request: CalcRequest,
    *,
    success: bool,
    result: dict | None,
    error_code: str | None,
    error_message: str | None,
) -> str:
    masses = (result or {}).get("masses") or {}
    checks = (result or {}).get("checks") or {}
    record = History(
        id=secrets.token_hex(12),
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
        success=success,
        error_message=error_message,
        request_json=request.model_dump_json(),
        result_json=json.dumps(
            {"success": success, "result": result, "error_code": error_code, "error_message": error_message},
            ensure_ascii=False,
        ),
        coal_gangue=masses.get("coal_gangue"),
        fly_ash=masses.get("fly_ash"),
        limestone=masses.get("limestone"),
        gypsum=masses.get("gypsum"),
        carbide_slag=masses.get("carbide_slag"),
        al_so3_ratio=(checks.get("al2o3_so3") or {}).get("actual"),
        ca_ratio=(checks.get("cao_ratio") or {}).get("actual"),
        xy_ratio=(checks.get("gangue_flyash") or {}).get("actual"),
    )
    db.add(record)
    db.commit()
    return record.id


@router.get("/example")
def get_example() -> dict:
    return {"materials": example_materials(), "batch_mass": 100}


@router.get("/params", response_model=ProcessParams)
def get_params(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> ProcessParams:
    return load_process_params(db)


@router.put("/params", response_model=ProcessParams)
def update_params(
    body: ProcessParams,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ProcessParams:
    return save_process_params(db, body)


@router.post("/solve", response_model=CalcResponse)
def solve(
    body: CalcRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalcResponse:
    stored = load_process_params(db)
    if body.params is None:
        body = body.model_copy(update={"params": stored})
    try:
        result = solve_blend(body)
    except SolverError as exc:
        history_id = _save_history(
            db,
            user,
            body,
            success=False,
            result=None,
            error_code=exc.code,
            error_message=exc.message,
        )
        return CalcResponse(
            success=False,
            error_code=exc.code,
            error_message=exc.message,
            history_id=history_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = result.model_dump()
    history_id = _save_history(
        db,
        user,
        body,
        success=True,
        result=payload,
        error_code=None,
        error_message=None,
    )
    return CalcResponse(success=True, result=result, history_id=history_id)
