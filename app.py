from flask import Flask, render_template, request, redirect, url_for, send_file
from threading import Thread
import subprocess, csv, datetime, os, re, socket
from mac_vendor_lookup import MacLookup

# Import our scanners
from bacnet_scan import bacnet_scan, deep_scan_device

app = Flask(__name__)

OUTPUT_DIR = "/home/makeitworkok/TTTv1.0.2/results"
os.makedirs(OUTPUT_DIR, exist_ok=True)
SCAN_CONFIG_FILE = "/home/makeitworkok/TTTv1.0.2/scan_range.txt"

def get_scan_range():
    if not os.path.exists(SCAN_CONFIG_FILE):
        return "10.46.12.0/24"
    with open(SCAN_CONFIG_FILE, "r") as f:
        return f.read().strip()

def set_scan_range(new_range):
    with open(SCAN_CONFIG_FILE, "w") as f:
        f.write(new_range.strip())

# --- ARP Scan ---
def run_arp_scan_with_range(subnet, repeats=10):
    devices_dict = {}
    mac_lookup = MacLookup()
    for _ in range(repeats):
        try:
            result = subprocess.run(
                ["sudo", "arp-scan", "--interface", "eth0", subnet],
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
                        vendor = mac_lookup.lookup(mac)
                    except Exception:
                        vendor = ""
                    # Use MAC as unique key (or IP if you prefer)
                    if mac not in devices_dict:
                        devices_dict[mac] = [ip, mac, hostname, vendor]
                    else:
                        # Optionally merge hostname/vendor if missing
                        if not devices_dict[mac][2] and hostname:
                            devices_dict[mac][2] = hostname
                        if not devices_dict[mac][3] and vendor:
                            devices_dict[mac][3] = vendor
        except Exception:
            continue

    devices = list(devices_dict.values())

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"arp_scan_{timestamp}.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["IP Address", "MAC Address", "Hostname", "Vendor"])
        writer.writerows(devices)
    return devices, csv_path

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

    # Get current live IP and Gateway
    current_ip = subprocess.getoutput("ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'")
    current_ip = current_ip.splitlines()[0] if current_ip else ""
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
scan_results = {"devices": [], "csv": None, "scanning": False, "time": 0}

def run_bacnet_scan():
    global scan_results
    scan_results["scanning"] = True
    scan_results["devices"], scan_results["csv"] = bacnet_scan()
    scan_results["scanning"] = False

@app.route("/bacnet", methods=["GET", "POST"])
def bacnet_page():
    global scan_results
    if request.method == "POST" and not scan_results["scanning"]:
        t = Thread(target=run_bacnet_scan)
        t.start()
        scan_results["time"] = 5
    return render_template("bacnet.html", results=scan_results)

@app.route("/bacnet_deep_scan", methods=["POST"])
def bacnet_deep_scan():
    try:
        device_instance = request.form.get("device_instance")
        address = request.form.get("address")
        print(f"Deep scan requested for device_instance={device_instance}, address={address}")
        results, csv_path = deep_scan_device(int(device_instance), address)
        for d in scan_results["devices"]:
            if str(d["device_instance"]) == str(device_instance):
                d["deep_csv"] = csv_path
        return redirect(url_for("bacnet"))
    except Exception as e:
        print("Error in /bacnet_deep_scan:", e)
        return "Internal Server Error: " + str(e), 500

# Use this destination in your ReadPropertyRequest, etc.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)

# In bacnet_scan.py, inside deep_scan_device
DEEP_SCAN_PORT = 47809  # Any unused UDP port

device = LocalDeviceObject(
    objectName="TTTv1DeepScanner",
    objectIdentifier=DEVICE_ID + 1,
    maxApduLengthAccepted=1024,
    segmentationSupported="segmentedBoth",
    vendorIdentifier=15,
)
app = BIPSimpleApplication(device, Address(f"{local_ip}:{DEEP_SCAN_PORT}"))