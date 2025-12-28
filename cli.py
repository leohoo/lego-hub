#!/usr/bin/env python3
"""CLI for controlling LEGO Technic Move Hub."""

import argparse
import asyncio
import sys

from lego_hub import LegoHub
from config import get_hub_address, save_hub_address


async def cmd_scan(args):
    """Scan for LEGO hubs."""
    print(f"Scanning for LEGO hubs ({args.timeout}s)...")
    devices = await LegoHub.scan(timeout=args.timeout)

    if not devices:
        print("No LEGO hubs found.")
        return 1

    print(f"\nFound {len(devices)} hub(s):\n")
    for i, (address, name) in enumerate(devices, 1):
        print(f"  {i}. {name} ({address})")

    # Auto-save if only one device found, or prompt for selection
    if len(devices) == 1:
        address, name = devices[0]
        save_hub_address(address, name)
        print(f"\nSaved '{name}' as default hub.")
    elif len(devices) > 1 and not args.no_save:
        print("\nSelect hub to save as default (1-{}, or 0 to skip): ".format(len(devices)), end="")
        try:
            choice = int(input())
            if 1 <= choice <= len(devices):
                address, name = devices[choice - 1]
                save_hub_address(address, name)
                print(f"Saved '{name}' as default hub.")
        except (ValueError, EOFError):
            pass

    return 0


async def cmd_status(args):
    """Show hub status."""
    address = args.address or get_hub_address()
    if not address:
        print("No hub address. Run 'scan' first or use --address.")
        return 1

    hub = LegoHub()
    try:
        print(f"Connecting to {address}...")
        await hub.connect(address)
        status = await hub.get_status()

        print(f"\n  Hub: {status['name']}")
        print(f"  Battery: {status['battery']}%")
        print(f"  Firmware: {status['firmware']}")
        print(f"  Hardware: {status['hardware']}")

        if status['attached_io']:
            print(f"\n  Attached I/O:")
            for port, io_type in sorted(status['attached_io'].items()):
                print(f"    Port {port}: {io_type}")
    finally:
        await hub.disconnect()

    return 0


async def cmd_drive(args):
    """Drive the car."""
    address = args.address or get_hub_address()
    if not address:
        print("No hub address. Run 'scan' first or use --address.")
        return 1

    hub = LegoHub()
    try:
        print(f"Connecting to {address}...")
        await hub.connect(address, calibrate_steering=True)
        print(f"Driving at speed {args.speed}...")
        await hub.drive(args.speed)

        if args.duration:
            await asyncio.sleep(args.duration)
            await hub.stop()
            print("Stopped.")
        else:
            print("Press Ctrl+C to stop.")
            try:
                while True:
                    await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                await hub.stop()
                print("\nStopped.")
    finally:
        await hub.disconnect()

    return 0


async def cmd_steer(args):
    """Steer the car."""
    address = args.address or get_hub_address()
    if not address:
        print("No hub address. Run 'scan' first or use --address.")
        return 1

    hub = LegoHub()
    try:
        print(f"Connecting to {address}...")
        print("Calibrating steering...")
        await hub.connect(address, calibrate_steering=True)
        print(f"Steering to angle {args.angle}...")
        await hub.steer(args.angle)
        await asyncio.sleep(2)  # Hold position so user can see
    finally:
        await hub.disconnect()

    return 0


async def cmd_stop(args):
    """Stop all motors."""
    address = args.address or get_hub_address()
    if not address:
        print("No hub address. Run 'scan' first or use --address.")
        return 1

    hub = LegoHub()
    try:
        print(f"Connecting to {address}...")
        await hub.connect(address, calibrate_steering=True)
        await hub.stop()
        print("Stopped.")
    finally:
        await hub.disconnect()

    return 0


async def cmd_lights(args):
    """Control lights."""
    address = args.address or get_hub_address()
    if not address:
        print("No hub address. Run 'scan' first or use --address.")
        return 1

    hub = LegoHub()
    try:
        print(f"Connecting to {address}...")
        await hub.connect(address)
        print(f"Setting lights to {args.brightness}%...")
        await hub.set_lights(args.brightness)
        await asyncio.sleep(2)  # Keep lights on
    finally:
        await hub.disconnect()

    return 0


async def cmd_calibrate(args):
    """Calibrate steering."""
    address = args.address or get_hub_address()
    if not address:
        print("No hub address. Run 'scan' first or use --address.")
        return 1

    hub = LegoHub()
    try:
        print(f"Connecting to {address}...")
        await hub.connect(address)
        print("Calibrating steering (finding end stops)...")
        steering_range = await hub.calibrate_steering()
        print(f"Calibration complete. Steering centered.")
    finally:
        await hub.disconnect()

    return 0


