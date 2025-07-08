"""
Central bootstrap – nothing but wiring.
Run with:  python app.py
"""

from flask import Flask
from tbag import config, db
from tbag.blueprints import kiosk, admin, components, projects, logs   # ← added *components*

# ── ensure database schema exists ───────────────────────────────────
db.init()

# ── Flask app ───────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
app.secret_key = config.SECRET

# ── register blueprints ─────────────────────────────────────────────
app.register_blueprint(kiosk.bp)
app.register_blueprint(admin.bp,       url_prefix="/admin")
app.register_blueprint(components.bp)                    # ← NEW
app.register_blueprint(projects.bp)
app.register_blueprint(logs.bp)

# ── dev server (prod → gunicorn) ────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
