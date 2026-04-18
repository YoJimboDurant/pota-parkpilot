from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for, send_file, flash, jsonify
from collections import Counter

from parkpilot.utils.adif import (
    export_all_adif_for_session,
    export_adif_for_session,
    get_session_operators,
)

from parkpilot.core.session_manager import get_current_session

from parkpilot.core.session_manager import (
    close_current_session,
    get_current_session,
    set_active_operator,
    set_last_mode,
    set_last_band,
    start_or_resume_session,
)

# ============================================================
# PATHS
# ============================================================

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "parkpilot_config.json"


# ============================================================
# CONFIG
# ============================================================

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fx:
        cfg_dx = json.load(fx)

    cfg_dx["operators"] = [op.upper().strip() for op in cfg_dx.get("operators", [])]
    return cfg_dx


# ============================================================
# DUPLICATE CHECKS
# ============================================================

def build_contact_dup_key_x(contact_dx: dict) -> tuple[str, str, str, str, str, str]:
    timestamp_x = str(contact_dx.get("timestamp_utc", "")).strip()
    utc_date_x = timestamp_x[:10] if len(timestamp_x) >= 10 else ""

    park_x = str(
        contact_dx.get("park_id", contact_dx.get("park", ""))
    ).upper().strip()

    return (
        str(contact_dx.get("operator", "")).upper().strip(),
        str(contact_dx.get("call", "")).upper().strip(),
        str(contact_dx.get("band", "")).upper().strip(),
        park_x,
        str(contact_dx.get("mode", "")).upper().strip(),
        utc_date_x,
    )


# ============================================================
# COUNTER FOR QSOs
# ============================================================

def build_session_summary_dx(session_id_x: str) -> dict:
    contacts_path_x = PROJECT_ROOT / "data" / "sessions" / "contacts.json"

    if not contacts_path_x.exists():
        return {
            "total_qsos": 0,
            "by_operator_dx": {},
            "by_mode_dx": {},
            "by_operator_mode_dx": {},
        }

    with open(contacts_path_x, "r", encoding="utf-8") as fx:
        raw_x = fx.read().strip()

    contacts_lx = json.loads(raw_x) if raw_x else []

    session_contacts_lx = [
        contact_dx
        for contact_dx in contacts_lx
        if contact_dx.get("session_id") == session_id_x
    ]

    total_qsos_x = len(session_contacts_lx)
    by_operator_cx = Counter()
    by_mode_cx = Counter()
    by_operator_mode_dx: dict[str, Counter] = {}

    for contact_dx in session_contacts_lx:
        mode_x = str(contact_dx.get("mode", "")).upper().strip()
        by_mode_cx[mode_x] += 1

        operators_in_qso_lx = contact_dx.get("operators_in_qso_lx", [])
        if not operators_in_qso_lx:
            operator_x = str(contact_dx.get("operator", "")).upper().strip()
            if operator_x:
                operators_in_qso_lx = [operator_x]

        for operator_x in operators_in_qso_lx:
            operator_clean_x = str(operator_x).upper().strip()
            if not operator_clean_x:
                continue

            by_operator_cx[operator_clean_x] += 1

            if operator_clean_x not in by_operator_mode_dx:
                by_operator_mode_dx[operator_clean_x] = Counter()

            by_operator_mode_dx[operator_clean_x][mode_x] += 1

    return {
        "total_qsos": total_qsos_x,
        "by_operator_dx": dict(sorted(by_operator_cx.items())),
        "by_mode_dx": dict(sorted(by_mode_cx.items())),
        "by_operator_mode_dx": {
            operator_x: dict(sorted(counter_x.items()))
            for operator_x, counter_x in sorted(by_operator_mode_dx.items())
        },
    }


def load_all_contacts_lx() -> list[dict]:
    contacts_path_x = PROJECT_ROOT / "data" / "sessions" / "contacts.json"

    if not contacts_path_x.exists():
        return []

    with open(contacts_path_x, "r", encoding="utf-8") as fx:
        raw_x = fx.read().strip()

    return json.loads(raw_x) if raw_x else []


def build_session_status_dx() -> dict:
    session_dx = get_current_session()

    if session_dx is None:
        return {
            "has_active_session": False,
            "session_id": "",
            "park_id": "",
            "active_operator": "",
            "total_qsos": 0,
            "last_contact_ts": "",
            "status_token": "no-session",
        }

    contacts_lx = load_all_contacts_lx()
    session_contacts_lx = [
        contact_dx
        for contact_dx in contacts_lx
        if contact_dx.get("session_id") == session_dx.session_id
    ]

    total_qsos_x = len(session_contacts_lx)

    if session_contacts_lx:
        last_contact_ts_x = max(
            str(contact_dx.get("timestamp_utc", "")).strip()
            for contact_dx in session_contacts_lx
        )
    else:
        last_contact_ts_x = ""

    status_token_x = "|".join([
        str(session_dx.session_id),
        str(session_dx.status),
        str(session_dx.active_operator),
        str(total_qsos_x),
        str(last_contact_ts_x),
    ])

    return {
        "has_active_session": True,
        "session_id": session_dx.session_id,
        "park_id": session_dx.park_id,
        "active_operator": session_dx.active_operator,
        "total_qsos": total_qsos_x,
        "last_contact_ts": last_contact_ts_x,
        "status_token": status_token_x,
    }


