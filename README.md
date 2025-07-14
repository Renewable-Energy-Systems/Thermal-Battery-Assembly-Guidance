# Thermal-Battery Assembly Guidance (**TBAG**)

End-to-end “shop-floor” guidance system for assembling molten-salt
thermal batteries.  
Runs on a **Raspberry Pi** inside the glove-box, drives coloured LEDs to
indicate the *current* component, accepts hands-free *Next / Abort*
commands via a USB foot-switch and records every session in an SQLite
log that supervisors can review from any browser.

```
               ┌──────────────┐
               │  Admin PC    │  http(s)://res-stack.weberq.in
               └──────────────┘
                       ▲
                       │ web UI + JSON
                       ▼
┌────────────┐  GPIO ┌─────────┐  USB HID ┌───────────┐
│  RPi 4     │──────▶│ coloured│◀─────────│ foot pedal│
│  (Gunicorn)│       │  LEDs   │           └───────────┘
└────────────┘       └─────────┘
```

---

## ✨  Key features
| Area | Highlights |
|------|------------|
| **Operator UI** | • Kiosk-style single page<br>• Live component preview + LED guidance<br>• Foot-switch (USB) = *space bar*<br>• Last-step review & summary |
| **Supervisor UI** | • Admin dashboard (sessions, projects, components)<br>• Live queue manager<br>• XLSX export |
| **Hardware** | • Any RPi (tested on 4 & 3B+)<br>• Simple 3 mm LEDs + 330 Ω resistors<br>• Optional industrial USB foot pedal |
| **Backend** | • Flask / Gunicorn<br>• SQLite DB (no server needed)<br>• REST-ish JSON endpoints |
| **Remote access** | • Cloudflare Tunnel recipe included *(optional)* |
| **Deployment** | • `systemd` service → auto-start & watchdog |

---

## 🛠️  Quick-start (dev / PC)

```bash
git clone https://github.com/Renewable-Energy-Systems/Thermal-Battery-Assembly-Guidance.git tbag
cd tbag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run
```

Browse to **http://localhost:5000** and start adding
**Projects → Components → Sessions**.

---

## 🐙  Production recipe (Raspberry Pi)

1. **Prepare OS & deps**

   ```bash
   sudo apt update && sudo apt install git python3-venv libgpiod2
   ```

2. **Clone + set-up venv**

   ```bash
   git clone https://github.com/Renewable-Energy-Systems/Thermal-Battery-Assembly-Guidance.git ~/ags
   cd ~/ags
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt gunicorn
   ```

3. **Create `systemd` unit**

   `/etc/systemd/system/tbag.service`

   ```ini
   [Unit]
   Description=TBAG Flask backend (Gunicorn)
   After=network.target

   [Service]
   User=pi
   WorkingDirectory=/home/pi/ags
   Environment="PATH=/home/pi/ags/.venv/bin"
   ExecStart=/home/pi/ags/.venv/bin/gunicorn -b 0.0.0.0:8000 \
             --workers 3 --timeout 90 app:app
   Restart=on-failure
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now tbag
   ```

4. **Wire LEDs**

   | GPIO | Colour | Component |
   |------|--------|-----------|
   | 17   | Red    | Anode     |
   |  4   | Blue   | Cathode   |
   | 25   | Green  | Electrolyte |
   | …    | …      | …         |

   *330 Ω resistor → LED → GND.  
   Pin numbers are configured per component in
   `components/&lt;cid&gt;/config.json`.*

5. **USB foot-switch**

   *Any* programmable HID pedal works.  
   Program it to emit a **space bar**:

   * short press &lt; 10 s → “Next / Review”  
   * long  press ≥ 10 s → “Force Stop”

6. **(Optional) expose over the internet**

   ```bash
   curl -L \
     https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb \
     -o cf.deb
   sudo apt install ./cf.deb
   sudo cloudflared tunnel login
   sudo cloudflared tunnel create res-stack
   sudo cloudflared tunnel route dns res-stack yoursub.weberq.in
   ```

   `/etc/cloudflared/config.yml`

   ```yaml
   tunnel: res-stack
   credentials-file: /home/pi/.cloudflared/res-stack.json

   ingress:
     - hostname: yoursub.weberq.in
       service: http://localhost:8000
     - service: http_status:404
   ```

   ```bash
   sudo systemctl enable --now cloudflared
   ```

---

## 📂  Project layout

```
ags/
├─ app.py                  ← Flask bootstrap
├─ tbag/
│  ├─ blueprints/          ← UI + API endpoints
│  ├─ helpers/             ← tiny pure-Python libs
│  ├─ gpio.py              ← LED / Button wrapper (mock-friendly)
│  ├─ db.py                ← SQLite migrations & helpers
│  └─ config.py            ← secrets, device ID, build stamp …
├─ components/             ← user-added component defs
├─ projects/               ← project JSONs (sequences)
├─ static/                 ← CSS / JS / logo
└─ templates/              ← Jinja2 pages
```

---

## 🔧  Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_ID` | `glovebox-pi` | Written into each DB record |
| `SECRET`    | generated UUID | Flask session key |
| `GPIOZERO_PIN_FACTORY` | `lgpio` | Use [`lgpio`](https://github.com/gpiozero/lgpio) backend (fast, no sudo) |

Define via `.env` or directly inside your `systemd` unit.

---

## 👟  Foot-switch logic (JS)

| Action | Condition | Key | Effect |
|--------|-----------|-----|--------|
| `NEXT / REVIEW` | press ≤ 10 s | **space** *keyup* | `/api/progress` `next` |
| `FORCE STOP`    | hold ≥ 10 s | **space** held   | Clicks *Stop* → `/api/progress` `abort` |

Implementation: [`static/script.js`](static/script.js) (v4.6).

---

## 🚑  Basic troubleshooting

| Symptom | Check |
|---------|-------|
| **LED stays on / GPIO busy** | `_reset_all_leds()` runs every step. Still stuck? `sudo lgpioreset`. |
| **Summary page 404** | Ensure `/api/progress` sends `"finish"` **before** redirect. |
| **Tunnel works but local 192.168 … preferred** | Operators bookmark `http://&lt;Pi-IP&gt;:8000`; public URL is fallback. |

---

## 📜  License

MIT © Renewable Energy Systems 2025 • Contributions welcome!

---

## Credits
Developed with ❤️ by [@kiranpranay](https://github.com/kiranpranay).  
Feel free to contribute or report issues!