import threading
import time
from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject
from bacpypes.pdu import Address
from bacpypes.core import run
from bacpypes.apdu import WhoIsRequest, IAmRequest, ReadPropertyRequest, ReadPropertyACK
from bacpypes.iocb import IOCB

BACNET_PORT = 47808
DEVICE_ID = 1234

class SingletonBACnetApp:
    def __init__(self, local_ip):
        self.device = LocalDeviceObject(
            objectName="TTTv1Scanner",
            objectIdentifier=DEVICE_ID,
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15,
        )
        self.app = BIPSimpleApplication(self.device, Address(f"{local_ip}:{BACNET_PORT}"))
        self.lock = threading.Lock()  # To serialize requests

    def run_forever(self):
        run()

# Singleton instance (to be initialized in your main app)
bacnet_app = None

def whois_scan(timeout=5):
    """
    Sends a WhoIs and collects IAm responses using the singleton BACnet app.
    """
    results = []
    responses = []

    def custom_indication(apdu):
        if isinstance(apdu, IAmRequest):
            responses.append({
                "device_instance": apdu.iAmDeviceIdentifier[1],
                "address": str(apdu.pduSource),
            })
        # Call the original handler if needed (optional)

    with bacnet_app.lock:
        # Save the original indication handler
        original_indication = bacnet_app.app.indication
        # Replace with our custom handler
        bacnet_app.app.indication = custom_indication

        # Send WhoIs
        whois = WhoIsRequest()
        whois.pduDestination = Address(f"255.255.255.255:{BACNET_PORT}")
        bacnet_app.app.request(whois)

        # Wait for responses
        time.sleep(timeout)

        # Restore the original handler
        bacnet_app.app.indication = original_indication

    return responses

def deep_scan(device_instance, address, timeout=5):
    """
    Query all objects and properties from a BACnet device.
    Returns a list of dicts (one per property).
    """
    results = []
    with bacnet_app.lock:
        # Step 1: Read the object list
        object_list = []
        try:
            req = ReadPropertyRequest(
                objectIdentifier=("device", int(device_instance)),
                propertyIdentifier="objectList",
                destination=Address(address),
            )
            iocb = IOCB(req)
            bacnet_app.app.request_io(iocb)
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
        for obj_id in object_list:
            for prop in ["objectName", "presentValue", "description", "units"]:
                try:
                    req = ReadPropertyRequest(
                        objectIdentifier=obj_id,
                        propertyIdentifier=prop,
                        destination=Address(address),
                    )
                    iocb = IOCB(req)
                    bacnet_app.app.request_io(iocb)
                    iocb.wait(timeout=timeout)
                    ack = iocb.ioResponse
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
    return results