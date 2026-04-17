from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parkpilot.core.session_manager import get_current_session


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "parkpilot_config.json"
DATA_DIR = PROJECT_ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
CONTACTS_PATH = SESSIONS_DIR / "contacts.json"
STATE_PATH = SESSIONS_DIR / "wsjtx_state.json"


# ============================================================
# MODELS
# ============================================================

@dataclass
class WSJTXStateDX:
    adif_file: str
    n_processed_records: int
    last_poll_utc: str


# ============================================================
# CONFIG
# ============================================================

def load_config(config_path_x: Path | None = None) -> dict[str, Any]:
    config_path_x = config_path_x or CONFIG_PATH

    with open(config_path_x, "r", encoding="utf-8") as fx:
        cfg_dx = json.load(fx)

    required_fields_x = [
        "adif_file",
        "operators",
        "operator_field",
        "park_source_field",
        "park_regex",
        "poll_seconds",
    ]

    for field_x in required_fields_x:
        if field_x not in cfg_dx:
            raise ValueError(f"Missing required config field: {field_x}")

    cfg_dx["operators"] = [str(op).upper().strip() for op in cfg_dx["operators"] if str(op).strip()]
    cfg_dx["operator_field"] = str(cfg_dx["operator_field"]).upper().strip()
    cfg_dx["park_source_field"] = str(cfg_dx["park_source_field"]).upper().strip()
    cfg_dx["poll_seconds"] = int(cfg_dx.get("poll_seconds", 2))

    return cfg_dx


# ============================================================
# BASIC HELPERS
# ============================================================

def _utc_now_iso_x() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _load_json_list_x(path_x: Path) -> list[dict[str, Any]]:
    if not path_x.exists():
        return []

    raw_x = path_x.read_text(encoding="utf-8").strip()
    if not raw_x:
        return []

    data_x = json.loads(raw_x)
    if not isinstance(data_x, list):
        raise ValueError(f"{path_x.name} does not contain a list")

    return data_x


def _write_json_x(path_x: Path, data_x: Any) -> None:
    _ensure_sessions_dir()
    with open(path_x, "w", encoding="utf-8") as fx:
        json.dump(data_x, fx, indent=2)


def _normalize_upper_str(value_x: Any) -> str:
    if value_x is None:
        return ""
    return str(value_x).upper().strip()


def _normalize_plain_str(value_x: Any) -> str:
    if value_x is None:
        return ""
    return str(value_x).strip()

def resolve_adif_path(cfg_dx: dict[str, Any]) -> Path:
    candidate_lx: list[str] = []

    primary_x = str(cfg_dx.get("adif_file", "")).strip()
    if primary_x:
        candidate_lx.append(primary_x)

    for candidate_x in cfg_dx.get("adif_file_candidates", []):
        candidate_str_x = str(candidate_x).strip()
        if candidate_str_x:
            candidate_lx.append(candidate_str_x)

    for candidate_x in candidate_lx:
        path_x = Path(candidate_x).expanduser()
        if path_x.exists():
            return path_x

    if candidate_lx:
        return Path(candidate_lx[0]).expanduser()

    raise ValueError("No ADIF file path configured.")



# ============================================================
# ADIF PARSING
# ============================================================

def extract_adif_records(full_text_x: str) -> list[str]:
    return [
        rec_x.strip()
        for rec_x in re.split(r"<eor>", full_text_x, flags=re.IGNORECASE)
        if rec_x.strip()
    ]


def parse_adif_record(record_text_x: str) -> dict[str, str]:
    record_dx: dict[str, str] = {}

    text_x = record_text_x.replace("\n", " ").replace("\r", " ")
    pattern_x = re.compile(r"<([^:>]+):(\d+)(?::[^>]+)?>", re.IGNORECASE)

    for match_x in pattern_x.finditer(text_x):
        field_name_x = match_x.group(1).upper().strip()
        field_len_x = int(match_x.group(2))
        value_start_x = match_x.end()
        value_end_x = value_start_x + field_len_x
        value_x = text_x[value_start_x:value_end_x].strip()
        record_dx[field_name_x] = value_x

    return record_dx


def extract_operator_from_record(record_dx: dict[str, str], cfg_dx: dict[str, Any]) -> str:
    preferred_field_x = cfg_dx["operator_field"]

    operator_x = _normalize_upper_str(record_dx.get(preferred_field_x))
    if operator_x:
        return operator_x

    for fallback_field_x in ["OPERATOR", "STATION_CALLSIGN"]:
        operator_x = _normalize_upper_str(record_dx.get(fallback_field_x))
        if operator_x:
            return operator_x

    return ""


