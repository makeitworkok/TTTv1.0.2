# TTTv1.0.2 Dashboard

This project began as a way to bridge a gap I kept seeing in the field, many HVAC controls technicians and account managers aren't deeply familiar with IT or systems integration. I’ve spent a lot of time trying to make this tool practical, accessible, and field-ready. My hope is that it can make networking and BACnet diagnostics easier for those of us who didn’t come up through the IT side of the house. If it helps you or your team get a clearer picture of what’s going on in the network, then it’s doing its job.

A web-based dashboard for network scanning, BACnet device discovery (with deep scan), and network configuration.  
Built with simplicity in mind, especially for those working in the trenches of HVAC controls and building automation. It’s meant to run cleanly on a Raspberry Pi with minimal setup.

---

## Features

- **Network Scan:** Scan your local subnet for devices using ARP.
- **BACnet Scan:** Discover BACnet devices and automatically perform a deep scan (all objects/points and properties are collected in one scan).
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
# Optional: override results location if desired
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
- Click **Start BACnet Scan** to discover BACnet devices and automatically perform a deep scan (all points/properties).
- While scanning, a "Please wait" message or spinner is shown.
- After scan, you see:
  - **Networks found**
  - **Device count**
  - **Unique devices** (one row per device instance)
- Download all results as CSV.

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

## Autostart on Boot (systemd)

To have the dashboard start automatically on boot, use a systemd service:

1. **Create the service file** `/etc/systemd/system/ttt.service` with the following contents:

    ```
    [Unit]
    Description=TTT Flask App
    After=network.target

    [Service]
    User=pi
    WorkingDirectory=/home/pi/TTTv1.0.2
    ExecStart=/usr/bin/python3 /home/pi/TTTv1.0.2/app.py
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target
    ```

2. **Enable and start the service:**
    ```sh
    sudo systemctl daemon-reload
    sudo systemctl enable ttt.service
    sudo systemctl start ttt.service
    ```

3. The dashboard will now start automatically at boot.  
   Check status with:
    ```sh
    sudo systemctl status ttt.service
    ```

**Tip:**  
Because no user is placed in the .service file, it will run as su.
To stop/start/enable/disable the service just run:
sudo systemctl ______ ttt.service

### Alternative: run on port 80
If you want plain http://<device-ip>/ (port 80), add binding capability to the service:

```ini
# Add to [Service]:
Environment=PORT=80
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
# Keep NoNewPrivileges unset
```

Then reload and restart the service.

---

## Autostart on Boot (systemd)

Create a service that runs as your user (makeitworkok) on port 8080.

```ini
# /etc/systemd/system/ttt.service
[Unit]
Description=TTT Flask App
After=network-online.target
Wants=network-online.target

[Service]
User=makeitworkok
Group=makeitworkok
WorkingDirectory=/home/makeitworkok/TTTv1.0.2
Environment=PYTHONUNBUFFERED=1
Environment=PORT=8080
Environment=TTT_RESULTS_DIR=/home/makeitworkok/TTTv1.0.2/results
Environment=ARP_SCAN_BIN=/usr/sbin/arp-scan
ExecStart=/usr/bin/python3 /home/makeitworkok/TTTv1.0.2/app.py
Restart=on-failure
RestartSec=2
# Note: do NOT set NoNewPrivileges=true if relying on arp-scan file capabilities.

[Install]
WantedBy=multi-user.target
```

Enable and start:
```sh
sudo systemctl daemon-reload
sudo systemctl enable --now ttt.service
sudo systemctl status ttt.service
```

Alternative (bind to port 80):
```ini
# Add to [Service]:
Environment=PORT=80
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
```
Reload and restart after changing the unit.

Alternative to file caps (if you can’t use setcap):
```ini
# Grant caps via service instead of file caps
AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN
CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN
```

---

## Access via tttv1.local
Ensure Avahi is running:
```sh
sudo systemctl enable --now avahi-daemon
sudo hostnamectl set-hostname tttv1
```
Then use http://tttv1.local:8080

---

## Hotspot / Wi‑Fi AP setup (optional)
Configure the device as an open AP on wlan0 (192.168.50.1/24) so clients can connect and reach the dashboard.

1) Install and stop services:
```sh
sudo apt-get install -y hostapd dnsmasq
sudo systemctl stop hostapd dnsmasq
```

2) Static IP for wlan0 (in /etc/dhcpcd.conf):
```
interface wlan0
    static ip_address=192.168.50.1/24
    nohook wpa_supplicant
```
Then:
```sh
sudo systemctl restart dhcpcd
```

3) DHCP (in /etc/dnsmasq.conf):
```
interface=wlan0
dhcp-range=192.168.50.2,192.168.50.200,255.255.255.0,24h
```

4) hostapd (in /etc/hostapd/hostapd.conf):
```
interface=wlan0
driver=nl80211
ssid=tttv1
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
# Open network (no WPA). Add WPA settings if you need security.
```
Point hostapd to that file:
```
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd
```

5) Optional internet sharing (NAT to eth0):
```sh
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
```

6) Start and enable:
```sh
sudo systemctl start hostapd dnsmasq
sudo systemctl enable hostapd dnsmasq
```

Connect to SSID tttv1 and open http://192.168.50.1:8080 (or http://tttv1.local:8080).

Notes:
- NAT is not required if you only need local access to the dashboard.
- Ensure the systemd service is running and listening on 0.0.0.0:8080.

---

## Troubleshooting
- ARP scan needs privileges:
  - sudo setcap cap_net_raw,cap_net_admin+eip /usr/sbin/arp-scan
  - getcap /usr/sbin/arp-scan → cap_net_admin,cap_net_raw+eip
  - If using service caps, add AmbientCapabilities/CapabilityBoundingSet as above.
- Service not starting:
  - sudo journalctl -u ttt.service -n 200 --no-pager
  - Confirm paths and User=makeitworkok
- Can’t reach the app:
  - sudo ss -lntp | grep -E ':80|:8080'
  - curl -I http://127.0.0.1:8080
- On AP but no page:
  - ip addr show wlan0 (expect 192.168.50.1/24)
  - Client must receive 192.168.50.x via DHCP
  - Ping 192.168.50.1 from client
- arp-scan not found:
  - which arp-scan → /usr/sbin/arp-scan

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