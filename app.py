from flask import Flask, render_template, request, redirect, url_for, send_file
import subprocess, csv, datetime, os, re, socket
import asyncio

from bac0_scan import bacnet_scan, bacnet_quick_scan, export_to_csv

app = Flask(__name__)

# Directory to store scan results
OUTPUT_DIR = "/home/makeitworkok/TTTv1.0.2/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# File to store the selected scan range for ARP scan
SCAN_RANGE_FILE = "/tmp/scan_range.txt"

# Get the current IP address of eth0
def get_eth0_ip():
    ip = subprocess.getoutput("ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'")
    return ip.splitlines()[0] if ip else ""

# Run ARP scan on the specified subnet, repeat for reliability
def run_arp_scan_with_range(subnet, repeats=10):
    devices_dict = {}
    try:
        from mac_vendor_lookup import MacLookup
        mac_lookup = MacLookup()
    except Exception as e:
        print("MacLookup import failed:", e)
        mac_lookup = None

    for _ in range(repeats):
        try:
            result = subprocess.run(
                ["arp-scan", "--interface", "eth0", subnet],
                capture_output=True, text=True, check=True
            )
            for line in result.stdout.splitlines():
                if line and ":" in line and line.split()[0].split('.')[0].isdigit():
                    parts = line.split()
                    ip, mac = parts[0], parts[1]
                    # Try to resolve hostname
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        hostname = ""
                    # Try to resolve vendor
                    try:
                        vendor = mac_lookup.lookup(mac) if mac_lookup else ""
                    except Exception:
                        vendor = ""
                    if mac not in devices_dict:
                        devices_dict[mac] = [ip, mac, hostname, vendor]
        except Exception as e:
            print("ARP scan failed:", e)
            continue

    devices = list(devices_dict.values())

    # Save results to CSV
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"arp_scan_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["IP Address", "MAC Address", "Hostname", "Vendor"])
        writer.writerows(devices)
    return devices, csv_path

# Get the current scan range for ARP scan
def get_scan_range():
    # Default to 192.168.0.0/24 if not set
    if not os.path.exists(SCAN_RANGE_FILE):
        return "192.168.0.0/24"
    with open(SCAN_RANGE_FILE, "r") as f:
        return f.read().strip() or "192.168.0.0/24"

# Set the scan range for ARP scan
def set_scan_range(subnet):
    with open(SCAN_RANGE_FILE, "w") as f:
        f.write(subnet)

# --- Flask Routes ---

@app.route("/")
def home():
    current_ip = get_eth0_ip()
    current_gw = subprocess.getoutput("ip route | grep '^default' | awk '{print $3}'")
    eth0_active = is_eth0_active()
    return render_template("index.html", current_ip=current_ip, current_gw=current_gw, eth0_active=eth0_active)

@app.route("/scan", methods=["GET", "POST"])
def scan():
    # ARP network scan page
    subnet = get_scan_range()
    devices, csv_path = [], None

    if request.method == "POST":
        if "octet" in request.form:
            # User updated subnet range
            base_ip = request.form.getlist("octet")
            cidr = request.form.get("cidr", "24")
            new_range = ".".join(base_ip) + f"/{cidr}"
            set_scan_range(new_range)
            subnet = new_range
        else:
            # User triggered a scan
            devices, csv_path = run_arp_scan_with_range(subnet)

    # Break subnet into parts for the controls
    base_ip, cidr = subnet.split("/")
    eth0_active = is_eth0_active()
    return render_template("scan.html", devices=devices, csv_path=csv_path,
                           base_ip=base_ip.split("."), cidr=cidr, eth0_active=eth0_active)

@app.route("/download/<filename>")
def download(filename):
    # Download CSV file by filename
    return send_file(os.path.join(OUTPUT_DIR, filename), as_attachment=True)

