"""
tbag.gpio  –  safe GPIO helpers
--------------------------------
Goal
~~~~
• On a *real* Raspberry Pi **with working permissions** we expose the real
  ``gpiozero`` classes (``LED`` / ``Button``).

• Everywhere else — laptop, CI, Docker, or even a Pi where the pins are
  already claimed / lack permissions — we **silently fall back** to no-op
  mocks that keep the public API but do nothing.

Behaviour switches automatically, but you can force mock mode via

    $ export TBAG_GPIO_MOCK=1

before starting the app.
"""
from __future__ import annotations

import os
import sys

__all__ = ["LED", "Button", "is_real", "using_mock"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _running_on_pi() -> bool:
    """Cheap heuristic → True only on real Pi boards (any model)."""
    return (
        sys.platform.startswith("linux")
        and os.path.exists("/sys/firmware/devicetree/base/model")
    )


def _force_mock() -> bool:
    """Respect TBAG_GPIO_MOCK env-var for tests / CI."""
    return bool(os.environ.get("TBAG_GPIO_MOCK"))


def _install_mock() -> None:
    """Register dummy LED / Button classes in *this* module."""
    class _Mock:                                    # pylint: disable=too-few-public-methods
        """Drop-in replacement that silently swallows everything."""
        is_active = False

        def __init__(self, *_, **__):
            pass

        def __getattr__(self, _):                   # any attr → dummy fn
            return lambda *a, **k: None

        def close(self):                            # real gpiozero has it
            pass

        # helpful in logs / repr()
        def __repr__(self) -> str:                  # pragma: no cover
            return f"<MockGPIO 0x{id(self):x}>"

    globals()["LED"] = globals()["Button"] = _Mock  # type: ignore
    globals()["using_mock"] = True


# ---------------------------------------------------------------------------
# main logic
# ---------------------------------------------------------------------------

using_mock: bool = False            # exported flag

if _force_mock() or not _running_on_pi():
    # Obviously not a Pi, *or* forced mock ⇒ go mock immediately
    _install_mock()

else:
    # Likely a Pi – try to use real gpiozero but fall back gracefully
    try:
        from gpiozero import Device, LED, Button          # type: ignore
        from gpiozero.pins.mock import MockFactory        # type: ignore

        # Quick probe: claim an innocuous pin (BCM-4) to detect
        # “GPIO busy / no mem / no permission” before the app starts.
        try:
            _probe = LED(4)
            _probe.close()
        except Exception:
            # Something is wrong → switch the *entire* process to mocks
            Device.pin_factory = MockFactory()
            using_mock = True
        else:
            using_mock = False

    except Exception:
        # gpiozero isn’t importable at all ⇒ fall back
        _install_mock()


# ---------------------------------------------------------------------------
# convenience helpers
# ---------------------------------------------------------------------------

def is_real() -> bool:
    """Return *True* when the real GPIO driver is active (not mocked)."""
    return not using_mock