async def cmd_run(args):
    """Interactive driving mode."""
    address = args.address or get_hub_address()
    if not address:
        print("No hub address. Run 'scan' first or use --address.")
        return 1

    hub = LegoHub()
    try:
        print(f"Connecting to {address}...")
        await hub.connect(address)
        print(f"Connected to {hub.name}!")
        print("Calibrating steering...")
        await hub.calibrate_steering()
        print("Ready!\n")
        print("Interactive mode:")
        print("  Arrow keys or w/a/s/d - drive & steer")
        print("  Space or x - stop (coast)")
        print("  b - brake (quick stop)")
        print("  l - toggle lights")
        print("  q - quit\n")

        import sys
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        lights_on = False
        speed = 0
        angle = 0

        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)

                # Handle arrow keys (escape sequences)
                if ch == '\x1b':
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A':  # Up arrow
                            ch = 'w'
                        elif ch3 == 'B':  # Down arrow
                            ch = 's'
                        elif ch3 == 'C':  # Right arrow
                            ch = 'd'
                        elif ch3 == 'D':  # Left arrow
                            ch = 'a'

                if ch == 'q':
                    break
                elif ch == 'w':
                    speed = min(100, speed + 20) if speed >= 0 else 0
                    await hub.drive(speed)
                    print(f"\rSpeed: {speed:4d}  Angle: {angle:4d}  ", end="", flush=True)
                elif ch == 's':
                    speed = max(-100, speed - 20) if speed <= 0 else 0
                    await hub.drive(speed)
                    print(f"\rSpeed: {speed:4d}  Angle: {angle:4d}  ", end="", flush=True)
                elif ch == 'a':
                    angle = max(-90, angle - 15)
                    await hub.steer(angle)
                    print(f"\rSpeed: {speed:4d}  Angle: {angle:4d}  ", end="", flush=True)
                elif ch == 'd':
                    angle = min(90, angle + 15)
                    await hub.steer(angle)
                    print(f"\rSpeed: {speed:4d}  Angle: {angle:4d}  ", end="", flush=True)
                elif ch == 'x' or ch == ' ':  # x or space to stop (coast)
                    speed = 0
                    angle = 0
                    await hub.stop()
                    print(f"\rSpeed: {speed:4d}  Angle: {angle:4d}  ", end="", flush=True)
                elif ch == 'b':  # brake (quick stop)
                    speed = 0
                    angle = 0
                    await hub.brake()
                    print(f"\rSpeed: {speed:4d}  Angle: {angle:4d}  [BRAKE]", end="", flush=True)
                elif ch == 'l':
                    lights_on = not lights_on
                    await hub.set_lights(100 if lights_on else 0)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            await hub.stop()
            print("\nDisconnecting...")
    finally:
        await hub.disconnect()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Control LEGO Technic Move Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--address", "-a",
        help="Hub Bluetooth address (uses saved address if not specified)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan for LEGO hubs")
    p_scan.add_argument("--timeout", "-t", type=int, default=5, help="Scan timeout (seconds)")
    p_scan.add_argument("--no-save", action="store_true", help="Don't save found hub")

    # status
    subparsers.add_parser("status", help="Show hub status")

    # drive
    p_drive = subparsers.add_parser("drive", help="Drive forward/backward")
    p_drive.add_argument("speed", type=int, help="Speed (-100 to 100)")
    p_drive.add_argument("--duration", "-d", type=float, help="Duration in seconds (runs until Ctrl+C if not set)")

    # steer
    p_steer = subparsers.add_parser("steer", help="Steer left/right (auto-calibrates)")
    p_steer.add_argument("angle", type=int, help="Angle (-90 to 90)")

    # stop
    subparsers.add_parser("stop", help="Stop all motors")

    # lights
    p_lights = subparsers.add_parser("lights", help="Control lights")
    p_lights.add_argument("brightness", type=int, help="Brightness (0-100)")

    # calibrate
    subparsers.add_parser("calibrate", help="Calibrate steering (find center)")

    # run (interactive)
    subparsers.add_parser("run", help="Interactive driving mode (keyboard control)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    handlers = {
        "scan": cmd_scan,
        "status": cmd_status,
        "drive": cmd_drive,
        "steer": cmd_steer,
        "stop": cmd_stop,
        "lights": cmd_lights,
        "calibrate": cmd_calibrate,
        "run": cmd_run,
    }

    return asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    sys.exit(main())
