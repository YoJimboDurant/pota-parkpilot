from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DIR = PROJECT_ROOT / "data" / "sessions"
CURRENT_SESSION_PATH = SESSIONS_DIR / "current_session.json"


# ============================================================
# MODELS
# ============================================================

@dataclass
class SessionDX:
    session_id: str
    session_date_local: str
    park_id: str
    operators_present_lx: list[str]
    active_operator: str
    status: str
    created_at_local: str
    last_updated_local: str
    last_mode: str = "CW"
    last_band: str = "20M"


# ============================================================
# HELPERS
# ============================================================

def _ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _now_local_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _make_session_id(session_date_utc_x: str, park_id_x: str) -> str:
    park_clean_x = park_id_x.upper().strip()
    return f"{session_date_utc_x}_{park_clean_x}"


def _normalize_operator_list(operators_lx: list[str]) -> list[str]:
    return [op.upper().strip() for op in operators_lx if op.strip()]


def _normalize_park_id(park_id_x: str) -> str:
    return park_id_x.upper().strip()


# ============================================================
# CORE API
# ============================================================

def get_current_session() -> Optional[SessionDX]:
    _ensure_sessions_dir()

    if not CURRENT_SESSION_PATH.exists():
        return None

    with open(CURRENT_SESSION_PATH, "r", encoding="utf-8") as fx:
        data_dx = json.load(fx)

    return SessionDX(**data_dx)


def save_session(session_dx: SessionDX) -> None:
    _ensure_sessions_dir()

    session_dx.last_updated_local = _now_local_str()

    with open(CURRENT_SESSION_PATH, "w", encoding="utf-8") as fx:
        json.dump(asdict(session_dx), fx, indent=2)


def start_or_resume_session(
    park_id_x: str,
    operators_present_lx: list[str],
    active_operator_x: str,
) -> tuple[SessionDX, str]:
    park_id_x = _normalize_park_id(park_id_x)
    operators_present_lx = _normalize_operator_list(operators_present_lx)
    active_operator_x = active_operator_x.upper().strip()
    today_utc_x = _today_utc_str()

    if not park_id_x:
        raise ValueError("park_id is required")

    if not operators_present_lx:
        raise ValueError("at least one operator is required")

    if active_operator_x not in operators_present_lx:
        raise ValueError("active operator must be in operators_present")

    existing_dx = get_current_session()

    if existing_dx:
        same_day_x = existing_dx.session_date_local == today_utc_x
        same_park_x = existing_dx.park_id == park_id_x

        if existing_dx.status == "active" and same_day_x and same_park_x:
            existing_dx.operators_present_lx = operators_present_lx
            existing_dx.active_operator = active_operator_x
            save_session(existing_dx)
            return existing_dx, "resumed"

    created_at_local_x = _now_local_str()

    session_dx = SessionDX(
        session_id=_make_session_id(today_utc_x, park_id_x),
        session_date_local=today_utc_x,
        park_id=park_id_x,
        operators_present_lx=operators_present_lx,
        active_operator=active_operator_x,
        status="active",
        created_at_local=created_at_local_x,
        last_updated_local=created_at_local_x,
        last_mode="CW",
        last_band="20M",
    )

    save_session(session_dx)
    return session_dx, "created"


def set_active_operator(active_operator_x: str) -> Optional[SessionDX]:
    session_dx = get_current_session()

    if session_dx is None:
        return None

    active_operator_x = active_operator_x.upper().strip()

    if active_operator_x not in session_dx.operators_present_lx:
        raise ValueError("operator is not present in current session")

    session_dx.active_operator = active_operator_x
    save_session(session_dx)
    return session_dx


def close_current_session() -> Optional[SessionDX]:
    session_dx = get_current_session()

    if session_dx is None:
        return None

    session_dx.status = "closed"
    save_session(session_dx)
    return session_dx


def set_last_mode(last_mode_x: str) -> Optional[SessionDX]:
    session_dx = get_current_session()

    if session_dx is None:
        return None

    session_dx.last_mode = last_mode_x.upper().strip()
    save_session(session_dx)
    return session_dx


def set_last_band(last_band_x: str) -> Optional[SessionDX]:
    session_dx = get_current_session()

    if session_dx is None:
        return None

    session_dx.last_band = last_band_x.upper().strip()
    save_session(session_dx)
    return session_dx