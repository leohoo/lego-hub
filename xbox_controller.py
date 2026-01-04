"""
Xbox Controller support for macOS using IOKit HID.

Runs CFRunLoop on the main thread to handle HID events.
"""

import ctypes
from ctypes import c_void_p, c_int32, c_uint32, c_int64, c_char_p, CFUNCTYPE, byref
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

# Load frameworks
iokit = ctypes.CDLL('/System/Library/Frameworks/IOKit.framework/IOKit')
cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')

# Constants
XBOX_VENDOR_ID = 0x045E
XBOX_PRODUCT_ID = 0x0B13
kIOHIDOptionsTypeSeizeDevice = 1
kCFRunLoopDefaultMode = c_void_p.in_dll(cf, 'kCFRunLoopDefaultMode')

# HID Usage Pages
kHIDPage_GenericDesktop = 0x01
kHIDPage_Simulation = 0x02
kHIDPage_Button = 0x09

# CoreFoundation types
cf.CFRunLoopGetCurrent.restype = c_void_p
cf.CFRunLoopRunInMode.argtypes = [c_void_p, ctypes.c_double, ctypes.c_bool]
cf.CFRunLoopRunInMode.restype = c_int32

cf.CFNumberCreate.argtypes = [c_void_p, c_int32, c_void_p]
cf.CFNumberCreate.restype = c_void_p
cf.CFDictionaryCreateMutable.argtypes = [c_void_p, c_int32, c_void_p, c_void_p]
cf.CFDictionaryCreateMutable.restype = c_void_p
cf.CFDictionarySetValue.argtypes = [c_void_p, c_void_p, c_void_p]
cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
cf.CFStringCreateWithCString.restype = c_void_p

cf.CFSetGetCount.argtypes = [c_void_p]
cf.CFSetGetCount.restype = c_int32
cf.CFSetGetValues.argtypes = [c_void_p, c_void_p]

# IOKit HID
iokit.IOHIDManagerCreate.argtypes = [c_void_p, c_uint32]
iokit.IOHIDManagerCreate.restype = c_void_p
iokit.IOHIDManagerSetDeviceMatching.argtypes = [c_void_p, c_void_p]
iokit.IOHIDManagerScheduleWithRunLoop.argtypes = [c_void_p, c_void_p, c_void_p]
iokit.IOHIDManagerOpen.argtypes = [c_void_p, c_uint32]
iokit.IOHIDManagerOpen.restype = c_int32
iokit.IOHIDManagerCopyDevices.argtypes = [c_void_p]
iokit.IOHIDManagerCopyDevices.restype = c_void_p

iokit.IOHIDDeviceScheduleWithRunLoop.argtypes = [c_void_p, c_void_p, c_void_p]
iokit.IOHIDDeviceOpen.argtypes = [c_void_p, c_uint32]
iokit.IOHIDDeviceOpen.restype = c_int32
iokit.IOHIDDeviceClose.argtypes = [c_void_p, c_uint32]
iokit.IOHIDDeviceClose.restype = c_int32
iokit.IOHIDDeviceRegisterInputValueCallback.argtypes = [c_void_p, c_void_p, c_void_p]
iokit.IOHIDManagerClose.argtypes = [c_void_p, c_uint32]
iokit.IOHIDManagerClose.restype = c_int32

iokit.IOHIDValueGetElement.argtypes = [c_void_p]
iokit.IOHIDValueGetElement.restype = c_void_p
iokit.IOHIDValueGetIntegerValue.argtypes = [c_void_p]
iokit.IOHIDValueGetIntegerValue.restype = c_int64
iokit.IOHIDElementGetUsagePage.argtypes = [c_void_p]
iokit.IOHIDElementGetUsagePage.restype = c_uint32
iokit.IOHIDElementGetUsage.argtypes = [c_void_p]
iokit.IOHIDElementGetUsage.restype = c_uint32

# Callback type
HIDCallback = CFUNCTYPE(None, c_void_p, c_int32, c_void_p, c_void_p)


class InputType(Enum):
    STICK_LEFT_X = 'left_stick_x'
    STICK_LEFT_Y = 'left_stick_y'
    STICK_RIGHT_X = 'right_stick_x'
    STICK_RIGHT_Y = 'right_stick_y'
    TRIGGER_LEFT = 'left_trigger'
    TRIGGER_RIGHT = 'right_trigger'
    BUTTON = 'button'


@dataclass
class ControllerEvent:
    input_type: InputType
    value: int
    pressed: bool = True


# Button mappings
BUTTON_NAMES = {
    1: 'A', 2: 'B', 4: 'X', 5: 'Y',
    7: 'LB', 8: 'RB',
    12: 'Start', 13: 'Xbox', 14: 'LS', 15: 'RS',
    16: 'Back'
}

# Axis mappings (page 0x01 - Generic Desktop)
STICK_MAP = {
    0x30: InputType.STICK_LEFT_X,
    0x31: InputType.STICK_LEFT_Y,
    0x32: InputType.STICK_RIGHT_X,
    0x33: InputType.STICK_RIGHT_Y,
}

# Trigger mappings (page 0x02 - Simulation)
TRIGGER_MAP = {
    0xc4: InputType.TRIGGER_RIGHT,
    0xc5: InputType.TRIGGER_LEFT,
}


