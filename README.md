# LEGO Hub BLE Controller

Python CLI for controlling LEGO Technic Move Hub (and other Powered Up hubs) via Bluetooth Low Energy.

## Requirements

- Python 3.10+
- `bleak` - BLE library for Python

```bash
pip install bleak
```

## Quick Start

### 1. Scan for Hubs

```bash
python cli.py scan
```

Scans for LEGO hubs and saves the found hub address for future commands.

### 2. Check Hub Status

```bash
python cli.py status
```

Shows hub name, battery level, firmware/hardware versions, and attached I/O devices.

### 3. Drive the Car

```bash
# Drive forward at 50% speed for 2 seconds
python cli.py drive 50 --duration 2

# Drive backward at 30% speed (runs until Ctrl+C)
python cli.py drive -30
```

### 4. Steer

```bash
# Steer left (-90 to 0) or right (0 to 90)
python cli.py steer -45   # steer left
python cli.py steer 45    # steer right
```

### 5. Control Lights

```bash
python cli.py lights 100   # full brightness
python cli.py lights 0     # off
```

### 6. Interactive Mode

```bash
python cli.py run
```

Controls:
- `W/S` or `Up/Down` arrows - accelerate/reverse
- `A/D` or `Left/Right` arrows - steer
- `Space` or `X` - stop (coast)
- `B` - brake (quick stop)
- `L` - toggle lights
- `Q` - quit

### 7. Xbox Controller Mode

```bash
python cli.py xbox
```

Control the car with an Xbox Series X|S controller connected via Bluetooth.

Controls:
- Right trigger - drive forward (analog speed 0-100)
- Left trigger - drive backward (analog speed 0-100)
- Left stick X - steer left/right
- A button - stop (coast)
- B button - brake (hold to brake, release to resume)
- X button - toggle lights
- Start button - quit

Notes:
- USB connections don't work on macOS due to driver restrictions. Use Bluetooth.
- Known issue: Brake (B button) does not work reliably while driving the car on the ground, but works when testing with the car upside down. Needs further investigation.

## CLI Commands

| Command | Description |
|---------|-------------|
| `scan` | Scan for LEGO hubs and save address |
| `status` | Show hub status (battery, firmware, I/O) |
| `drive <speed>` | Drive at speed (-100 to 100) |
| `steer <angle>` | Steer to angle (-90 to 90) |
| `stop` | Stop all motors (coast) |
| `lights <brightness>` | Set lights (0-100) |
| `calibrate` | Calibrate steering (find center) |
| `run` | Interactive keyboard control |
| `xbox` | Xbox controller control (Bluetooth) |

Options:
- `--address` / `-a` - Specify hub Bluetooth address (uses saved address if not specified)
- `--duration` / `-d` - Duration for drive command (seconds)
- `--timeout` / `-t` - Scan timeout (seconds, default 5)

## Technic Move Hub Specifics

The LEGO Technic Move Hub (found in sets like 42099 4x4 X-treme Off-Roader, 42124 Off-Road Buggy) uses a special combined control port for driving.

### Port Map

| Port | Device | Description |
|------|--------|-------------|
| 50 | TECHNIC_MOVE_HUB_DRIVE_MOTOR | Left drive motor |
| 51 | TECHNIC_MOVE_HUB_DRIVE_MOTOR | Right drive motor |
| 52 | TECHNIC_MOVE_HUB_STEERING_MOTOR | Steering motor |
| 53 | TECHNIC_MOVE_HUB_LIGHTS | Front lights |
| 54 (0x36) | Combined Virtual Port | Drive + Steer + Lights |

### Combined Control (Port 0x36)

The Technic Move Hub exposes a virtual port 0x36 (54) for combined control of drive, steering, and lights in a single command:

```python
# Combined command structure (13 bytes)
cmd = bytearray([
    0x0d, 0x00,           # Length (13 bytes)
    0x81,                 # Port Output Command
    0x36,                 # Port 54 (combined)
    0x11,                 # Execute immediately with feedback
    0x51, 0x00, 0x03,     # WriteDirectModeData, mode 3
    0x00,                 # Padding
    speed,                # Speed: -100 to 100 (signed byte)
    steering,             # Steering: -100 to 100 (signed byte)
    lights,               # Lights: 0 to 100
    0x00                  # Padding
])
```

### Steering Calibration

Before using the combined drive command, steering must be calibrated:

```python
port = 0x36

# Step 1: Start calibration (0x10)
cal1 = bytearray([0x0d, 0x00, 0x81, port, 0x11, 0x51, 0x00, 0x03,
                  0x00, 0x00, 0x00, 0x10, 0x00])
await send(cal1)
await asyncio.sleep(2.0)  # Wait for steering to find center

# Step 2: End calibration (0x08)
cal2 = bytearray([0x0d, 0x00, 0x81, port, 0x11, 0x51, 0x00, 0x03,
                  0x00, 0x00, 0x00, 0x08, 0x00])
await send(cal2)
```

