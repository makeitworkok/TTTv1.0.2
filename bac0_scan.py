import BAC0
import asyncio
import csv
import datetime
import os
import socket
import fcntl
import struct

# Directory to store scan results as CSV files (project-relative or env override)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("TTT_RESULTS_DIR", os.path.join(BASE_DIR, "results"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get the IP address of a given network interface (e.g., 'eth0')
def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15].encode('utf-8'))
    )[20:24])

# Example usage to get eth0 IP and subnet mask
eth0_ip = get_ip_address('eth0')
ip_with_mask = f"{eth0_ip}/24"

# Main BACnet scan: discovers devices and collects all points/properties
async def bacnet_scan(ip_with_mask, return_networks=False):
    # Start BAC0 with the given IP/mask
    bacnet = BAC0.lite(ip=ip_with_mask)
    await asyncio.sleep(1)  # Allow BAC0 to initialize
    bacnet.discover()       # Send Who-Is to discover devices
    await asyncio.sleep(10) # Wait for responses

    discovered = getattr(bacnet, "discoveredDevices", {})
    results = []

    # Properties and object types to scan for each device
    props = ["objectName", "description", "units", "presentValue", "outOfService"]
    object_types = [
        "analogInput", "analogOutput", "analogValue",
        "binaryInput", "binaryOutput", "binaryValue",
        "multiStateInput", "multiStateOutput", "multiStateValue"
    ]

    # Loop through discovered devices
    for key, info in discovered.items():
        instance = info['object_instance'][1]
        device_ip = str(info['address'])
        network_number = info.get("network") or info.get("network_number") or ""

        # Read device-level info (vendor, model, location)
        device_info = {}
        for prop in ["vendorName", "modelName", "location"]:
            try:
                value = await bacnet.read(f"{device_ip} device {instance} {prop}")
                device_info[prop] = value
            except Exception:
                device_info[prop] = None

        # Try to get the objectList for the device (preferred)
        objects = []
        try:
            object_list = await bacnet.read(f"{device_ip} device {instance} objectList")
            for obj_type, obj_instance in object_list:
                obj_row = {
                    "device_instance": instance,
                    "device_ip": device_ip,
                    "network_number": network_number,
                    "object_type": obj_type,
                    "object_instance": obj_instance,
                    "vendorName": device_info["vendorName"],
                    "modelName": device_info["modelName"],
                    "location": device_info["location"]
                }
                # Read properties for each object
                for prop in props:
                    try:
                        value = await bacnet.read(f"{device_ip} {obj_type} {obj_instance} {prop}")
                        obj_row[prop] = value
                    except Exception:
                        obj_row[prop] = None
                objects.append(obj_row)
        except Exception:
            # If objectList fails, try common object types/instances manually
            for obj_type in object_types:
                if obj_type.startswith("analog"):
                    scan_props = ["objectName", "description", "presentValue", "outOfService"]
                else:
                    scan_props = ["objectName", "description", "units", "presentValue", "outOfService"]
                for idx in range(1, 10):
                    obj_found = False
                    obj_row = {
                        "device_instance": instance,
                        "device_ip": device_ip,
                        "network_number": network_number,
                        "object_type": obj_type,
                        "object_instance": idx,
                        "vendorName": device_info["vendorName"],
                        "modelName": device_info["modelName"],
                        "location": device_info["location"]
                    }
                    for prop in scan_props:
                        try:
                            value = await bacnet.read(f"{device_ip} {obj_type} {idx} {prop}")
                            obj_row[prop] = value
                            obj_found = True
                        except Exception:
                            obj_row[prop] = None
                    if obj_found:
                        objects.append(obj_row)

        results.extend(objects)

    # Optionally return the list of networks found
    if return_networks:
        networks_found = set()
        for info in discovered.values():
            net = info.get("network") or info.get("network_number")
            if net:
                networks_found.add(str(net))
        bacnet.disconnect()  # Properly disconnect BAC0 instance
        return results, sorted(networks_found)

    bacnet.disconnect()  # Properly disconnect BAC0 instance
    return results

# Quick BACnet scan: only queries device-level info (no points/objects)
async def bacnet_quick_scan(ip_with_mask, return_networks=False):
    bacnet = BAC0.lite(ip=ip_with_mask)
    await asyncio.sleep(1)
    bacnet.discover()
    await asyncio.sleep(10)

    discovered = getattr(bacnet, "discoveredDevices", {})
    results = []

    # Only collect device-level info for each discovered device
    for key, info in discovered.items():
        instance = info['object_instance'][1]
        device_ip = str(info['address'])
        network_number = info.get("network") or info.get("network_number") or ""

        device_info = {}
        for prop in ["vendorName", "modelName", "location"]:
            try:
                value = await bacnet.read(f"{device_ip} device {instance} {prop}")
                device_info[prop] = value
            except Exception:
                device_info[prop] = None

        results.append({
            "device_instance": instance,
            "device_ip": device_ip,
            "network_number": network_number,
            "vendorName": device_info["vendorName"],
            "modelName": device_info["modelName"],
            "location": device_info["location"]
        })

    # Optionally return the list of networks found
    if return_networks:
        networks_found = set()
        for info in discovered.values():
            net = info.get("network") or info.get("network_number")
            if net:
                networks_found.add(str(net))
        bacnet.disconnect()
        return results, sorted(networks_found)

    bacnet.disconnect()
    return results

# Export scan results to a CSV file and return the file path
def export_to_csv(results):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"bac0_scan_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        fieldnames = [
            "device_ip",
            "device_instance",
            "vendorName",
            "network_number",
            "location",
            "modelName",
            "object_instance",
            "objectName",
            "description",
            "presentValue",
            "units",
            "object_type",
            "outOfService"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for device in results:
            row = {key: device.get(key, "") for key in fieldnames}
            writer.writerow(row)
    return csv_path