class XboxController:
    """Xbox controller using IOKit HID - runs on main thread."""

    def __init__(self, on_event: Optional[Callable[[ControllerEvent], None]] = None):
        self.on_event = on_event
        self._manager = None
        self._device = None
        self._run_loop = None
        self._callback = HIDCallback(self._input_callback)

        # State tracking for deduplication
        self._last_values = {}

    def connect(self) -> bool:
        """Connect to Xbox controller. Returns True if found."""
        self._manager = iokit.IOHIDManagerCreate(None, 0)

        # Match Xbox controller
        vid = c_int32(XBOX_VENDOR_ID)
        pid = c_int32(XBOX_PRODUCT_ID)
        vid_cf = cf.CFNumberCreate(None, 3, byref(vid))
        pid_cf = cf.CFNumberCreate(None, 3, byref(pid))
        vid_key = cf.CFStringCreateWithCString(None, b"VendorID", 0)
        pid_key = cf.CFStringCreateWithCString(None, b"ProductID", 0)
        match_dict = cf.CFDictionaryCreateMutable(None, 2, None, None)
        cf.CFDictionarySetValue(match_dict, vid_key, vid_cf)
        cf.CFDictionarySetValue(match_dict, pid_key, pid_cf)

        iokit.IOHIDManagerSetDeviceMatching(self._manager, match_dict)

        # Schedule with run loop
        self._run_loop = cf.CFRunLoopGetCurrent()
        iokit.IOHIDManagerScheduleWithRunLoop(self._manager, self._run_loop, kCFRunLoopDefaultMode)

        # Open manager
        if iokit.IOHIDManagerOpen(self._manager, 0) != 0:
            return False

        # Get devices
        devices = iokit.IOHIDManagerCopyDevices(self._manager)
        if not devices:
            return False

        count = cf.CFSetGetCount(devices)
        if count == 0:
            return False

        # Get first device
        device_array = (c_void_p * count)()
        cf.CFSetGetValues(devices, ctypes.cast(device_array, c_void_p))
        self._device = device_array[0]

        # Open with exclusive access
        if iokit.IOHIDDeviceOpen(self._device, kIOHIDOptionsTypeSeizeDevice) != 0:
            return False

        # Schedule device and register callback
        iokit.IOHIDDeviceScheduleWithRunLoop(self._device, self._run_loop, kCFRunLoopDefaultMode)
        iokit.IOHIDDeviceRegisterInputValueCallback(self._device, self._callback, None)

        return True

    def poll(self, timeout: float = 0.01):
        """Poll for events. Call this repeatedly from your main loop."""
        cf.CFRunLoopRunInMode(kCFRunLoopDefaultMode, timeout, False)

    def disconnect(self):
        """Disconnect from the controller and release resources."""
        if self._device:
            iokit.IOHIDDeviceClose(self._device, 0)
            self._device = None
        if self._manager:
            iokit.IOHIDManagerClose(self._manager, 0)
            self._manager = None
        self._callback = None

    def _input_callback(self, context, result, sender, value):
        """HID input callback - fires on every input change."""
        element = iokit.IOHIDValueGetElement(value)
        usage_page = iokit.IOHIDElementGetUsagePage(element)
        usage = iokit.IOHIDElementGetUsage(element)
        int_value = iokit.IOHIDValueGetIntegerValue(value)

        event = None

        if usage_page == kHIDPage_Button:
            pressed = int_value != 0
            key = ('button', usage)
            if self._last_values.get(key) != pressed:
                self._last_values[key] = pressed
                event = ControllerEvent(InputType.BUTTON, usage, pressed)

        elif usage_page == kHIDPage_GenericDesktop and usage in STICK_MAP:
            input_type = STICK_MAP[usage]
            # Sticks: 0-65535 centered at 32768 -> -100 to 100
            normalized = int(((int_value - 32768) / 32768.0) * 100)
            # Apply deadzone
            if abs(normalized) < 15:
                normalized = 0
            # Invert Y axes
            if input_type in (InputType.STICK_LEFT_Y, InputType.STICK_RIGHT_Y):
                normalized = -normalized

            key = ('stick', usage)
            if self._last_values.get(key) != normalized:
                self._last_values[key] = normalized
                event = ControllerEvent(input_type, normalized)

        elif usage_page == kHIDPage_Simulation and usage in TRIGGER_MAP:
            input_type = TRIGGER_MAP[usage]
            # Triggers: 0-1023 -> 0-100
            normalized = int((int_value / 1023.0) * 100)

            key = ('trigger', usage)
            if self._last_values.get(key) != normalized:
                self._last_values[key] = normalized
                event = ControllerEvent(input_type, normalized)

        if event and self.on_event:
            self.on_event(event)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(line_buffering=True)

    def on_event(event: ControllerEvent):
        if event.input_type == InputType.BUTTON:
            name = BUTTON_NAMES.get(event.value, f"B{event.value}")
            print(f"Button {name} {'pressed' if event.pressed else 'released'}")
        else:
            print(f"{event.input_type.value}: {event.value}")

    print("Looking for Xbox controller...")
    controller = XboxController(on_event=on_event)

    if not controller.connect():
        print("No Xbox controller found. Make sure it's connected via Bluetooth.")
        sys.exit(1)

    print("Connected! Press buttons and move sticks. Ctrl+C to exit.\n")

    try:
        while True:
            controller.poll(0.1)
    except KeyboardInterrupt:
        print("\nDone.")
