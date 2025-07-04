#!/usr/bin/env python3
"""
Launches TBAG UI in a frameless, full-screen window.
"""
import webview, os, time

# wait until gunicorn is listening (max 10 s)
for _ in range(20):
    try:
        from urllib.request import urlopen
        urlopen("http://127.0.0.1:8000", timeout=1).close()
        break
    except Exception:
        time.sleep(0.5)

webview.create_window(
    title="Thermal Battery Assembly",
    url="http://127.0.0.1:8000",
    fullscreen=True,
    frameless=True,
)
webview.start()
