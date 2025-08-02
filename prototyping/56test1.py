import BAC0
import asyncio
import csv
import socket
import fcntl
import struct

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15].encode('utf-8'))
    )[20:24])

# Usage:
eth0_ip = get_ip_address('eth0')
ip_with_mask = f"{eth0_ip}/24"

async def main():
    bacnet = BAC0.lite(ip=ip_with_mask)
    bacnet.discover()
    await asyncio.sleep(10)

    discovered = getattr(bacnet, "discoveredDevices", {})
    print("BAC0 discoveredDevices:", discovered)

    props = ["objectName", "description", "units", "presentValue", "outOfService"]

    object_types = [
        "analogInput", "analogOutput", "analogValue",
        "binaryInput", "binaryOutput", "binaryValue",
        "multiStateInput", "multiStateOutput", "multiStateValue"
    ]

    rows = []

    for key, info in discovered.items():
        instance = info['object_instance'][1]
        device_ip = info['address']
        # Get device-level MAC and network number
        network_number = info.get("network") or info.get("network_number") or ""
        print(f"\nDeep scanning device instance {instance} at {device_ip}")

        # Read device-level info
        device_info = {}
        for prop in ["vendorName", "modelName", "location"]:
            try:
                value = await bacnet.read(f"{device_ip} device {instance} {prop}")
                device_info[prop] = value
            except Exception:
                device_info[prop] = None

        # Try objectList first
        try:
            object_list = await bacnet.read(f"{device_ip} device {instance} objectList")
            print(f"RAW objectList for device {instance}:", object_list)
            for obj_type, obj_instance in object_list:
                row = {
                    "device_instance": instance,
                    "device_ip": device_ip,
                    "network_number": network_number,
                    "object_type": obj_type,
                    "object_instance": obj_instance,
                    "vendorName": device_info["vendorName"],
                    "modelName": device_info["modelName"],
                    "location": device_info["location"]
                }
                for prop in props:
                    try:
                        value = await bacnet.read(f"{device_ip} {obj_type} {obj_instance} {prop}")
                        row[prop] = value
                    except Exception as e:
                        row[prop] = None
                rows.append(row)
        except Exception as e:
            print(f"Error reading objectList for device {instance}: {e}")
            # Fallback: probe common object types/instances
            for obj_type in object_types:
                if obj_type.startswith("analog"):
                    scan_props = ["objectName", "description", "presentValue", "outOfService"]
                else:
                    scan_props = ["objectName", "description", "units", "presentValue", "outOfService"]
                for idx in range(1, 10):
                    obj_found = False
                    row = {
                        "device_instance": instance,
                        "device_ip": device_ip,
                        "network_number": network_number,
                        "mac": mac,
                        "object_type": obj_type,
                        "object_instance": idx,
                        "vendorName": device_info["vendorName"],
                        "modelName": device_info["modelName"],
                        "location": device_info["location"]
                    }
                    for prop in scan_props:
                        try:
                            value = await bacnet.read(f"{device_ip} {obj_type} {idx} {prop}")
                            row[prop] = value
                            obj_found = True
                        except Exception:
                            row[prop] = None
                    if obj_found:
                        rows.append(row)

    # Write to CSV
    csv_path = "bacnet_points.csv"
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
        "outOfService",
    ]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"\nResults written to {csv_path}")

    await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