# --- Network Config Page ---
@app.route("/network", methods=["GET", "POST"])
def network():
    config_file = "/etc/dhcpcd.conf"

    # Set eth0 to DHCP mode
    def set_dhcp():
        # Remove static config for eth0 entirely
        with open(config_file, "r") as f:
            lines = f.readlines()
        with open(config_file, "w") as f:
            for line in lines:
                if not line.startswith(("interface eth0", "static ip_address=", "static routers=", "static domain_name_servers=")):
                    f.write(line)
        subprocess.run(["sudo", "systemctl", "restart", "dhcpcd"])

    # Set eth0 to static mode with given IP/mask/gateway
    def set_static(ip, mask, gateway):
        with open(config_file, "r") as f:
            lines = f.readlines()
        with open(config_file, "w") as f:
            for line in lines:
                if not line.startswith(("interface eth0", "static ip_address=", "static routers=", "static domain_name_servers=")):
                    f.write(line)
            f.write("interface eth0\n")
            f.write(f"static ip_address={ip}/{mask}\n")
            f.write(f"static routers={gateway}\n")
            f.write(f"static domain_name_servers={gateway}\n")
        subprocess.run(["sudo", "systemctl", "restart", "dhcpcd"])

    if request.method == "POST":
        mode = request.form.get("mode")
        if mode == "dhcp":
            set_dhcp()
        elif mode == "static":
            ip = request.form.get("ip")
            mask = request.form.get("mask", "24")
            gateway = request.form.get("gateway")
            # Validate IP and gateway format
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", gateway):
                set_static(ip, mask, gateway)
        return redirect(url_for("network"))

    # Detect mode (DHCP or Static)
    mode = "dhcp"
    with open(config_file, "r") as f:
        conf = f.read()
        if "static ip_address=" in conf:
            mode = "static"

    # Get current live IP and Gateway every time the page loads
    current_ip = get_eth0_ip()
    current_gw = subprocess.getoutput("ip route | grep '^default' | awk '{print $3}'")

    # Split into octets (default to 0 if missing)
    def split_octets(addr):
        parts = addr.split(".") if addr else ["0","0","0","0"]
        while len(parts) < 4:
            parts.append("0")
        return parts

    ip_octets = split_octets(current_ip)
    gw_octets = split_octets(current_gw)

    return render_template("network.html", 
                           current_ip=current_ip, 
                           mode=mode,
                           ip_octets=ip_octets,
                           gw_octets=gw_octets)

# --- BACnet Scan Page ---
@app.route("/bacnet_scan", methods=["GET", "POST"])
def bacnet_scan_route():
    results = {}
    if request.method == "POST":
        scan_type = request.form.get("scan_type", "full")
        eth0_ip = get_eth0_ip()
        ip_with_mask = f"{eth0_ip}/24" if eth0_ip else "0.0.0.0/24"
        # Choose scan type: quick or full
        if scan_type == "quick":
            scan_results, networks_found = asyncio.run(bacnet_quick_scan(ip_with_mask, return_networks=True))
        else:
            scan_results, networks_found = asyncio.run(bacnet_scan(ip_with_mask, return_networks=True))

        # Only keep one entry per unique device_instance
        unique_devices = {}
        for d in scan_results:
            inst = d["device_instance"]
            if inst not in unique_devices:
                unique_devices[inst] = d

        results = {
            "devices": [
                {
                    "device_instance": d["device_instance"],
                    "address": d["device_ip"],
                    "vendorName": d.get("vendorName", "-"),
                    "modelName": d.get("modelName", "-")
                }
                for d in unique_devices.values()
            ],
            "csv": export_to_csv(scan_results),
            "networks_found": networks_found,
            "device_count": len(unique_devices)
        }
    eth0_active = is_eth0_active()
    return render_template("bacnet.html", results=results, eth0_active=eth0_active)

@app.route("/download_csv")
def download_csv():
    # Download CSV by path (legacy, not used in main flow)
    path = request.args.get("path")
    return send_file(path, as_attachment=True)

# --- Add your other routes (network, index, etc.) below ---

def is_eth0_active():
    # Returns True if eth0 is up, False otherwise
    output = subprocess.getoutput("cat /sys/class/net/eth0/operstate")
    return output.strip() == "up"

if __name__ == "__main__":
    print("Flask app started!")
    app.run(host="0.0.0.0", port=80)
