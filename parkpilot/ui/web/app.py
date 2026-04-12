from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for

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

        return render_template(
            "index.html",
            cfg_dx=cfg_dx,
            session_dx=session_dx,
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

        contacts_lx.append(contact_dx)

        with open(contacts_path_x, "w", encoding="utf-8") as fx:
            json.dump(contacts_lx, fx, indent=2)

        return redirect(url_for("index"))

    return app