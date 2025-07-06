"""
Abstract away GPIO so desktop-development works without HW.
"""
import sys, os
try:
    from gpiozero import LED, Button, Device
    if not (sys.platform.startswith("linux") and os.path.exists("/proc/cpuinfo")):
        from gpiozero.pins.mock import MockFactory
        Device.pin_factory = MockFactory()
except ImportError:      # gpiozero missing
    class _Dummy:
        def __getattr__(self,*_): return lambda *a,**k: None
        is_active = False
    LED = Button = _Dummy    # type: ignore

red_led, pedal = LED(17), Button(27)     # BCM pins
