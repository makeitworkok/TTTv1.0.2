# TTTv1.0.2 Dashboard

A simple, modern web dashboard for Raspberry Pi that helps technicians scan and manage IP networks, including BACnet/IP devices.  
Built for ease of use in the field, with a mobile-friendly interface inspired by Trane's design language.

---

## Features

- **Network Scan:**  
  Scan your local network for connected devices, showing IP, MAC, Hostname, and Vendor (manufacturer) information.
- **Network Settings:**  
  View and configure the Pi's Ethernet settings (DHCP or static IP).
- **BACnet/IP Scan:**  
  Discover BACnet devices on your network and export results.
- **Responsive UI:**  
  Works great on mobile, desktop, and Raspberry Pi touchscreens.
- **Tabbed Dashboard:**  
  Modern tabbed interface for easy navigation (Network Scan, Network Settings, BACnet Scan, About).
- **CSV Export:**  
  Download scan results as CSV for reporting or further analysis.

---

## Screenshots

![Dashboard Screenshot](docs/screenshot_dashboard.png)  
*Add your own screenshots in the `docs/` folder!*

---

## Requirements

- Raspberry Pi (tested on Raspberry Pi OS 64-bit Lite, Bullseye)
- Python 3.7+
- Flask
- `arp-scan` (for network scanning)
- `mac-vendor-lookup` (for MAC vendor lookup)
- `bacnet_scan.py` (custom or third-party BACnet scanner module)
- sudo privileges (for network configuration and scanning)

---

## Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/yourusername/TTTv1.0.2.git
   cd TTTv1.0.2
   ```

2. **Install dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3-pip arp-scan
   pip3 install flask mac-vendor-lookup
   ```

3. **(Optional) Install BACnet/IP scanner dependencies:**  
   *(Edit this section based on your `bacnet_scan.py` requirements.)*

4. **Run the app:**
   ```bash
   sudo python3 app.py
   ```
   > **Note:** `sudo` is required for network scanning and configuration.

5. **Access the dashboard:**  
   Open a browser and go to `http://<raspberrypi-ip>/`

---

## Usage

- **Network Scan:**  
  Click "Network Scan" to see all devices on your subnet, including IP, MAC, Hostname, and Vendor.
- **Network Settings:**  
  Change between DHCP and static IP.  
  *Changing settings will restart the network interface.*
- **BACnet Scan:**  
  Scan for BACnet/IP devices and download results as CSV.
- **Touchscreen Kiosk Mode:**  
  To use the dashboard on a Pi touchscreen, launch Chromium in kiosk mode:
  ```bash
  chromium-browser --kiosk http://localhost/
  ```

---

## Project Structure

```
TTTv1.0.2/
├── app.py                # Main Flask app
├── bacnet_scan.py        # BACnet/IP scan logic
├── ttt_scan.py           # Standalone ARP scan script
├── templates/
│   ├── index.html
│   ├── network.html
│   ├── scan.html
│   └── bacnet.html
├── results/              # Scan results (CSV)
├── docs/                 # Screenshots and documentation
└── README.md
```

---

## Security Notes

- This tool is intended for use on trusted networks.
- Running as root is required for some features (network config, arp-scan).
- Do **not** expose this dashboard to the public internet.

---

## Change Log

- **2025-07-27:**  
  - Added hostname and vendor lookup to ARP scan results (requires `mac-vendor-lookup`).
  - Improved scan reliability by aggregating results from multiple scans.
  - Updated UI to use a tabbed, mobile-friendly layout inspired by Trane.com.
  - Added About tab and improved About content.
  - Added CSV export for scan results.
  - Added instructions for running the dashboard in kiosk mode on Raspberry Pi touchscreen.
  - Updated templates for consistent look and feel across all pages.

---

## Credits

- UI inspired by [Trane](https://trane.com)
- Created by MakeItWorkOK, 2025

---

## License

MIT License (see [LICENSE](LICENSE) file)