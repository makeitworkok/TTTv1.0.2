import csv
import datetime
import os
import subprocess
import time
from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject
from bacpypes.pdu import Address
from bacpypes.core import run, stop
from bacpypes.apdu import WhoIsRequest, IAmRequest, ReadPropertyRequest, ReadPropertyACK, ReadAccessSpecification, ReadPropertyMultipleRequest, ReadAccessResult
from bacpypes.object import get_datatype
from bacpypes.iocb import IOCB

OUTPUT_DIR = "/home/makeitworkok/TTTv1.0.2/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BACNET_PORT = 47808
DEVICE_ID = 1234
TIMEOUT = 10  # seconds


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
            device_instance = apdu.iAmDeviceIdentifier[1]
            address = str(apdu.pduSource)
            device_info = {
                "device_instance": device_instance,
                "address": address,
                "object_name": "",
                "vendor_name": "",
                "model_name": "",
            }
            # Try to read additional properties
            for prop, key in [
                ("objectName", "object_name"),
                ("vendorName", "vendor_name"),
                ("modelName", "model_name"),
            ]:
                try:
                    req = ReadPropertyRequest(
                        objectIdentifier=("device", device_instance),
                        propertyIdentifier=prop,
                        destination=Address(address),
                    )
                    self.request(req)
                    ack = self.get_next_response(timeout=1)
                    if isinstance(ack, ReadPropertyACK):
                        device_info[key] = str(ack.propertyValue.cast_out())
                except Exception:
                    pass
            self.devices.append(device_info)
        super().indication(apdu)

    def get_next_response(self, timeout=1):
        # Wait for a response (simple synchronous wait)
        import queue
        q = queue.Queue()
        def response_handler(apdu):
            q.put(apdu)
        self.response = response_handler
        try:
            return q.get(timeout=timeout)
        except Exception:
            return None


def bacnet_scan(timeout=TIMEOUT):
    local_ip = get_eth0_ip()
    if not local_ip:
        print("No IP found on eth0. Cannot run BACnet scan.")
        return [], None

    device = LocalDeviceObject(
        objectName="TTTv1Scanner",
        objectIdentifier=DEVICE_ID,
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15,
    )

    app = WhoIsCollector(device, local_ip)

    whois = WhoIsRequest()
    whois.pduDestination = Address(f"255.255.255.255:{BACNET_PORT}")
    app.request(whois)

    print(f"Scanning for BACnet devices ({timeout} seconds)...")
    # Start event loop in a thread, sleep in main thread
    from threading import Thread
    t = Thread(target=run)
    t.start()
    for i in range(timeout, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    stop()
    t.join()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"bacnet_scan_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "device_instance",
                "address",
                "object_name",
                "vendor_name",
                "model_name",
            ],
        )
        writer.writeheader()
        writer.writerows(app.devices)

    print("Scan complete.")
    print(f"Discovered {len(app.devices)} BACnet devices.")
    if csv_path:
        print(f"Results saved to {csv_path}")
    return app.devices, csv_path


def deep_scan_device(device_instance, address, timeout=5):
    """
    Query all objects and properties from a BACnet device.
    Returns a list of dicts (one per property).
    """
    local_ip = get_eth0_ip()
    DEEP_SCAN_PORT = 47809
    device = LocalDeviceObject(
        objectName="TTTv1DeepScanner",
        objectIdentifier=DEVICE_ID + 1,
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15,
    )
    app = BIPSimpleApplication(device, Address(f"{local_ip}:{DEEP_SCAN_PORT}"))

    # Step 1: Read the object list
    object_list = []
    try:
        req = ReadPropertyRequest(
            objectIdentifier=("device", device_instance),
            propertyIdentifier="objectList",
            destination=Address(address),
        )
        iocb = IOCB(req)
        app.request_io(iocb)
        iocb.wait(timeout=timeout)
        ack = iocb.ioResponse
        if isinstance(ack, ReadPropertyACK):
            object_list = ack.propertyValue.cast_out()
        else:
            print("No response or error for objectList")
    except Exception as e:
        print(f"Failed to read objectList: {e}")
        return []

    # Step 2: For each object, read common properties
    results = []
    for obj_id in object_list:
        for prop in ["objectName", "presentValue", "description", "units"]:
            try:
                req = ReadPropertyRequest(
                    objectIdentifier=obj_id,
                    propertyIdentifier=prop,
                    destination=Address(address),  # Always send to device's IP:47808
                )
                app.request(req)
                ack = app.get_next_response(timeout=timeout)
                if isinstance(ack, ReadPropertyACK):
                    value = ack.propertyValue.cast_out()
                else:
                    value = ""
            except Exception:
                value = ""
            results.append({
                "object_type": obj_id[0],
                "instance": obj_id[1],
                "property": prop,
                "value": value,
            })
    # Save to CSV
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"deep_scan_{device_instance}_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["object_type", "instance", "property", "value"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Deep scan complete for device {device_instance}. Results saved to {csv_path}")
    return results, csv_path


if __name__ == "__main__":
    bacnet_scan()