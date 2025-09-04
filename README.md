# TTTv1.0.2 Dashboard

> 🚀 **Platform Testing Update**  
> We’re currently putting the **Radxa Zero 3e** through its paces as a potential platform of choice for this project!  
> It’s looking promising, but we want to make sure it meets all our needs—so expect plenty of tinkering and testing before we make anything official.  
>
> **Interested in helping out with testing?**  
> I’d love some extra hands (and hardware!) on deck. If you’re curious or want to help, please reach out!
>

My name is Chris Favre, project manager and evangelist of all things HVAC. Over the years I've seen the industry change from pneumatic to DOS and text based, graphical programming, and web based solutions. As time has evolved, we have a great need for easy to use toolsets to keep our technicians and account managers up to date. Who still remembers Hayes commands, ATDT8675309? 

This project began as a way to bridge a gap I kept seeing in the field, many HVAC controls technicians and account managers aren't deeply familiar with IT or systems integration. I’ve spent a lot of time trying to make this tool practical, accessible, and field-ready. My hope is that it can make networking and BACnet diagnostics easier for those of us who didn’t come up through the IT side of the house. If it helps you or your team get a clearer picture of what’s going on in the network, then it’s doing its job.

A web-based dashboard for network scanning, BACnet device discovery (with deep scan), and network configuration.  
Built with simplicity in mind, especially for those working in the trenches of HVAC controls and building automation. It’s meant to run cleanly on a Raspberry Pi with minimal setup.

---

## Features

- **Network Scan:** Scan your local subnet for devices using ARP.
- **BACnet Scan:** Discover BACnet devices and automatically perform a deep scan (all objects/points and properties are collected in one scan).
- **Adjustable BACnet UDP Port:** Default is 47808; change per-scan in the UI or set a default via env var.
- **Network Settings:** Configure static/DHCP IP for `eth0`.
- **CSV Export:** Download scan results as CSV files, with consistent column order.
- **Live Device/Network Info:** See networks found and device count after each scan.
- **Progress Feedback:** "Please wait" message or spinner shown during BACnet scan.
- **Easy Setup:** No background threads or global state; uses a singleton BACnet app.
- **Optional Wi-Fi Access Point:** Turn your device into an open Wi-Fi AP for direct access.
- **Local Hostname Access:** Access the dashboard at `http://tttv1.local` instead of an IP address.

---

## Requirements

- Python 3.7+
- Linux (Raspberry Pi OS Bullseye recommended)
- Python packages:
  - flask
  - BAC0
  - bacpypes
  - mac-vendor-lookup (optional)
  - netifaces (optional)
- System tools:
  - arp-scan
  - libcap2-bin (to grant capabilities to arp-scan)
  - avahi-daemon (for .local hostname access)
  - hostapd and dnsmasq (optional, for Wi‑Fi AP)

---

## Installation

```sh
# Get code
git clone https://github.com/yourrepo/TTTv1.0.2.git
cd TTTv1.0.2

# System packages
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip arp-scan libcap2-bin avahi-daemon

# Allow arp-scan to run without sudo (raw sockets)
sudo setcap cap_net_raw,cap_net_admin+eip "$(which arp-scan)"
getcap "$(which arp-scan)"   # expect: cap_net_admin,cap_net_raw+eip

# (Optional) Python venv
python3 -m venv .venv
. .venv/bin/activate

# Python deps
pip install -r requirements.txt
```

---

## Usage (manual)

```sh
# In project folder
export PORT=8080
# Optional defaults:
# export BACNET_UDP_PORT=47808   # Default BACnet port (change if your site uses a non-standard port)
# export TTT_RESULTS_DIR=/home/makeitworkok/TTTv1.0.2/results
python3 app.py
```

Open http://127.0.0.1:8080 (or the device IP on port 8080).  
If you must use port 80, run via systemd with CAP_NET_BIND_SERVICE (see below).

---

## Accessing the Dashboard via `tttv1.local`

This project is configured to be accessible at `http://tttv1.local` on your network, so you don't need to remember the device's IP address.

**How it works:**
- The Raspberry Pi runs the `avahi-daemon` service, which advertises its hostname on the local network using mDNS (Bonjour/ZeroConf).
- By default, the Pi's hostname is set to `tttv1`. You can check or set it with:
  ```sh
  sudo hostnamectl set-hostname tttv1
  sudo systemctl restart avahi-daemon
  ```
- Any computer or phone on the same network can access the dashboard at `http://tttv1.local`.

**Note:**  
- Most modern OSes (Windows 10+, macOS, Linux, iOS, Android) support `.local` hostnames out of the box.  
- If you have trouble, make sure `avahi-daemon` is running on the Pi and your client device supports mDNS.

---

## Network Scan

- Go to **Network Scan** tab.
- Click **Start Scan** to scan your subnet.
- Results show IP, MAC, Hostname, Vendor.
- Download results as CSV.

---

## BACnet Scan

