from flask import Flask, render_template, request, redirect, url_for, send_file
import subprocess, csv, datetime, os, re, socket
import asyncio
import ipaddress

from bac0_scan import bacnet_scan, bacnet_quick_scan, export_to_csv

app = Flask(__name__)

# Use project-relative results dir (or override via TTT_RESULTS_DIR)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("TTT_RESULTS_DIR", os.path.join(BASE_DIR, "results"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Absolute path (systemd often lacks /usr/sbin in PATH)
ARP_SCAN_BIN = os.environ.get("ARP_SCAN_BIN", "/usr/sbin/arp-scan")
BACNET_UDP_PORT = int(os.environ.get("BACNET_UDP_PORT", "47808"))

# File to store the selected scan range for ARP scan
SCAN_RANGE_FILE = "/tmp/scan_range.txt"

# Get the current IP address of eth0
def get_eth0_ip():
    ip = subprocess.getoutput("ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'")
    return ip.splitlines()[0] if ip else ""

def get_up_interface(preferred="eth0"):
    """Prefer eth0; fall back to wlan0 if it's the only active link."""
    for iface in (preferred, "wlan0"):
        state = subprocess.getoutput(f"cat /sys/class/net/{iface}/operstate 2>/dev/null").strip()
        if state == "up":
            return iface
    return preferred

def get_iface_cidr(iface):
    """Return first IPv4 CIDR on iface, e.g. 192.168.50.1/24, or ''."""
    return subprocess.getoutput(
        f"ip -4 -o addr show {iface} | awk '{{print $4}}' | head -n1"
    ).strip()

def pick_interface_for_subnet(subnet_cidr):
    """
    Pick eth0/wlan0 whose IP is inside the requested subnet.
    Falls back to get_up_interface if no exact match.
    """
    try:
        target_net = ipaddress.ip_network(subnet_cidr, strict=False)
    except Exception:
        return get_up_interface("eth0")
    for iface in ("eth0", "wlan0"):
        cidr = get_iface_cidr(iface)
        if not cidr:
            continue
        try:
            if ipaddress.ip_interface(cidr).ip in target_net:
                state = subprocess.getoutput(f"cat /sys/class/net/{iface}/operstate 2>/dev/null").strip()
                if state == "up":
                    return iface
        except Exception:
            pass
    return get_up_interface("eth0")

