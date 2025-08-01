from flask import Flask, render_template, request, redirect, url_for, send_file
import subprocess, csv, datetime, os, re, socket
import threading

from bacnet_core import SingletonBACnetApp, whois_scan, deep_scan

app = Flask(__name__)

OUTPUT_DIR = "/home/makeitworkok/TTTv1.0.2/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SCAN_RANGE_FILE = "/tmp/scan_range.txt"

def get_eth0_ip():
    ip = subprocess.getoutput("ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'")
    return ip.splitlines()[0] if ip else ""

# --- BACnet Singleton Initialization (must be before any route uses bacnet_app) ---
local_ip = get_eth0_ip()
from bacnet_core import bacnet_app as _bacnet_app
_bacnet_app = SingletonBACnetApp(local_ip)
import bacnet_core
bacnet_core.bacnet_app = _bacnet_app

event_loop_thread = threading.Thread(target=_bacnet_app.run_forever, daemon=True)
event_loop_thread.start()

# --- ARP Scan ---
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
                    # Hostname lookup
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        hostname = ""
                    # Vendor lookup
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

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"arp_scan_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["IP Address", "MAC Address", "Hostname", "Vendor"])
        writer.writerows(devices)
    return devices, csv_path

def get_scan_range():
    # Default to 192.168.0.0/24 if not set
    if not os.path.exists(SCAN_RANGE_FILE):
        return "192.168.0.0/24"
    with open(SCAN_RANGE_FILE, "r") as f:
        return f.read().strip() or "192.168.0.0/24"

def set_scan_range(subnet):
    with open(SCAN_RANGE_FILE, "w") as f:
        f.write(subnet)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/scan", methods=["GET", "POST"])
def scan():
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
    return render_template("scan.html", devices=devices, csv_path=csv_path,
                           base_ip=base_ip.split("."), cidr=cidr)

@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_DIR, filename), as_attachment=True)

# --- Network Config Page ---
@app.route("/network", methods=["GET", "POST"])
def network():
    config_file = "/etc/dhcpcd.conf"

    def set_dhcp():
        # Remove static config for eth0 entirely
        with open(config_file, "r") as f:
            lines = f.readlines()
        with open(config_file, "w") as f:
            for line in lines:
                if not line.startswith(("interface eth0", "static ip_address=", "static routers=", "static domain_name_servers=")):
                    f.write(line)
        subprocess.run(["sudo", "systemctl", "restart", "dhcpcd"])

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

# --- BACnet Scan (with background thread and countdown) ---

@app.route("/bacnet", methods=["GET", "POST"])
def bacnet_page():
    if request.method == "POST":
        devices = whois_scan(timeout=5)
        # Save to CSV
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(OUTPUT_DIR, f"bacnet_scan_{timestamp}.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["device_instance", "address"])
            writer.writeheader()
            writer.writerows(devices)
        return render_template("bacnet.html", results={"devices": devices, "csv": csv_path})
    return render_template("bacnet.html", results={"devices": [], "csv": None})

@app.route("/bacnet_deep_scan", methods=["POST"])
def bacnet_deep_scan():
    device_instance = request.form.get("device_instance")
    address = request.form.get("address")
    results = deep_scan(device_instance, address)
    # Save to CSV
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"deep_scan_{device_instance}_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["object_type", "instance", "property", "value"])
        writer.writeheader()
        writer.writerows(results)
    return render_template("deep_scan_result.html", results=results, csv=csv_path)

# --- Example: Download CSV Route (optional, if you want to serve CSVs directly) ---
@app.route("/download/<filename>")
def download_file(filename):
    return send_file(os.path.join(OUTPUT_DIR, filename), as_attachment=True)

# --- Add your other routes (network, index, etc.) below ---

if __name__ == "__main__":
    print("Flask app started!")
    app.run(host="0.0.0.0", port=80)