The hub moves the steering motor to find its end stops, then centers it.

### Direct Motor Control

Individual motors can be controlled directly using port output commands:

```python
# Set motor power on a specific port
# [Length=8] [HubID=0] [MsgType=0x81] [Port] [Flags=0x11] [SubCmd=0x51] [Mode=0] [Power]
cmd = bytearray([0x08, 0x00, 0x81, port, 0x11, 0x51, 0x00, power])
```

Power values:
- `0` - Coast/float
- `1-100` - Forward
- `-1 to -100` (as `& 0xFF`) - Reverse
- `126` - Hold position
- `127` - Brake

### Lights Control

Lights can be controlled independently without calibration:

```python
# Set lights on port 53
port = 53  # TECHNIC_MOVE_HUB_LIGHTS
brightness = 100  # 0-100
cmd = bytearray([0x08, 0x00, 0x81, port, 0x11, 0x51, 0x00, brightness])
```

## LEGO BLE Wireless Protocol

Reference: https://lego.github.io/lego-ble-wireless-protocol-docs/index.html

### UUIDs

| Name | UUID |
|------|------|
| LEGO Manufacturer ID | 0x0397 |
| LEGO Service | `00001623-1212-efde-1623-785feabcd123` |
| LEGO Characteristic | `00001624-1212-efde-1623-785feabcd123` |

### Message Structure

All messages follow this format:

```
[Length] [Hub ID] [Message Type] [Payload...]
```

- **Length**: Total message length (1 byte for messages < 128 bytes)
- **Hub ID**: Always 0x00
- **Message Type**: See table below
- **Payload**: Message-specific data

### Message Types

| Type | Value | Description |
|------|-------|-------------|
| Hub Properties | 0x01 | Get/set hub properties (name, firmware, battery, etc.) |
| Hub Actions | 0x02 | Perform hub actions (shutdown, disconnect, etc.) |
| Hub Alerts | 0x03 | Subscribe to hub alerts |
| Hub Attached IO | 0x04 | Notification when IO devices attach/detach |
| Generic Error | 0x05 | Error messages from hub |
| Port Information Request | 0x21 | Request port capabilities |
| Port Mode Information Request | 0x22 | Request mode details |
| Port Input Format Setup (Single) | 0x41 | Configure sensor input format |
| Port Input Format Setup (Combined) | 0x42 | Configure combined mode input |
| Port Information | 0x43 | Response to port info request |
| Port Mode Information | 0x44 | Response to mode info request |
| Port Value (Single) | 0x45 | Sensor value update (single mode) |
| Port Value (Combined) | 0x46 | Sensor value update (combined mode) |
| Port Output Command | 0x81 | Send commands to motors/outputs |
| Port Output Command Feedback | 0x82 | Feedback from output commands |

### IO Device Types

Common device type IDs (see `io_device_type.py` for full list):

| Device | Type ID |
|--------|---------|
| Powered Up Medium Motor | 0x01 |
| Powered Up Train Motor | 0x02 |
| Powered Up Lights | 0x08 |
| Technic Large Motor | 0x2E |
| Technic XL Motor | 0x2F |
| Technic Move Hub Drive Motor | 0x56 |
| Technic Move Hub Steering Motor | 0x57 |
| Technic Move Hub Lights | 0x58 |
| Hub Battery Voltage | 0x14 |
| Hub IMU Accelerometer | 0x39 |
| Hub IMU Gyro | 0x3A |
| Hub IMU Position | 0x3B |

## Project Structure

```
lego-hub/
├── cli.py               # Main CLI entry point
├── config.py            # Hub address persistence (~/.lego-hub.json)
├── lego_hub.py          # LegoHub class for hub communication
├── scan.py              # Standalone scanner with detailed output
├── lego_message.py      # Message parsing class
├── message_header.py    # Header and MessageType enum
└── io_device_type.py    # IO device type enum
```

## References

- [LEGO BLE Wireless Protocol Docs](https://lego.github.io/lego-ble-wireless-protocol-docs/index.html)
- [Pybricks Assigned Numbers](https://github.com/pybricks/technical-info/blob/master/assigned-numbers.md)
- [node-poweredup](https://github.com/nathankellenicki/node-poweredup)
- [TechnicMoveHub](https://github.com/DanieleBenedettelli/TechnicMoveHub)
- [LEGO Bluetooth Programming (Japanese)](https://www.docswell.com/s/bricklife/ZDXYL5-lego-bluetooth-programming)
