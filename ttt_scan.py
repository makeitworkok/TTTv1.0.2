import subprocess
import csv
import datetime
import os

# Directory to save CSV results
OUTPUT_DIR = "/home/makeitworkok/TTTv1.0.2/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def scan_network(interface="eth0", subnet="10.46.12.0/24"):
    try:
        print(f"Scanning {subnet} on {interface}...")
        result = subprocess.run(
            ["sudo", "arp-scan", "--interface", interface, subnet],
            capture_output=True, text=True, check=True
        )
        
        lines = result.stdout.splitlines()
        devices = []
        for line in lines:
            # Look for lines that contain IP and MAC
            if line and ":" in line and line.split()[0].startswith("10."):
                parts = line.split()
                ip, mac = parts[0], parts[1]
                devices.append((ip, mac))
        
        # Save to CSV
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(OUTPUT_DIR, f"scan_{timestamp}.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["IP Address", "MAC Address"])
            writer.writerows(devices)
        
        print(f"Found {len(devices)} devices.")
        print(f"Results saved to {csv_path}")
        return devices
    except subprocess.CalledProcessError as e:
        print("Scan failed. Are you connected to the right network?")
        return []

if __name__ == "__main__":
    scan_network()
