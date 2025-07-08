"""
tbag.gpio  –  safe GPIO helpers
--------------------------------
• On a real Pi      → real gpiozero LED/Button.
• Else (PC/CI)      → no-op mocks that behave like the real classes.
"""
from __future__ import annotations
import os, sys

try:
    from gpiozero import Device, LED, Button  # type: ignore
    if not (
        sys.platform.startswith("linux")
        and os.path.exists("/sys/firmware/devicetree/base/model")
    ):
        raise RuntimeError("not-pi")          # force mock on non-Pi
except Exception:                             # import error or forced mock
    class _Mock:
        """drop-in replacement for gpiozero devices"""
        is_active = False

        # accept any constructor signature
        def __init__(self, *_, **__):
            pass

        # any attribute access returns a do-nothing function
        def __getattr__(self, _):
            return lambda *a, **k: None

    LED = Button = _Mock                      # type: ignore
else:
    # real Pi, but allow override
    if os.environ.get("TBAG_GPIO_MOCK"):
        from gpiozero.pins.mock import MockFactory  # type: ignore
        Device.pin_factory = MockFactory()
