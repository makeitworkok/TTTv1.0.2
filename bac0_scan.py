import BAC0
import asyncio
import csv
import datetime
import os

OUTPUT_DIR = "/home/makeitworkok/TTTv1.0.2/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

_bacnet_instance = None

async def get_bacnet(ip_with_mask="192.168.0.63/24"):
    global _bacnet_instance
    if _bacnet_instance is None:
        _bacnet_instance = BAC0.lite(ip=ip_with_mask)
        await asyncio.sleep(1)  # Give BAC0 time to initialize
    return _bacnet_instance

async def bacnet_scan(ip_with_mask="192.168.0.63/24", extra_props=None):
    bacnet = await get_bacnet(ip_with_mask)
    bacnet.discover()
    await asyncio.sleep(10)

    discovered = getattr(bacnet, "discoveredDevices", {})
    results = []
    device_props = [
        "objectName", "vendorName", "modelName", "description",
        "systemStatus", "firmwareRevision", "location"
    ]
    if extra_props:
        device_props.extend(extra_props)

    object_types = [
        "analogInput", "analogOutput", "analogValue",
        "binaryInput", "binaryOutput", "binaryValue"
    ]
    max_instance = 4  # Adjust as needed

    for key, info in discovered.items():
        instance = info['object_instance'][1]
        device_ip = str(info['address'])
        # Gather device-level info
        device_info = {}
        for prop in device_props:
            try:
                value = await bacnet.read(f"{device_ip} device {instance} {prop}")
                device_info[prop] = value
            except Exception as e:
                device_info[prop] = f"Error: {e}"

        # Gather all objects/points for this device
        objects = []
        for obj_type in object_types:
            if obj_type.startswith("analog"):
                props = ["objectName", "description", "presentValue"]
            else:
                props = ["objectName", "description", "units", "presentValue"]
            if extra_props:
                props.extend(extra_props)
            for idx in range(1, max_instance + 1):
                obj_found = False
                obj_data = {
                    "object_type": obj_type,
                    "object_instance": idx,
                }
                try:
                    # Probe with objectName first
                    value = await bacnet.read(f"{device_ip} {obj_type} {idx} objectName")
                    obj_data["objectName"] = value
                    obj_found = True
                except Exception:
                    continue  # Skip this object if objectName fails
                for prop in props:
                    if prop == "objectName":
                        continue
                    try:
                        value = await bacnet.read(f"{device_ip} {obj_type} {idx} {prop}")
                        obj_data[prop] = value
                    except Exception:
                        obj_data[prop] = None
                if obj_found:
                    objects.append(obj_data)

        device_data = {
            "device_instance": instance,
            "address": device_ip,
            **device_info,
            "objects": objects
        }
        results.append(device_data)

    # Clean up vendor/model for display
    for device in results:
        for key in ["vendorName", "modelName"]:
            val = device.get(key, "")
            if not val or "Error" in str(val):
                device[key] = "-"
            else:
                device[key] = str(val)
    return results

def export_to_csv(results):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"bac0_scan_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        fieldnames = [
            "device_instance", "address",
            "objectName", "vendorName", "modelName", "description",
            "systemStatus", "firmwareRevision", "location"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for device in results:
            row = {key: device.get(key, "") for key in fieldnames}
            writer.writerow(row)
    return csv_path

async def bacnet_deep_scan(device_instance, address, extra_props=None):
    bacnet = await get_bacnet()
    object_types = [
        "analogInput", "analogOutput", "analogValue",
        "binaryInput", "binaryOutput", "binaryValue"
    ]
    results = []
    max_instance = 4  # Adjust as needed for your site

    for obj_type in object_types:
        # 'units' is usually only for analogs
        if obj_type.startswith("analog"):
            props = ["objectName", "description", "presentValue"]
        else:
            props = ["objectName", "description", "units", "presentValue"]
        if extra_props:
            props.extend(extra_props)
        for idx in range(1, max_instance + 1):
            obj_found = False
            obj_data = {
                "object_type": obj_type,
                "object_instance": idx,
            }
            for prop in props:
                try:
                    value = await bacnet.read(f"{address} {obj_type} {idx} {prop}")
                    obj_data[prop] = value
                    obj_found = True
                except Exception:
                    obj_data[prop] = None
            if obj_found:
                results.append(obj_data)
                print(f"Reading: {address} {obj_type} {idx} {prop}")
    if not results:
        results.append({
            "object_type": "device",
            "object_instance": device_instance,
            "property": "error",
            "value": "No objects found or device did not respond."
        })
    print(f"Deep scan for address={address}, device_instance={device_instance}")
    return results

def export_deep_scan_to_csv(results):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"bacnet_deep_scan_{timestamp}.csv")
    # Collect all possible keys from results for fieldnames
    all_keys = set()
    for row in results:
        all_keys.update(row.keys())
    fieldnames = list(all_keys)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    return csv_path
