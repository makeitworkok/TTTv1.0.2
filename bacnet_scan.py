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
from bacpypes.constructeddata import ArrayOf
from bacpypes.object import ObjectIdentifier
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
    Reduced deep scan: just read and save the objectList property from the device.
    """
    print("Entered deep_scan_device")
    local_ip = get_eth0_ip()
    DEEP_SCAN_PORT = BACNET_PORT
    device = LocalDeviceObject(
        objectName="TTTv1DeepScanner",
        objectIdentifier=DEVICE_ID + 1,
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15,
    )
    app = BIPSimpleApplication(device, Address(f"{local_ip}:{DEEP_SCAN_PORT}"))

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
        print(f"DEBUG: ack type: {type(ack)}, ack value: {repr(ack)}")
        if isinstance(ack, ReadPropertyACK):
            print("=== BACnet Deep Scan Debug ===")
            print(f"type(ack.propertyValue): {type(ack.propertyValue)}")
            print(f"repr(ack.propertyValue): {repr(ack.propertyValue)}")
            print(f"dir(ack.propertyValue): {dir(ack.propertyValue)}")
            print("Trying cast_out(list)...")
            try:
                object_list = ack.propertyValue.cast_out(list)
                print(f"objectList received (cast_out(list)): {object_list}")
            except Exception as e:
                print(f"cast_out(list) failed: {e}")
            print("Trying cast_out(tuple)...")
            try:
                object_list = ack.propertyValue.cast_out(tuple)
                print(f"objectList received (cast_out(tuple)): {object_list}")
            except Exception as e:
                print(f"cast_out(tuple) failed: {e}")
            print("Trying cast_out(str)...")
            try:
                object_list = ack.propertyValue.cast_out(str)
                print(f"objectList received (cast_out(str)): {object_list}")
            except Exception as e:
                print(f"cast_out(str) failed: {e}")
            print("Trying cast_out() with no args...")
            try:
                object_list = ack.propertyValue.cast_out()
                print(f"objectList received (cast_out()): {object_list}")
            except Exception as e:
                print(f"cast_out() failed: {e}")
            print("=== End BACnet Deep Scan Debug ===")
        else:
            print(f"No response or error for objectList (ack={ack})")
            return []
    except Exception as e:
        print(f"Failed to read objectList: {e}")
        return []

    # Save just the object list to CSV
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"deep_scan_{device_instance}_{timestamp}.csv")
    fieldnames = ["object_type", "instance"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for obj in object_list:
            if isinstance(obj, (list, tuple)) and len(obj) == 2:
                writer.writerow({"object_type": obj[0], "instance": obj[1]})
            else:
                writer.writerow({"object_type": str(obj), "instance": ""})
    print(f"Object list for device {device_instance} saved to {csv_path}")
    return object_list, csv_path


if __name__ == "__main__":
    bacnet_scan()