def extract_park_from_record(record_dx: dict[str, str], cfg_dx: dict[str, Any]) -> str:
    candidate_fields_lx = []

    preferred_field_x = str(cfg_dx.get("park_source_field", "")).upper().strip()
    if preferred_field_x:
        candidate_fields_lx.append(preferred_field_x)

    for fallback_field_x in ["MY_SIG_INFO", "COMMENT", "NOTES"]:
        if fallback_field_x not in candidate_fields_lx:
            candidate_fields_lx.append(fallback_field_x)

    pattern_x = str(cfg_dx["park_regex"]).replace("\\\\", "\\")

    for field_x in candidate_fields_lx:
        source_text_x = _normalize_upper_str(record_dx.get(field_x))
        if not source_text_x:
            continue

        match_x = re.search(pattern_x, source_text_x, flags=re.IGNORECASE)
        if match_x:
            return match_x.group(0).upper()

    return ""

def extract_timestamp_utc_from_record(record_dx: dict[str, str]) -> str:
    qso_date_x = _normalize_plain_str(record_dx.get("QSO_DATE"))
    time_on_x = _normalize_plain_str(record_dx.get("TIME_ON") or record_dx.get("TIME_OFF"))

    if not re.fullmatch(r"\d{8}", qso_date_x):
        return ""

    if not re.fullmatch(r"\d{4,6}", time_on_x):
        return ""

    time_on_x = time_on_x.ljust(6, "0")

    dt_x = datetime.strptime(f"{qso_date_x}{time_on_x}", "%Y%m%d%H%M%S")
    dt_x = dt_x.replace(tzinfo=timezone.utc)
    return dt_x.isoformat().replace("+00:00", "Z")


# ============================================================
# STATE
# ============================================================

def load_state(cfg_dx: dict[str, Any]) -> WSJTXStateDX:
    resolved_adif_x = str(resolve_adif_path(cfg_dx))

    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as fx:
            data_dx = json.load(fx)

        try:
            state_dx = WSJTXStateDX(**data_dx)
        except TypeError:
            state_dx = WSJTXStateDX(
                adif_file=resolved_adif_x,
                n_processed_records=0,
                last_poll_utc="",
            )
    else:
        state_dx = WSJTXStateDX(
            adif_file=resolved_adif_x,
            n_processed_records=0,
            last_poll_utc="",
        )

    if state_dx.adif_file != resolved_adif_x:
        state_dx.adif_file = resolved_adif_x
        state_dx.n_processed_records = 0

    return state_dx


def save_state(state_dx: WSJTXStateDX) -> None:
    _write_json_x(STATE_PATH, asdict(state_dx))


# ============================================================
# CONTACT STORAGE
# ============================================================

def load_contacts_lx() -> list[dict[str, Any]]:
    return _load_json_list_x(CONTACTS_PATH)


def save_contacts_lx(contacts_lx: list[dict[str, Any]]) -> None:
    _write_json_x(CONTACTS_PATH, contacts_lx)


def _contact_key_x(contact_dx: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        _normalize_plain_str(contact_dx.get("session_id")),
        _normalize_upper_str(contact_dx.get("operator")),
        _normalize_upper_str(contact_dx.get("call")),
        _normalize_upper_str(contact_dx.get("band")),
        _normalize_upper_str(contact_dx.get("mode")),
        _normalize_plain_str(contact_dx.get("timestamp_utc")),
    )


def build_existing_contact_keys_sx(contacts_lx: list[dict[str, Any]]) -> set[tuple[str, str, str, str, str, str]]:
    return {_contact_key_x(contact_dx) for contact_dx in contacts_lx}


# ============================================================
# IMPORT LOGIC
# ============================================================

