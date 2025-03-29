# This script scans for BLE Lego Hub and processes advertisement data.
# https://lego.github.io/lego-ble-wireless-protocol-docs/index.html#advertising
# Manufacturer Data is interpreted as a dict by BleakScanner, value of the data starts from offet 4 (-4 to the table of the documentation)

import asyncio
from bleak import BleakScanner

def advertisement_callback(device, advertisement_data):
    """Callback function to handle advertisement data."""
    if device.name and "Technic Hub" in device.name:  # Filter for Technic Hub
        print(f"\n🔹 Device Found: {device.name} - {device.address}")

        # Manually extract manufacturer data from the advertisement bytes
        if advertisement_data.manufacturer_data:
            for manufacturer_id, data in advertisement_data.manufacturer_data.items():
                # Corrected extraction (index 0 to 5)
                print(f"🔹 Manufacturer ID: {manufacturer_id:04X}")
                print(f"🔹 Raw Manufacturer Data (Hex): {data.hex()}")

                # Extract fields from the data (index 0-5)
                print(f"🔹 Button State: {data[0]}")
                print(f"🔹 System Type and Device Number: 0x{data[1]:02X}")
                print(f"🔹 Device Capabilities: 0x{data[2]:02X}")
                print(f"🔹 Last Network ID: {data[3]}")
                print(f"🔹 Status: 0x{data[4]:02X}")
                print(f"🔹 Option: 0x{data[5]:02X}")  # Extract the Option field from index 5

async def scan_devices():
    """Scans for BLE devices using a callback function."""
    scanner = BleakScanner(advertisement_callback)
    async with scanner:
        await asyncio.sleep(10)  # Scan for 10 seconds

asyncio.run(scan_devices())
