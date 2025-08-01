# TTTv1.0.2 Dashboard

A web-based dashboard for network scanning, BACnet device discovery, and network configuration.  
Designed for easy deployment on Linux (e.g., Raspberry Pi).

---

## Features

- **Network Scan:** Scan your local subnet for devices using ARP.
- **BACnet Scan:** Discover BACnet devices and perform deep scans.
- **Network Settings:** Configure static/DHCP IP for `eth0`.
- **CSV Export:** Download scan results as CSV files.
- **Easy Setup:** No background threads or global state; uses a singleton BACnet app.
- **Optional Wi-Fi Access Point:** Turn your device into an open Wi-Fi AP for direct access.

---

## Requirements

- **Python 3.7+**
- **Linux (Raspberry Pi 4 64-bit Lite, Bullseye recommended)**
- **Packages:**
  - `flask`
  - `bacpypes`
  - `mac-vendor-lookup` (optional, for vendor info)
- **System tools:**
  - `arp-scan` (`sudo apt-get install arp-scan`)
  - `hostapd` and `dnsmasq` (if you want to run as a Wi-Fi AP)

---

## Installation

```sh
git clone https://github.com/yourrepo/TTTv1.0.2.git
cd TTTv1.0.2
pip install -r requirements.txt
sudo apt-get install arp-scan
```

---

## Usage

```sh
sudo python3 app.py
```
- Visit `http://<device-ip>:80` in your browser.

---

## Network Scan

- Go to **Network Scan** tab.
- Click **Start Scan** to scan your subnet.
- Results show IP, MAC, Hostname, Vendor.
- Download results as CSV.

---

## BACnet Scan

- Go to **BACnet Scan** tab.
- Click **Start BACnet Scan** to discover BACnet devices.
- Click **Deep Scan** for any device to view all objects/properties.
- Download results as CSV.

---

## Network Settings

- Go to **Network Settings** tab.
- Set static IP or switch to DHCP for `eth0`.
- Changes are applied to `/etc/dhcpcd.conf` and take effect after restarting the `dhcpcd` service.

---

## Wi-Fi Access Point (Optional)

To make your device an open Wi-Fi AP (`tttv1`):

1. **Install required packages:**
   ```sh
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
Connect to it and access the dashboard at `http://192.168.50.1`.**

---

## Troubleshooting

- **ARP Scan not working:** Make sure `arp-scan` is installed and run as root.
- **BACnet Scan errors:** Ensure only one BACnet app instance is running.
- **Network config not applying:** Check `/etc/dhcpcd.conf` and restart `dhcpcd`.
- **Wi-Fi AP not showing:** Check hostapd and dnsmasq configs, and use correct interface.
- **IP not changing:** Make sure no other network manager is controlling `eth0` and check for errors in `dhcpcd` status.

---

## Project Structure

```
TTTv1.0.2/
├── app.py                # Main Flask app and routes
├── bacnet_core.py        # BACnet singleton and scan logic
├── requirements.txt      # Python dependencies
├── templates/            # HTML templates for Flask
│   ├── index.html
│   ├── network.html
│   ├── bacnet.html
│   ├── deep_scan_result.html
│   └── ... (other pages)
├── results/              # CSV output files from scans
│   └── bacnet_scan_*.csv
│   └── deep_scan_*.csv
│   └── arp_scan_*.csv
├── static/               # Static files (CSS, JS, images)
├── README.md             # This documentation
└── ...                   # Other supporting files
```

---

## Contributing

Pull requests welcome!

---

## License

MIT