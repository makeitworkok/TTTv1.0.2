import BAC0
import asyncio

async def main():
    ip_with_mask = "192.168.0.63/24"
    bacnet = BAC0.lite(ip=ip_with_mask)

    bacnet.discover()
    await asyncio.sleep(10)  # Give time for discovery

    discovered = getattr(bacnet, "discoveredDevices", {})
    print("BAC0 discoveredDevices:", discovered)

    props = ["objectName", "description", "units", "presentValue"]

    for key, info in discovered.items():
        instance = info['object_instance'][1]
        device_ip = info['address']
        print(f"\nDeep scanning device instance {instance} at {device_ip}")
        try:
            object_list = await bacnet.read(f"{device_ip} device {instance} objectList")
            print(f"RAW objectList for device {instance}:", object_list)
            for obj_type, obj_instance in object_list:
                print(f"\nObject: type={obj_type}, instance={obj_instance}")
                for prop in props:
                    try:
                        value = await bacnet.read(f"{device_ip} {obj_type} {obj_instance} {prop}")
                        print(f"  {prop}: {value}")
                    except Exception as e:
                        print(f"  Error reading {prop}: {e}")
        except Exception as e:
            print(f"Error reading objectList for device {instance}: {e}")

    await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())