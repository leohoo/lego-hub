# This script scans for BLE Lego Hub and processes advertisement data.
# https://lego.github.io/lego-ble-wireless-protocol-docs/index.html#advertising
# Manufacturer Data is interpreted as a dict by BleakScanner, value of the data starts from offet 4 (-4 to the table of the documentation)

import asyncio
from bleak import BleakScanner, BleakClient
from lego_message import LegoMessage
from message_header import MessageType
from io_device_type import IODeviceType

LEGO_MANUFACTURER_ID = 0x0397  # LEGO System A/S
LEGO_CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"

# Hub properties we want to query
HUB_PROPERTIES = {
    0x01: "Advertising Name",
    0x03: "Firmware Version",
    0x04: "Hardware Version",
    0x06: "Battery Voltage",
    0x08: "Manufacturer Name",
    0x0B: "System Type ID",
}

seen_devices = set()
found_devices = []  # Store devices to connect later

def advertisement_callback(device, advertisement_data):
    """Callback function to handle advertisement data."""
    # Check if this is a LEGO device by manufacturer ID
    if LEGO_MANUFACTURER_ID not in advertisement_data.manufacturer_data:
        return

    # Skip if we've already seen this device
    if device.address in seen_devices:
        return
    seen_devices.add(device.address)

    print(f"\n🔹 Device Found: {device.name or 'Unknown'} - {device.address}")
    found_devices.append(device)

    # Extract manufacturer data
    data = advertisement_data.manufacturer_data[LEGO_MANUFACTURER_ID]
    print(f"   Raw Data (Hex): {data.hex()}")

LEGO_SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"

def parse_version(data):
    """Parse LEGO version format (4 bytes)."""
    if len(data) < 4:
        return data.hex()
    # Format: major.minor.bugfix.build
    return f"{data[3] >> 4}.{data[3] & 0x0f}.{data[2]:02d}.{(data[1] << 8) | data[0]:04d}"

def parse_property_value(prop_id, data):
    """Parse property value based on its type."""
    if prop_id in (0x03, 0x04):  # Version fields
        return parse_version(data)
    elif prop_id == 0x06:  # Battery voltage (percentage)
        return f"{data[0]}%"
    elif prop_id in (0x01, 0x08):  # String fields
        return data.decode('utf-8', errors='replace')
    else:
        return data.hex()

async def get_hub_info(client):
    """Query hub properties and attached IO."""
    hub_info = {}
    attached_io = []

    # Set up notification handler to receive responses
    response_event = asyncio.Event()
    response_data = {}

    def notification_handler(sender, data):
        msg = LegoMessage.from_bytes(data)
        if msg.header.message_type == MessageType.HUB_PROPERTIES:
            prop_id = msg.payload[0]
            prop_value = msg.payload[2:]  # Skip property ID and operation
            response_data[prop_id] = prop_value
            response_event.set()
        elif msg.header.message_type == MessageType.HUB_ATTACHED_IO:
            port_id = msg.payload[0]
            event = msg.payload[1]
            if event == 0x01 and len(msg.payload) >= 4:  # Attached
                io_type = int.from_bytes(msg.payload[2:4], 'little')
                try:
                    io_name = IODeviceType(io_type).name
                except ValueError:
                    io_name = f"Unknown (0x{io_type:04x})"
                attached_io.append((port_id, io_name))

    await client.start_notify(LEGO_CHARACTERISTIC_UUID, notification_handler)

    # Query each hub property
    for prop_id, prop_name in HUB_PROPERTIES.items():
        response_event.clear()
        # Request property: [prop_id, 0x05 = request update]
        cmd = LegoMessage(MessageType.HUB_PROPERTIES, bytearray([prop_id, 0x05]))
        await client.write_gatt_char(LEGO_CHARACTERISTIC_UUID, cmd.to_bytes())
        try:
            await asyncio.wait_for(response_event.wait(), timeout=1.0)
            if prop_id in response_data:
                hub_info[prop_name] = parse_property_value(prop_id, response_data[prop_id])
        except asyncio.TimeoutError:
            pass

    # Wait a moment for attached IO notifications
    await asyncio.sleep(0.5)

    await client.stop_notify(LEGO_CHARACTERISTIC_UUID)
    return hub_info, attached_io

async def connect_and_query(device):
    """Connect to device and query its info."""
    print(f"\n📡 Connecting to {device.name}...")
    try:
        async with BleakClient(device.address) as client:
            if client.is_connected:
                print(f"   Connected!")
                hub_info, attached_io = await get_hub_info(client)

                print(f"\n   Hub Properties:")
                for name, value in hub_info.items():
                    print(f"   • {name}: {value}")

                if attached_io:
                    print(f"\n   Attached I/O Devices:")
                    for port_id, io_name in attached_io:
                        print(f"   • Port {port_id}: {io_name}")
    except Exception as e:
        print(f"   Connection failed: {e}")

async def scan_devices():
    """Scans for BLE devices using a callback function."""
    print("Scanning for LEGO devices (5 seconds)...")
    print("Make sure your hub is ON and NOT connected to another app.\n")

    scanner = BleakScanner(advertisement_callback)
    async with scanner:
        await asyncio.sleep(5)

    if not found_devices:
        print("\nNo LEGO devices found.")
        return

    print(f"\nScan complete. Found {len(found_devices)} device(s).")

    # Connect to each found device
    for device in found_devices:
        await connect_and_query(device)

    print("\nDone.")

asyncio.run(scan_devices())