# ============================================================
# APP FACTORY
# ============================================================

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
    )
    app.config["SECRET_KEY"] = "parkpilot-dev-key"

    @app.route("/", methods=["GET"])
    def index():
        cfg_dx = load_config()
        session_dx = get_current_session()

        exportable_operators_lx = []
        summary_dx = {
            "total_qsos": 0,
            "by_operator_dx": {},
            "by_mode_dx": {},
            "by_operator_mode_dx": {},
        }

        if session_dx is not None:
            exportable_operators_lx = get_session_operators(session_dx.session_id)
            summary_dx = build_session_summary_dx(session_dx.session_id)

        status_dx = build_session_status_dx()

        return render_template(
            "index.html",
            cfg_dx=cfg_dx,
            session_dx=session_dx,
            exportable_operators_lx=exportable_operators_lx,
            summary_dx=summary_dx,
            status_dx=status_dx,
        )

    @app.route("/session/start", methods=["POST"])
    def session_start():
        park_id_x = request.form.get("park_id", "").upper().strip()

        operators_present_lx = request.form.getlist("operators_present")
        operators_present_lx = [op.upper().strip() for op in operators_present_lx]

        active_operator_x = request.form.get("active_operator", "").upper().strip()

        if not active_operator_x and operators_present_lx:
            active_operator_x = operators_present_lx[0]

        start_or_resume_session(
            park_id_x=park_id_x,
            operators_present_lx=operators_present_lx,
            active_operator_x=active_operator_x,
        )

        return redirect(url_for("index"))

    @app.route("/session/set_active_operator", methods=["POST"])
    def session_set_active_operator():
        active_operator_x = request.form.get("active_operator", "").upper().strip()
        set_active_operator(active_operator_x)
        return redirect(url_for("index"))

    @app.route("/session/close", methods=["POST"])
    def session_close():
        close_current_session()
        return redirect(url_for("index"))

    @app.route("/contact/manual", methods=["POST"])
    def add_manual_contact():
        session_dx = get_current_session()

        if session_dx is None:
            return redirect(url_for("index"))

        call_x = request.form.get("call", "").upper().strip()
        mode_x = request.form.get("mode", "CW").upper().strip()
        band_x = request.form.get("band", "20M").upper().strip()
        rst_sent_x = request.form.get("rst_sent", "599").strip()
        rst_rcvd_x = request.form.get("rst_rcvd", "599").strip()
        notes_x = request.form.get("notes", "").strip()

        set_last_mode(mode_x)
        set_last_band(band_x)

        operators_in_qso_lx = [
            op.upper().strip()
            for op in request.form.getlist("operators_in_qso")
            if op.strip()
        ]

        if not call_x:
            return redirect(url_for("index"))

        valid_operators_lx = session_dx.operators_present_lx
        operators_in_qso_lx = [
            op_x for op_x in valid_operators_lx
            if op_x in set(operators_in_qso_lx)
        ]

        if mode_x == "SSB":
            if not operators_in_qso_lx:
                operators_in_qso_lx = [session_dx.active_operator]
        else:
            operators_in_qso_lx = [session_dx.active_operator]

        contacts_path_x = PROJECT_ROOT / "data" / "sessions" / "contacts.json"

        if contacts_path_x.exists():
            with open(contacts_path_x, "r", encoding="utf-8") as fx:
                raw_x = fx.read().strip()
            contacts_lx = json.loads(raw_x) if raw_x else []
        else:
            contacts_lx = []

        contact_dx = {
            "session_id": session_dx.session_id,
            "session_date_local": session_dx.session_date_local,
            "park_id": session_dx.park_id,
            "operator": session_dx.active_operator,
            "operators_in_qso_lx": operators_in_qso_lx,
            "call": call_x,
            "band": band_x,
            "mode": mode_x,
            "rst_sent": rst_sent_x,
            "rst_rcvd": rst_rcvd_x,
            "notes": notes_x,
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        }

        new_dup_key_x = build_contact_dup_key_x(contact_dx)

        session_contacts_lx = [
            existing_dx
            for existing_dx in contacts_lx
            if str(existing_dx.get("session_id", "")).strip() == str(session_dx.session_id).strip()
        ]

        existing_dup_keys_x = {
            build_contact_dup_key_x(existing_dx)
            for existing_dx in session_contacts_lx
        }

        if new_dup_key_x in existing_dup_keys_x:
            flash("Duplicate contact ignored.", "warning")
            return redirect(url_for("index"))

        contacts_lx.append(contact_dx)

        with open(contacts_path_x, "w", encoding="utf-8") as fx:
            json.dump(contacts_lx, fx, indent=2)

        return redirect(url_for("index"))

    @app.route("/export/adif/current/all")
    def export_current_adif_all():
        session_dx = get_current_session()
        paths_lx = export_all_adif_for_session(session_dx.session_id)

        # For now just return first file (we’ll zip later)
        return send_file(paths_lx[0], as_attachment=True)

    @app.route("/export/adif/current/<operator_x>")
    def export_current_adif_operator(operator_x: str):
        session_dx = get_current_session()

        if session_dx is None:
            return redirect(url_for("index"))

        try:
            export_path_x = export_adif_for_session(
                session_id_x=session_dx.session_id,
                operator_x=operator_x,
            )
        except ValueError:
            flash(f"No contacts to export for {operator_x}.")
            return redirect(url_for("index"))

        return send_file(export_path_x, as_attachment=True)

    @app.route("/api/session_status", methods=["GET"])
    def api_session_status():
        return jsonify(build_session_status_dx())

    return app