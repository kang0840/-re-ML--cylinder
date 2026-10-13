"""Keep the public Render service active while this script runs on the Pi.

Run: python3 "Server Power.py"
Stop: Ctrl+C
Uses only the Python standard library. Does not enable startup on boot.
"""

import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SERVER_URL = "https://ml-cylinder.onrender.com/"
INTERVAL_SECONDS = 300
TIMEOUT_SECONDS = 90
KST = timezone(timedelta(hours=9))


def log(message):
    print(f"[{datetime.now(KST):%Y-%m-%d %H:%M:%S} KST] {message}", flush=True)


def ping_server():
    request = Request(SERVER_URL, headers={"User-Agent": "SmartCylinder-ServerPower/1.0"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            log(f"HTTP {response.status}: response received")
    except HTTPError as error:
        log(f"HTTP {error.code}: server returned an error; will retry next interval")
        error.close()
    except (URLError, OSError, TimeoutError):
        log("Connection failed or timed out; will retry next interval")


def main():
    log("Started: sending a request every 5 minutes. Stop with Ctrl+C.")
    try:
        while True:
            ping_server()
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log("Stopped")


if __name__ == "__main__":
    main()
