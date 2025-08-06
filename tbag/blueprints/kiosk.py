"""
tbag.blueprints.kiosk
─────────────────────
Shop-floor runtime.

• Claims sessions from the queue and guides the operator step-by-step.  
• **Before every run** forces *all* LED pins low – even if another
  process has them locked – then keeps exactly one LED on (current
  component).  
• Frees every line at start / finish / abort, so no stale exports linger.  
• Records NEXT / FINISH / ABORT in the database + event-log.
"""

from __future__ import annotations

import datetime
import sqlite3
import time
from typing import Dict, Optional

from flask import Blueprint, abort, jsonify, render_template, request

from ..config import DEVICE_ID
from ..db import DB_FILE, log
from ..gpio import LED, Button                        # mocked on non-Pi hosts
from ..helpers.components import ALLOWED_GPIO_PINS, load_component
from ..helpers.projects import load_config

# ── try direct gpiod access (preferred) ───────────────────────────────
try:
    import gpiod  # type: ignore
    _HAS_GPIOD = True
except ImportError:
    _HAS_GPIOD = False
    print("[INFO] python3-gpiod not found; falling back to gpiozero reset")

# ────────────────────────── GPIO helpers ──────────────────────────────
_led_cache: Dict[int, LED] = {}      # lazy, 1 LED object per *used* pin
_current_pin: Optional[int] = None   # LED that is currently ON


def _led(pin: int) -> LED:
    """Return a cached LED object for *pin* (create on first use)."""
    if pin not in _led_cache:
        _led_cache[pin] = LED(pin)
    return _led_cache[pin]


def _activate_led(pin: Optional[int]) -> None:
    """
    Switch on *pin* and switch off/close the previously-active LED.
    Pass ``None`` to simply turn everything off.
    """
    global _current_pin

    if pin == _current_pin:
        return  # nothing to do

    # ── turn previous off ──────────────────────────────────────────
    if _current_pin is not None:
        try:
            _led(_current_pin).off()
        finally:
            _led(_current_pin).close()
            _led_cache.pop(_current_pin, None)

    _current_pin = None  # reset even if new pin fails

    # ── turn new one on ────────────────────────────────────────────
    if pin is not None:
        try:
            _led(pin).on()
            _current_pin = pin
        except Exception as exc:     # never crash the API
            print(f"[WARN] cannot switch LED on GPIO {pin}: {exc}", flush=True)
            try:
                _led(pin).close()
            finally:
                _led_cache.pop(pin, None)


def _reset_all_leds() -> None:
    """
    Force every *allowed* GPIO line low and release it – even if another
    userspace process owns the pin.

    Preferred path: use `gpiod` (GPIO character device).  
    Fallback: use gpiozero’s LED wrapper (may fail if line busy).
    """
    for pin in ALLOWED_GPIO_PINS:
        # ── gpiod (steals the line) ───────────────────────────────
        if _HAS_GPIOD:
            try:
                chip = gpiod.Chip("gpiochip0")
                line = chip.get_line(pin)
                line.request(
                    consumer="tbag-force-reset",
                    type=gpiod.LINE_REQ_DIR_OUT,
                    default_vals=[0],   # drive LOW immediately
                )
                time.sleep(0.005)       # 5 ms – let the LED discharge
            except Exception as exc:
                # fall through to gpiozero attempt
                print(f"[WARN] gpiod reset failed for GPIO {pin}: {exc}",
                      flush=True)
            finally:
                try:
                    line.release()
                except Exception:
                    pass
                try:
                    chip.close()
                except Exception:
                    pass

        # ── gpiozero fallback ─────────────────────────────────────
        try:
            led = LED(pin)
            led.off()
        except Exception as exc:
            print(f"[WARN] gpiozero reset failed for GPIO {pin}: {exc}",
                  flush=True)
        finally:
            try:
                led.close()
            except Exception:
                pass
            _led_cache.pop(pin, None)

    global _current_pin
    _current_pin = None


