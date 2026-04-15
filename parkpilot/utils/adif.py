from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
EXPORTS_DIR = DATA_DIR / "exports"

CONTACTS_PATH = SESSIONS_DIR / "contacts.json"


# ============================================================
# CONSTANTS
# ============================================================

ADIF_VERSION = "3.1.4"
PROGRAM_ID = "ParkPilot"

MODE_MAP_DX = {
    "CW": "CW",
    "SSB": "SSB",
    "SSTV": "SSTV",
    "DIGITAL": "MFSK",  # temporary compromise until submodes are tracked
    "OTHER": "OTHER",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def _normalize_str(value_x: Any) -> str:
    if value_x is None:
        return ""
    return str(value_x).strip()


def _normalize_upper_str(value_x: Any) -> str:
    return _normalize_str(value_x).upper()


def _normalize_mode(mode_x: Any) -> str:
    mode_clean_x = _normalize_upper_str(mode_x)
    return MODE_MAP_DX.get(mode_clean_x, mode_clean_x or "OTHER")


def _slugify_filename_part(value_x: Any) -> str:
    value_clean_x = _normalize_upper_str(value_x)

    if not value_clean_x:
        return "UNKNOWN"

    out_chars_lx: list[str] = []
    for char_x in value_clean_x:
        if char_x.isalnum() or char_x in {"-", "_"}:
            out_chars_lx.append(char_x)
        else:
            out_chars_lx.append("_")

    return "".join(out_chars_lx).strip("_") or "UNKNOWN"


def _ensure_exports_dir() -> None:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CONTACT LOADING
# ============================================================

def _load_contacts_lx() -> list[dict[str, Any]]:
    if not CONTACTS_PATH.exists():
        return []

    with open(CONTACTS_PATH, "r", encoding="utf-8") as fx:
        data_x = json.load(fx)

    if not isinstance(data_x, list):
        raise ValueError("contacts.json does not contain a list of contacts")

    return data_x


def _normalize_operators_in_qso_lx(contact_dx: dict[str, Any]) -> list[str]:
    """
    Returns the normalized operator list for a contact.

    Preference:
    1. operators_in_qso_lx if present and non-empty
    2. fallback to legacy single operator field
    """
    operators_raw_x = contact_dx.get("operators_in_qso_lx", [])

    operators_lx: list[str] = []

    if isinstance(operators_raw_x, list):
        for operator_x in operators_raw_x:
            operator_clean_x = _normalize_upper_str(operator_x)
            if operator_clean_x:
                operators_lx.append(operator_clean_x)

    if not operators_lx:
        legacy_operator_x = _normalize_upper_str(contact_dx.get("operator"))
        if legacy_operator_x:
            operators_lx.append(legacy_operator_x)

    # de-duplicate while preserving order
    seen_sx: set[str] = set()
    deduped_lx: list[str] = []

    for operator_x in operators_lx:
        if operator_x not in seen_sx:
            seen_sx.add(operator_x)
            deduped_lx.append(operator_x)

    return deduped_lx


# ============================================================
# TIME HELPERS
# ============================================================

def _parse_timestamp_utc(timestamp_utc_x: Any) -> datetime:
    timestamp_clean_x = _normalize_str(timestamp_utc_x)

    if not timestamp_clean_x:
        raise ValueError("timestamp_utc is missing")

    if timestamp_clean_x.endswith("Z"):
        timestamp_clean_x = timestamp_clean_x[:-1] + "+00:00"

    dt_x = datetime.fromisoformat(timestamp_clean_x)

    if dt_x.tzinfo is None:
        dt_x = dt_x.replace(tzinfo=timezone.utc)

    return dt_x.astimezone(timezone.utc)


def _adif_date_x(dt_x: datetime) -> str:
    return dt_x.strftime("%Y%m%d")


def _adif_time_x(dt_x: datetime) -> str:
    return dt_x.strftime("%H%M%S")


# ============================================================
# ADIF HELPERS
# ============================================================

def _make_adif_field(field_name_x: str, value_x: Any) -> str:
    value_str_x = _normalize_str(value_x)

    if not value_str_x:
        return ""

    return f"<{field_name_x.upper()}:{len(value_str_x)}>{value_str_x}"


def _build_adif_header() -> str:
    parts_lx = [
        _make_adif_field("ADIF_VER", ADIF_VERSION),
        _make_adif_field("PROGRAMID", PROGRAM_ID),
        "<EOH>",
        "",
    ]
    return "\n".join(parts_lx)


# ============================================================
# CONTACT FILTERING
# ============================================================

def get_contacts_for_session(
    session_id_x: str,
    operator_x: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Return contacts for a session.

    If operator_x is provided, include contacts where operator_x appears
    in operators_in_qso_lx.
    """
    contacts_lx = _load_contacts_lx()

    session_id_clean_x = _normalize_str(session_id_x)
    operator_clean_x = _normalize_upper_str(operator_x) if operator_x else ""

    filtered_lx: list[dict[str, Any]] = []

    for contact_dx in contacts_lx:
        contact_session_id_x = _normalize_str(contact_dx.get("session_id"))

        if contact_session_id_x != session_id_clean_x:
            continue

        if operator_clean_x:
            operators_in_qso_lx = _normalize_operators_in_qso_lx(contact_dx)
            if operator_clean_x not in operators_in_qso_lx:
                continue

        filtered_lx.append(contact_dx)

    return filtered_lx


def get_session_operators(session_id_x: str) -> list[str]:
    """
    Return the sorted unique set of operators participating in a session.
    """
    contacts_lx = get_contacts_for_session(session_id_x=session_id_x)
    operators_sx: set[str] = set()

    for contact_dx in contacts_lx:
        for operator_x in _normalize_operators_in_qso_lx(contact_dx):
            operators_sx.add(operator_x)

    return sorted(operators_sx)


# ============================================================
# ADIF RECORD BUILDING
# ============================================================

def contact_to_adif_record(
    contact_dx: dict[str, Any],
    station_callsign_x: Optional[str] = None,
) -> str:
    """
    Build one ADIF record for one contact, from the perspective of
    the operator whose file is being exported.
    """
    call_x = _normalize_upper_str(contact_dx.get("call"))
    band_x = _normalize_upper_str(contact_dx.get("band"))
    mode_x = _normalize_mode(contact_dx.get("mode"))
    rst_sent_x = _normalize_str(contact_dx.get("rst_sent"))
    rst_rcvd_x = _normalize_str(contact_dx.get("rst_rcvd"))
    park_id_x = _normalize_upper_str(contact_dx.get("park_id"))
    notes_x = _normalize_str(contact_dx.get("notes"))
    timestamp_utc_x = _normalize_str(contact_dx.get("timestamp_utc"))

    station_callsign_clean_x = _normalize_upper_str(station_callsign_x)
    operators_in_qso_lx = _normalize_operators_in_qso_lx(contact_dx)
    shared_ops_x = ",".join(operators_in_qso_lx)

    if not call_x:
        raise ValueError("contact is missing call")

    if not timestamp_utc_x:
        raise ValueError(f"contact {call_x} is missing timestamp_utc")

    dt_utc_x = _parse_timestamp_utc(timestamp_utc_x)
    qso_date_x = _adif_date_x(dt_utc_x)
    time_on_x = _adif_time_x(dt_utc_x)

    comment_parts_lx: list[str] = []

    if notes_x:
        comment_parts_lx.append(notes_x)

    if shared_ops_x:
        comment_parts_lx.append(f"Shared QSO operators: {shared_ops_x}")

    comment_x = " | ".join(comment_parts_lx)

    record_parts_lx = [
        _make_adif_field("STATION_CALLSIGN", station_callsign_clean_x),
        _make_adif_field("OPERATOR", station_callsign_clean_x),
        _make_adif_field("CALL", call_x),
        _make_adif_field("QSO_DATE", qso_date_x),
        _make_adif_field("TIME_ON", time_on_x),
        _make_adif_field("BAND", band_x),
        _make_adif_field("MODE", mode_x),
        _make_adif_field("RST_SENT", rst_sent_x),
        _make_adif_field("RST_RCVD", rst_rcvd_x),
        _make_adif_field("MY_SIG", "POTA"),
        _make_adif_field("MY_SIG_INFO", park_id_x),
        _make_adif_field("COMMENT", comment_x),
        "<EOR>",
    ]

    return "\n".join(part_x for part_x in record_parts_lx if part_x)


def build_adif_text(
    contacts_lx: list[dict[str, Any]],
    station_callsign_x: Optional[str] = None,
) -> str:
    adif_records_lx = [
        contact_to_adif_record(
            contact_dx=contact_dx,
            station_callsign_x=station_callsign_x,
        )
        for contact_dx in contacts_lx
    ]

    if not adif_records_lx:
        return _build_adif_header()

    return _build_adif_header() + "\n".join(adif_records_lx) + "\n"


# ============================================================
# FILE NAMING
# ============================================================

def _build_export_filename(
    session_date_local_x: Any,
    park_id_x: Any,
    operator_x: Any,
) -> str:
    date_part_x = _slugify_filename_part(session_date_local_x)
    park_part_x = _slugify_filename_part(park_id_x)
    operator_part_x = _slugify_filename_part(operator_x)

    return f"{date_part_x}_{park_part_x}_{operator_part_x}.adi"


# ============================================================
# EXPORT FUNCTIONS
# ============================================================

def export_adif_for_session(
    session_id_x: str,
    operator_x: str,
) -> Path:
    """
    Export one ADIF file for one operator in a session.

    Includes every contact where operator_x appears in operators_in_qso_lx.
    """
    _ensure_exports_dir()

    operator_clean_x = _normalize_upper_str(operator_x)
    if not operator_clean_x:
        raise ValueError("operator_x is required")

    contacts_lx = get_contacts_for_session(
        session_id_x=session_id_x,
        operator_x=operator_clean_x,
    )

    if not contacts_lx:
        raise ValueError(
            f"no contacts found for session '{session_id_x}' and operator '{operator_clean_x}'"
        )

    first_contact_dx = contacts_lx[0]
    session_date_local_x = first_contact_dx.get("session_date_local", "")
    park_id_x = first_contact_dx.get("park_id", "")

    filename_x = _build_export_filename(
        session_date_local_x=session_date_local_x,
        park_id_x=park_id_x,
        operator_x=operator_clean_x,
    )
    export_path_x = EXPORTS_DIR / filename_x

    adif_text_x = build_adif_text(
        contacts_lx=contacts_lx,
        station_callsign_x=operator_clean_x,
    )

    with open(export_path_x, "w", encoding="utf-8", newline="\n") as fx:
        fx.write(adif_text_x)

    return export_path_x


def export_all_adif_for_session(session_id_x: str) -> list[Path]:
    """
    Export one ADIF file per operator participating in a session.
    """
    operator_lx = get_session_operators(session_id_x)

    if not operator_lx:
        raise ValueError(f"no operators found for session '{session_id_x}'")

    export_paths_lx = [
        export_adif_for_session(
            session_id_x=session_id_x,
            operator_x=operator_x,
        )
        for operator_x in operator_lx
    ]

    return export_paths_lx