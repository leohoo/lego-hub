import asyncio
from bleak import BleakClient, BleakScanner
from lego_message import LegoMessage
from message_header import MessageType
from io_device_type import IODeviceType

LEGO_MANUFACTURER_ID = 0x0397
LEGO_SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"
LEGO_CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"

# Hub property IDs
HUB_PROPERTIES = {
    0x01: "name",
    0x03: "firmware_version",
    0x04: "hardware_version",
    0x06: "battery",
    0x08: "manufacturer",
}


class LegoHub:
    """Unified class for LEGO Hub communication."""

    def __init__(self):
        self.client = None
        self.address = None
        self.name = None
        self.properties = {}
        self.attached_io = {}
        self._notification_handlers = []
        self._encoder_value = None

    @staticmethod
    async def scan(timeout=5):
        """Scan for LEGO hubs. Returns list of (address, name) tuples."""
        found = []
        seen = set()

        def callback(device, adv_data):
            if LEGO_MANUFACTURER_ID in adv_data.manufacturer_data:
                if device.address not in seen:
                    seen.add(device.address)
                    found.append((device.address, device.name or "Unknown"))

        scanner = BleakScanner(callback)
        async with scanner:
            await asyncio.sleep(timeout)
        return found

    async def connect(self, address, calibrate_steering=False):
        """Connect to a hub by address."""
        self.address = address
        self.client = BleakClient(address)
        await self.client.connect()

        if not self.client.is_connected:
            raise ConnectionError(f"Failed to connect to {address}")

        # Set up notification handler
        await self.client.start_notify(
            LEGO_CHARACTERISTIC_UUID, self._handle_notification
        )

        # Query hub properties
        await self._query_properties()

        # Wait for attached IO notifications
        await asyncio.sleep(0.3)

        # Auto-calibrate steering if requested
        if calibrate_steering:
            await self.calibrate_steering()

        return self

    async def disconnect(self):
        """Disconnect from the hub."""
        if self.client and self.client.is_connected:
            await self.client.stop_notify(LEGO_CHARACTERISTIC_UUID)
            await self.client.disconnect()
        self.client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    def _handle_notification(self, sender, data):
        """Handle incoming notifications from the hub."""
        try:
            msg = LegoMessage.from_bytes(data)

            if msg.header.message_type == MessageType.HUB_PROPERTIES:
                self._handle_property_response(msg.payload)
            elif msg.header.message_type == MessageType.HUB_ATTACHED_IO:
                self._handle_attached_io(msg.payload)
            elif msg.header.message_type == MessageType.PORT_VALUE_SINGLE:
                self._handle_port_value(msg.payload)

            for handler in self._notification_handlers:
                handler(msg)
        except Exception:
            pass

    def _handle_port_value(self, payload):
        """Handle port value update (encoder position)."""
        if len(payload) >= 5:
            port = payload[0]
            value = int.from_bytes(payload[1:5], "little", signed=True)
            if port == 52:  # Steering port
                self._encoder_value = value

    def _handle_property_response(self, payload):
        """Parse hub property response."""
        prop_id = payload[0]
        value = payload[2:]  # Skip prop_id and operation byte

        if prop_id in (0x03, 0x04):  # Version
            self.properties[HUB_PROPERTIES.get(prop_id, prop_id)] = self._parse_version(value)
        elif prop_id == 0x06:  # Battery
            self.properties["battery"] = value[0]
        elif prop_id in (0x01, 0x08):  # String
            decoded = value.decode("utf-8", errors="replace").strip()
            self.properties[HUB_PROPERTIES.get(prop_id, prop_id)] = decoded
            if prop_id == 0x01:
                self.name = decoded

    def _handle_attached_io(self, payload):
        """Parse attached IO notification."""
        port_id = payload[0]
        event = payload[1]

        if event == 0x00:  # Detached
            self.attached_io.pop(port_id, None)
        elif event == 0x01 and len(payload) >= 4:  # Attached
            io_type = int.from_bytes(payload[2:4], "little")
            try:
                io_name = IODeviceType(io_type).name
            except ValueError:
                io_name = f"UNKNOWN_0x{io_type:04x}"
            self.attached_io[port_id] = io_name

    @staticmethod
    def _parse_version(data):
        """Parse LEGO version format."""
        if len(data) < 4:
            return data.hex()
        return f"{data[3] >> 4}.{data[3] & 0x0f}.{data[2]:02d}.{(data[1] << 8) | data[0]:04d}"

    async def _query_properties(self):
        """Query all hub properties."""
        for prop_id in HUB_PROPERTIES:
            cmd = LegoMessage(MessageType.HUB_PROPERTIES, bytearray([prop_id, 0x05]))
            await self._send(cmd.to_bytes())
            await asyncio.sleep(0.05)

    async def _send(self, data):
        """Send raw bytes to the hub."""
        if not self.client or not self.client.is_connected:
            raise ConnectionError("Not connected to hub")
        await self.client.write_gatt_char(LEGO_CHARACTERISTIC_UUID, data)

    # -------------------------------------------------------------------------
    # Motor Control - Technic Move Hub uses combined port 0x36 (54)
    # -------------------------------------------------------------------------

    # Current state for combined command
    _current_speed = 0
    _current_steering = 0
    _current_lights = 0

    async def calibrate_steering(self):
        """
        Calibrate steering using Technic Move Hub built-in calibration.
        Must be called before steering will work correctly.
        """
        port = 0x36  # Combined control port (54 decimal)

        # Calibration command 1: start calibration (0x10)
        cal1 = bytearray([0x0d, 0x00, 0x81, port, 0x11, 0x51, 0x00, 0x03, 0x00, 0x00, 0x00, 0x10, 0x00])
        await self._send(cal1)
        await asyncio.sleep(2.0)  # Wait for steering to find center

        # Calibration command 2: end calibration (0x08)
        cal2 = bytearray([0x0d, 0x00, 0x81, port, 0x11, 0x51, 0x00, 0x03, 0x00, 0x00, 0x00, 0x08, 0x00])
        await self._send(cal2)
        await asyncio.sleep(0.5)

        # Reset state and wait for hub to be ready
        self._current_speed = 0
        self._current_steering = 0
        self._current_lights = 0
        await asyncio.sleep(0.3)

    async def _send_drive_command(self, speed=None, steering=None, lights=None):
        """
        Send combined drive command to Technic Move Hub.
        Uses port 0x36 with mode 0x03 for combined control.
        """
        if speed is not None:
            self._current_speed = max(-100, min(100, int(speed)))
        if steering is not None:
            self._current_steering = max(-100, min(100, int(steering)))
        if lights is not None:
            self._current_lights = max(0, min(100, int(lights)))

        port = 0x36
        speed_byte = self._current_speed & 0xFF
        steer_byte = self._current_steering & 0xFF
        lights_byte = self._current_lights & 0xFF

        cmd = bytearray([
            0x0d, 0x00, 0x81, port, 0x11, 0x51, 0x00, 0x03,
            0x00, speed_byte, steer_byte, lights_byte, 0x00
        ])
        await self._send(cmd)

    async def drive(self, speed):
        """
        Drive forward/backward.
        speed: -100 (full reverse) to 100 (full forward)
        """
        await self._send_drive_command(speed=speed)

    async def steer(self, angle):
        """
        Steer left/right.
        angle: -100 (full left) to 100 (full right)

        The steering value is continuous:
        - Negative = steer left
        - Positive = steer right
        - 0 = return to center
        """
        await self._send_drive_command(steering=angle)

    async def stop(self):
        """Stop all motors (float/coast)."""
        await self._send_drive_command(speed=0, steering=0)

    async def brake(self):
        """Brake all motors (quick stop)."""
        # Send brake (127) to individual drive motor ports
        for port in [50, 51]:  # Left and right drive motors
            cmd = bytearray([0x08, 0x00, 0x81, port, 0x11, 0x51, 0x00, 127])
            await self._send(cmd)
        self._current_speed = 0
        self._current_steering = 0

    async def release_brake(self):
        """Release brake on drive motors (coast)."""
        # Send coast (0) to individual drive motor ports
        for port in [50, 51]:
            cmd = bytearray([0x08, 0x00, 0x81, port, 0x11, 0x51, 0x00, 0])
            await self._send(cmd)

    async def set_lights(self, brightness):
        """
        Set lights brightness.
        brightness: 0 (off) to 100 (full)

        Sends both direct port command (for non-calibrated mode) and
        combined command (for calibrated mode) to ensure lights work.
        """
        self._current_lights = max(0, min(100, int(brightness)))

        # Direct port 53 command (works without calibration)
        port = 53  # TECHNIC_MOVE_HUB_LIGHTS
        cmd = bytearray([0x08, 0x00, 0x81, port, 0x11, 0x51, 0x00, self._current_lights & 0xFF])
        await self._send(cmd)

        # Also send combined command (works after calibration)
        await self._send_drive_command(lights=self._current_lights)

    # -------------------------------------------------------------------------
    # Hub Actions
    # -------------------------------------------------------------------------

    async def shutdown(self):
        """Shutdown the hub."""
        cmd = LegoMessage(MessageType.HUB_ACTIONS, bytearray([0x01]))
        await self._send(cmd.to_bytes())

    async def get_status(self):
        """Get current hub status."""
        return {
            "name": self.name,
            "address": self.address,
            "battery": self.properties.get("battery"),
            "firmware": self.properties.get("firmware_version"),
            "hardware": self.properties.get("hardware_version"),
            "attached_io": dict(self.attached_io),
        }