# Run ARP scan on the specified subnet, repeat for reliability
def run_arp_scan_with_range(subnet, repeats=10):
    """Run arp-scan on the chosen subnet and return (devices, csv_path, error)."""
    devices_dict = {}
    error = None
    try:
        from mac_vendor_lookup import MacLookup
        mac_lookup = MacLookup()
    except Exception as e:
        print("MacLookup import failed:", e)
        mac_lookup = None

    # Choose interface that actually belongs to the subnet
    iface = pick_interface_for_subnet(subnet)

    if not os.path.exists(ARP_SCAN_BIN):
        error = f"arp-scan not found at {ARP_SCAN_BIN}"
        print(error)
        return [], None, error

    # Ensure iface is up
    if subprocess.getoutput(f"cat /sys/class/net/{iface}/operstate 2>/dev/null").strip() != "up":
        error = f"Interface {iface} is down. Bring link up and try again."
        print(error)
        return [], None, error

    # No sudo; rely on setcap on /usr/sbin/arp-scan
    base_cmd = [ARP_SCAN_BIN, "--interface", iface, subnet]
    print("ARP-SCAN CMD:", " ".join(base_cmd), "euid=", os.geteuid())

    for _ in range(repeats):
        try:
            result = subprocess.run(base_cmd, capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and ":" in parts[1] and parts[0][0].isdigit():
                    ip, mac = parts[0], parts[1]
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        hostname = ""
                    try:
                        vendor = mac_lookup.lookup(mac) if mac_lookup else ""
                    except Exception:
                        vendor = ""
                    devices_dict.setdefault(mac, [ip, mac, hostname, vendor])
        except subprocess.CalledProcessError as e:
            msg = e.stderr or e.stdout or str(e)
            print("ARP scan failed:", msg)
            if "must be root" in msg.lower() or "operation not permitted" in msg.lower():
                error = "arp-scan needs privileges. Run: sudo setcap cap_net_raw,cap_net_admin+eip /usr/sbin/arp-scan"
            else:
                error = msg
            break
        except Exception as e:
            error = str(e)
            print("ARP scan failed:", error)
            break

    devices = list(devices_dict.values())
    csv_path = None
    if devices:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(OUTPUT_DIR, f"arp_scan_{timestamp}.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["IP Address", "MAC Address", "Hostname", "Vendor"])
            writer.writerows(devices)

    return devices, csv_path, error

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
    subnet = get_scan_range()
    devices, csv_path, error = [], None, None

    if request.method == "POST":
        if "octet" in request.form:
            base_ip = request.form.getlist("octet")
            cidr = request.form.get("cidr", "24")
            subnet = ".".join(base_ip) + f"/{cidr}"
            set_scan_range(subnet)
        else:
            # Run scan
            devices, csv_path, error = run_arp_scan_with_range(subnet)

    base_ip, cidr = subnet.split("/")
    return render_template(
        "scan.html",
        devices=devices,
        csv_path=csv_path,
        base_ip=base_ip.split("."),
        cidr=cidr,
        error=error,
        eth0_active=is_eth0_active(),
    )

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
    error = None
    results = {}
    udp_port = BACNET_UDP_PORT

    # determine source IP/mask as you already do (example using eth0 IP)
    eth0_ip = get_eth0_ip()
    if (eth0_ip):
        ip_with_mask = f"{eth0_ip}/24"
    else:
        ip_with_mask = ""

    if request.method == "POST":
        # read UDP port from form, fallback to env default
        try:
            udp_port = int(request.form.get("udp_port", udp_port))
            if udp_port < 1024 or udp_port > 65535:
                udp_port = BACNET_UDP_PORT
        except Exception:
            udp_port = BACNET_UDP_PORT

        if not ip_with_mask:
            error = "No IP on eth0. Connect and try again."
        else:
            scan_type = request.form.get("scan_type", "full")
            try:
                if scan_type == "quick":
                    scan_results, networks_found = asyncio.run(
                        bacnet_quick_scan(ip_with_mask, return_networks=True, udp_port=udp_port)
                    )
                else:
                    scan_results, networks_found = asyncio.run(
                        bacnet_scan(ip_with_mask, return_networks=True, udp_port=udp_port)
                    )

                # Only keep one entry per unique device_instance
                unique_devices = {}
                for d in scan_results:
                    inst = d.get("device_instance")
                    if inst is not None and inst not in unique_devices:
                        unique_devices[inst] = d

                results = {
                    "devices": [
                        {
                            "device_instance": d.get("device_instance"),
                            "address": d.get("device_ip"),
                            "vendorName": d.get("vendorName", "-"),
                            "modelName": d.get("modelName", "-"),
                        }
                        for d in unique_devices.values()
                    ],
                    "csv": export_to_csv(scan_results) if scan_results else None,
                    "networks_found": networks_found,
                    "device_count": len(unique_devices),
                }
            except Exception as e:
                import traceback
                print("BACnet scan failed:", e)
                print(traceback.format_exc())
                error = f"BACnet scan failed: {e}"

    return render_template(
        "bacnet.html",
        error=error,
        eth0_active=is_eth0_active(),
        udp_port=udp_port,
        results=results,
    )

@app.route("/download_csv")
def download_csv():
    # Download CSV by path (legacy, not used in main flow)
    path = request.args.get("path")
    return send_file(path, as_attachment=True)

# --- Add your other routes (network, index, etc.) below ---

def is_eth0_active():
    """True if eth0 link is up."""
    return subprocess.getoutput("cat /sys/class/net/eth0/operstate 2>/dev/null").strip() == "up"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))  # was 80; default to 8080
    print(f"Flask app started on port {port}!")
    app.run(host="0.0.0.0", port=port)