- Go to **BACnet Scan** tab.
- Set the optional “BACnet UDP Port” (default 47808). This value applies to the current scan only.
- Click **Start Full Scan** or **Quick Scan**.
- After scan, you see networks found, device count, and can download CSV.

Tip:
- To change the default port globally (for all sessions), set environment variable `BACNET_UDP_PORT` (see systemd example below).
- Ensure firewalls allow the selected UDP port.

---

## Network Settings

- Go to **Network Settings** tab.
- Set static IP or switch to DHCP for `eth0`.
- Changes are applied to `/etc/dhcpcd.conf` and take effect after restarting the `dhcpcd` service.

---

## Setting up the Wi-Fi Access Point (AP) on Raspberry Pi

To make your device an open Wi-Fi AP (`tttv1`):

1. **Install required packages:**
   ```sh
   sudo apt-get update
   sudo apt-get install hostapd dnsmasq
   sudo systemctl stop hostapd
   sudo systemctl stop dnsmasq
   ```

2. **Configure `/etc/hostapd/hostapd.conf`:**
   ```
   interface=wlan0
   driver=nl80211
   ssid=tttv1
   hw_mode=g
   channel=6
   auth_algs=1
   wmm_enabled=0
   ignore_broadcast_ssid=0
   # No WPA settings for open network
   ```
   Set the config file location in `/etc/default/hostapd`:
   ```
   DAEMON_CONF="/etc/hostapd/hostapd.conf"
   ```

3. **Configure `/etc/dnsmasq.conf` for DHCP:**
   ```
   interface=wlan0
   dhcp-range=192.168.50.2,192.168.50.20,255.255.255.0,24h
   ```

4. **Set static IP for `wlan0` in `/etc/dhcpcd.conf`:**
   ```
   interface wlan0
       static ip_address=192.168.50.1/24
       nohook wpa_supplicant
   ```

5. **Enable IP forwarding and NAT:**
   ```sh
   sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
   sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
   ```
   To make IP forwarding permanent, add to `/etc/sysctl.conf`:
   ```
   net.ipv4.ip_forward=1
   ```

6. **Restart services:**
   ```sh
   sudo systemctl restart dhcpcd
   sudo systemctl start hostapd
   sudo systemctl start dnsmasq
   ```

**Your device will now broadcast an open Wi-Fi network named `tttv1`.  
Connect to it and access the dashboard at `http://192.168.50.1` or `http://tttv1.local`.**

---

## Troubleshooting

- **ARP Scan not working:** Make sure `arp-scan` is installed and run as root.
- **BACnet Scan errors:** Ensure only one BACnet app instance is running.
- **Network config not applying:** Check `/etc/dhcpcd.conf` and restart `dhcpcd`.
- **Wi-Fi AP not showing:** Check hostapd and dnsmasq configs, and use correct interface.
- **IP not changing:** Make sure no other network manager is controlling `eth0` and check for errors in `dhcpcd` status.
- **Can't access `tttv1.local`:** Ensure `avahi-daemon` is running and your client supports mDNS.
- ARP scan says “arp-scan needs privileges”:
  - Ensure caps are set: getcap /usr/sbin/arp-scan → cap_net_admin,cap_net_raw+eip
  - If you set NoNewPrivileges=true in the service, remove it (blocks file caps).
  - Alternative: grant caps via service instead of file caps:
    - AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN
    - CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN
- Service not starting:
  - sudo journalctl -u ttt.service -n 200 --no-pager
  - Verify paths and user in the unit file match your system.
- Can’t reach the app:
  - sudo ss -lntp | grep -E ':80|:8080'
  - curl -I http://127.0.0.1:8080
- arp-scan not found:
  - Install: sudo apt-get install -y arp-scan
  - Ensure correct path: which arp-scan → /usr/sbin/arp-scan
- BACnet devices not discovered on expected port:
  - Verify the device’s BACnet/IP port setting.
  - Set the port in the BACnet Scan page or via env: `BACNET_UDP_PORT=<port>`.
  - Ensure UDP is permitted on that port (switch/firewall).

---

## Project Structure

```
TTTv1.0.2/
├── app.py                # Main Flask app and routes
├── bac0_scan.py          # BACnet scan logic (deep scan built-in, uses BAC0)
├── requirements.txt      # Python dependencies
├── templates/            # HTML templates for Flask
│   ├── index.html        # Dashboard landing page
│   ├── network.html      # Network settings/configuration page
│   ├── bacnet.html       # BACnet scan and results page
│   ├── scan.html         # ARP network scan page
│   └── ...               # (other HTML pages)
├── results/              # CSV output files from scans
│   ├── bacnet_scan_*.csv
│   └── arp_scan_*.csv
├── static/               # Static files (CSS, JS, images, spinner, etc.)
├── README.md             # This documentation
└── ...                   # Other supporting files (legacy code, helpers, etc.)
```

---

## Contributing

Pull requests welcome!

---

## License

MIT

---
