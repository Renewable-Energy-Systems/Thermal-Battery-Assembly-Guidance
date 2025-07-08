"""
Central bootstrap – nothing but wiring.
Run with:  python app.py
"""

from flask import Flask
from tbag import config, db
from tbag.blueprints import kiosk, admin, projects, logs

db.init()                             # ensure tables exist

app = Flask(__name__,
            template_folder="templates",
            static_folder="static")
app.secret_key = config.SECRET

# register blueprints
app.register_blueprint(kiosk.bp)
app.register_blueprint(admin.bp , url_prefix="/admin")
app.register_blueprint(projects.bp)
app.register_blueprint(logs.bp)

if __name__ == "__main__":               # dev; prod → gunicorn
    app.run(host="0.0.0.0", port=8000, debug=False)
