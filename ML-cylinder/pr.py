#!/usr/bin/env python3
"""Run a local SOCKS5/HTTP proxy without changing OS network settings.

Default mode listens only on localhost.  To share an already-connected VPN
with a device on the same LAN, explicitly choose that LAN address:
    python pr.py --bind 192.168.0.10
"""

import argparse
import ipaddress
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


SOCKS5_PORT = 1080
HTTP_PORT = 3128
LOCALHOST = "127.0.0.1"


def private_ipv4_addresses() -> list[str]:
    """Return usable private IPv4 addresses reported by Windows."""
    addresses: set[str] = set()
    try:
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, encoding="cp949", errors="ignore", check=False
        )
        for value in re.findall(r"(?:IPv4[^:]*:\s*)(\d{1,3}(?:\.\d{1,3}){3})", result.stdout):
            try:
                address = ipaddress.ip_address(value)
                if address.is_private and not address.is_loopback and not address.is_link_local:
                    addresses.add(str(address))
            except ValueError:
                continue
    except OSError:
        pass
    return sorted(addresses, key=lambda value: tuple(map(int, value.split("."))))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a SOCKS5 and HTTP proxy.")
    parser.add_argument(
        "--bind",
        default=LOCALHOST,
        help="Listening IPv4 address. Default: 127.0.0.1 (this PC only).",
    )
    parser.add_argument("--socks-port", type=int, default=SOCKS5_PORT)
    parser.add_argument("--http-port", type=int, default=HTTP_PORT)
    return parser.parse_args()


def validate_bind_address(value: str) -> None:
    if value == "0.0.0.0":
        raise ValueError("0.0.0.0 is not allowed. Specify one LAN IPv4 address explicitly.")
    address = ipaddress.ip_address(value)
    if address.version != 4:
        raise ValueError("Only IPv4 addresses are supported.")
    if value != LOCALHOST and (not address.is_private or address.is_link_local):
        raise ValueError("--bind must be 127.0.0.1 or a private LAN IPv4 address.")


def start_proxy(args: argparse.Namespace) -> int:
    try:
        validate_bind_address(args.bind)
    except ValueError as exc:
        print(f"Invalid bind address: {exc}", file=sys.stderr)
        return 2

    if shutil.which("pproxy") is None:
        # This also works when pproxy was installed into the current Python environment.
        try:
            __import__("pproxy")
        except ImportError:
            print("pproxy is not installed. Run: python -m pip install pproxy", file=sys.stderr)
            return 1

    command = [
        sys.executable,
        "-m",
        "pproxy",
        "-l",
        f"socks5://{args.bind}:{args.socks_port}",
        "-l",
        f"http://{args.bind}:{args.http_port}",
    ]
    log_path = Path(__file__).with_name("pproxy.log")

    # This script never changes Windows proxy, routing, DNS, firewall, or VPN settings.
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
        time.sleep(1)
        if process.poll() is not None:
            print(f"Proxy failed to start. Check: {log_path}", file=sys.stderr)
            return process.returncode or 1

        print("Proxy started. Windows proxy, routing, DNS, and VPN settings were not changed.")
        print(f"SOCKS5: {args.bind}:{args.socks_port}")
        print(f"HTTP:   {args.bind}:{args.http_port}")
        if args.bind == LOCALHOST:
            print("Local-only mode. For LAN sharing, restart with --bind and one of:")
            for address in private_ipv4_addresses():
                print(f"  python pr.py --bind {address}")
        else:
            print("LAN sharing is enabled only on the selected interface. Do not set this PC's system proxy.")

        try:
            return process.wait()
        except KeyboardInterrupt:
            print("Stopping proxy...")
            process.terminate()
            try:
                return process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                return process.wait()


if __name__ == "__main__":
    raise SystemExit(start_proxy(parse_args()))