# ─────────────────────────── Flask BP ─────────────────────────────────
bp = Blueprint("kiosk", __name__)
pedal = Button(20) if hasattr(Button, "__call__") else Button()   # mock-safe

# ── UI entry point ────────────────────────────────────────────────────
@bp.route("/")
def index():
    return render_template("index.html")


# ── PENDING QUEUE feed ────────────────────────────────────────────────
@bp.get("/api/pending")
def pending():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT session_id,project,stack_id,operator,ts_created "
            "FROM runs WHERE status='pending' ORDER BY ts_created"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── CLAIM oldest pending job ──────────────────────────────────────────
@bp.post("/api/claim")
def claim():
    sid = (request.json or {}).get("session_id")
    if not sid:
        abort(400, "session_id missing")

    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        run = c.execute(
            """
            UPDATE runs
               SET status     = 'active',
                   ts_started = ?,
                   device     = ?
             WHERE session_id = ? AND status = 'pending'
            RETURNING *
            """,
            (datetime.datetime.now().isoformat(timespec="seconds"),
             DEVICE_ID,
             sid),
        ).fetchone()

    if run is None:
        abort(409, "session already claimed or not found")

    _reset_all_leds()                          # ⇠ force-clean GPIO state
    cfg = load_config(run["project"]) or {"sequence": []}

    return jsonify(status="claimed",
                   session=dict(run),
                   sequence=cfg["sequence"])


# ── PROGRESS / FINISH / ABORT ─────────────────────────────────────────
@bp.post("/api/progress")
def progress():
    """
    JS calls:
      • next   → {action:'next',   component:'anode', session_id:…}
      • finish → {action:'finish', …}
      • abort  → {action:'abort',  step:4,           …}
    """
    data = request.get_json(force=True)
    sid  = data["session_id"]
    act  = data["action"]
    now  = datetime.datetime.now().isoformat(timespec="seconds")

    # ── NEXT ──────────────────────────────────────────────────────────
    if act == "next":
        comp_id = data.get("component")
        if comp_id:                             # look-up GPIO pin
            comp = load_component(comp_id)
            if comp and comp.get("gpio") not in (None, ""):
                try:
                    _activate_led(int(comp["gpio"]))
                except ValueError:
                    print(f"[WARN] non-numeric GPIO in {comp_id}", flush=True)

        log("next_pressed", {"session_id": sid, "component": comp_id})
        return jsonify(status="ok")

    # ── FINISH / ABORT → update DB first ─────────────────────────────
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()

        if act == "finish":
            cur.execute(
                """
                UPDATE runs
                   SET status      = 'finished',
                       ts_finished = ?
                 WHERE session_id  = ? AND status = 'active'
                """,
                (now, sid),
            )
        elif act == "abort":
            cur.execute(
                """
                UPDATE runs
                   SET status        = 'aborted',
                       ts_finished   = ?,
                       interrupted_at= ?
                 WHERE session_id    = ? AND status = 'active'
                """,
                (now, data.get("step"), sid),
            )

        conn.commit()

    _reset_all_leds()                           # ⇠ off after run end

    if act == "finish":
        log("session_end",   {"session_id": sid})
    elif act == "abort":
        log("session_abort", {"session_id": sid, "step": data.get("step")})

    return jsonify(status=act)


# ── SUMMARY page ──────────────────────────────────────────────────────
@bp.route("/session/<sid>")
def session_overview(sid: str):
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        run = c.execute(
            "SELECT * FROM runs WHERE session_id = ?", (sid,)
        ).fetchone()

    if run is None:
        abort(404, "session not found")

    cfg = load_config(run["project"]) or {"sequence": []}
    return render_template("summary.html",
                           run=run,
                           total_steps=len(cfg["sequence"]))


# ── tiny helper for the foot-pedal ────────────────────────────────────
@bp.get("/pedal")
def pedal_state():
    return jsonify(pressed=bool(getattr(pedal, "is_active", False)))
