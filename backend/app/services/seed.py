from __future__ import annotations

import json
import secrets

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import ProcessParamRow, User
from app.models.schemas import ProcessParams


def _uid() -> str:
    return secrets.token_hex(12)


DEFAULT_USERS = (
    ("admin", "admin123", "admin"),
    ("user", "user123", "user"),
)


def seed_defaults(db: Session) -> None:
    if db.query(User).count() == 0:
        for username, password, role in DEFAULT_USERS:
            db.add(
                User(
                    id=_uid(),
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                )
            )
    if db.query(ProcessParamRow).count() == 0:
        db.add(
            ProcessParamRow(
                id=1,
                payload_json=ProcessParams().model_dump_json(),
            )
        )
    db.commit()


def load_process_params(db: Session) -> ProcessParams:
    row = db.get(ProcessParamRow, 1)
    if row is None:
        return ProcessParams()
    data = json.loads(row.payload_json)
    return ProcessParams.model_validate(data)


def save_process_params(db: Session, params: ProcessParams) -> ProcessParams:
    row = db.get(ProcessParamRow, 1)
    payload = params.model_dump_json()
    if row is None:
        db.add(ProcessParamRow(id=1, payload_json=payload))
    else:
        row.payload_json = payload
    db.commit()
    return params
