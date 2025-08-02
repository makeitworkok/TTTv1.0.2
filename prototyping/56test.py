import BAC0
import asyncio

async def main():
    device_ip = "192.168.0.135"
    bacnet = BAC0.lite(ip="192.168.0.63/24")  # Use your local IP/mask

    await asyncio.sleep(2)  # Give BAC0 time to initialize

    object_types = [
        "analogInput", "analogOutput", "analogValue",
        "binaryInput", "binaryOutput", "binaryValue"
    ]
    base_props = ["objectName", "description", "presentValue"]

    discovered = []

    for obj_type in object_types:
        # Only include 'units' for non-analog types
        if obj_type.startswith("analog"):
            props = ["objectName", "description", "presentValue"]
        else:
            props = ["objectName", "description", "units", "presentValue"]

        for idx in range(1, 10):  # Scan a reasonable range for each type
            obj_found = False
            obj_data = {"type": obj_type, "instance": idx}
            for prop in props:
                try:
                    value = await bacnet.read(f"{device_ip} {obj_type} {idx} {prop}")
                    obj_data[prop] = value
                    obj_found = True
                except Exception:
                    obj_data[prop] = None
            if obj_found:
                discovered.append(obj_data)
                print(f"Found {obj_type} {idx}:")
                for prop in props:
                    print(f"  {prop}: {obj_data[prop]}")
                print("-" * 30)

    print(f"\nTotal discovered objects: {len(discovered)}")

    await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())