def record_to_contact_dx(
    record_dx: dict[str, str],
    cfg_dx: dict[str, Any],
) -> dict[str, Any] | None:
    session_dx = get_current_session()

    if session_dx is None:
        print("SKIP: no current session")
        return None

    if session_dx.status != "active":
        print(f"SKIP: session not active ({session_dx.status})")
        return None

    operator_x = extract_operator_from_record(record_dx, cfg_dx)
    park_x = extract_park_from_record(record_dx, cfg_dx)
    call_x = _normalize_upper_str(record_dx.get("CALL"))
    band_x = _normalize_upper_str(record_dx.get("BAND"))
    mode_x = _normalize_upper_str(record_dx.get("SUBMODE") or record_dx.get("MODE"))
    timestamp_utc_x = extract_timestamp_utc_from_record(record_dx)

    print("---- WSJT-X RECORD CHECK ----")
    print(f"session park: {session_dx.park_id}")
    print(f"session operators: {session_dx.operators_present_lx}")
    print(f"record operator: {operator_x}")
    print(f"record park: {park_x}")
    print(f"call: {call_x}")
    print(f"band: {band_x}")
    print(f"mode: {mode_x}")
    print(f"timestamp_utc: {timestamp_utc_x}")

    if operator_x not in session_dx.operators_present_lx:
        print("SKIP: operator mismatch")
        return None

    if park_x != session_dx.park_id:
        print("SKIP: park mismatch")
        return None

    rst_sent_x = _normalize_plain_str(record_dx.get("RST_SENT") or record_dx.get("SRX_STRING"))
    rst_rcvd_x = _normalize_plain_str(record_dx.get("RST_RCVD") or record_dx.get("STX_STRING"))
    notes_x = _normalize_plain_str(record_dx.get("COMMENT"))

    if not call_x or not band_x or not mode_x or not timestamp_utc_x:
        print("SKIP: missing required fields")
        return None

    print("IMPORT: matched")

    return {
        "session_id": session_dx.session_id,
        "session_date_local": session_dx.session_date_local,
        "park_id": session_dx.park_id,
        "operator": operator_x,
        "operators_in_qso_lx": [operator_x],
        "call": call_x,
        "band": band_x,
        "mode": mode_x,
        "rst_sent": rst_sent_x,
        "rst_rcvd": rst_rcvd_x,
        "notes": notes_x,
        "timestamp_utc": timestamp_utc_x,
        "source": "WSJT-X",
    }

def import_records_lx(records_lx: list[str], cfg_dx: dict[str, Any]) -> int:
    contacts_lx = load_contacts_lx()
    existing_keys_sx = build_existing_contact_keys_sx(contacts_lx)
    imported_n_x = 0

    for record_text_x in records_lx:
        record_dx = parse_adif_record(record_text_x)
        contact_dx = record_to_contact_dx(record_dx, cfg_dx)

        if contact_dx is None:
            continue

        contact_key_x = _contact_key_x(contact_dx)
        if contact_key_x in existing_keys_sx:
            continue

        contacts_lx.append(contact_dx)
        existing_keys_sx.add(contact_key_x)
        imported_n_x += 1

    if imported_n_x > 0:
        save_contacts_lx(contacts_lx)

    return imported_n_x


# ============================================================
# POLLING
# ============================================================

def poll_once(cfg_dx: dict[str, Any]) -> dict[str, Any]:
    adif_path_x = resolve_adif_path(cfg_dx)
    state_dx = load_state(cfg_dx)

    if not adif_path_x.exists():
        raise FileNotFoundError(f"WSJT-X ADIF file not found: {adif_path_x}")

    text_x = adif_path_x.read_text(encoding="utf-8", errors="ignore")
    records_lx = extract_adif_records(text_x)

    if state_dx.n_processed_records > len(records_lx):
        state_dx.n_processed_records = 0

    new_records_lx = records_lx[state_dx.n_processed_records :]
    imported_n_x = import_records_lx(new_records_lx, cfg_dx)

    state_dx.n_processed_records = len(records_lx)
    state_dx.last_poll_utc = _utc_now_iso_x()
    save_state(state_dx)

    return {
        "records_seen": len(records_lx),
        "records_checked": len(new_records_lx),
        "contacts_imported": imported_n_x,
        "last_poll_utc": state_dx.last_poll_utc,
    }


def run_service_loop(cfg_dx: dict[str, Any] | None = None) -> None:
    cfg_dx = cfg_dx or load_config()

    while True:
        result_dx = poll_once(cfg_dx)
        print(
            f"[{result_dx['last_poll_utc']}] "
            f"checked={result_dx['records_checked']} "
            f"imported={result_dx['contacts_imported']} "
            f"total_seen={result_dx['records_seen']}"
        )
        time.sleep(cfg_dx["poll_seconds"])

