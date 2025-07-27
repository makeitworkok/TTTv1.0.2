import csv
import datetime
import os
import subprocess
import time
from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject
from bacpypes.pdu import Address
from bacpypes.core import run, stop
from bacpypes.apdu import WhoIsRequest, IAmRequest

OUTPUT_DIR = "/home/makeitworkok/TTTv1.0.2/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BACNET_PORT = 47808
DEVICE_ID = 1234
TIMEOUT = 5  # seconds


def get_eth0_ip():
    result = subprocess.getoutput(
        "ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'"
    )
    return result.strip()


def get_broadcast(ip):
    parts = ip.split(".")
    if len(parts) == 4:
        parts[-1] = "255"
        return ".".join(parts)
    return ip


class WhoIsCollector(BIPSimpleApplication):
    def __init__(self, device, local_ip):
        super().__init__(device, Address(f"{local_ip}:{BACNET_PORT}"))
        self.devices = []

    def indication(self, apdu):
        if isinstance(apdu, IAmRequest):
            self.devices.append(
                {
                    "device_instance": apdu.iAmDeviceIdentifier[1],
                    "address": str(apdu.pduSource),
                }
            )
        super().indication(apdu)


def bacnet_scan(timeout=TIMEOUT):
    local_ip = get_eth0_ip()
    if not local_ip:
        print("No IP found on eth0. Cannot run BACnet scan.")
        return [], None

    broadcast_ip = get_broadcast(local_ip)

    device = LocalDeviceObject(
        objectName="TTTv1Scanner",
        objectIdentifier=DEVICE_ID,
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15,
    )

    app = WhoIsCollector(device, local_ip)

    whois = WhoIsRequest()
    whois.pduDestination = Address(f"{broadcast_ip}:{BACNET_PORT}")
    app.request(whois)

    print(f"Scanning for BACnet devices ({timeout} seconds)...")
    for i in range(timeout, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    run(timeout=0)
    stop()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"bacnet_scan_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["device_instance", "address"])
        writer.writeheader()
        writer.writerows(app.devices)

    print("Scan complete.")
    print(f"Discovered {len(app.devices)} BACnet devices.")
    if csv_path:
        print(f"Results saved to {csv_path}")
    return app.devices, csv_path


if __name__ == "__main__":
    bacnet_scan()