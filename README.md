# Emergency Kit for Meshtastic

**Set up Meshtastic when there's no internet.**

Meshtastic radios talk to each other without the internet. Setting them up usually needs it: the web flasher, the firmware and the apps all download at the moment you use them. This kit puts them on a USB drive while you still have a connection, so you can flash radios and install the apps anywhere later.

> Independent community project. Not made or endorsed by Meshtastic LLC. Meshtastic® is a registered trademark of Meshtastic LLC.

## Download

**[Meshtastic-Emergency-Kit-Setup-v0.2.10.zip](https://github.com/doktordeathray/emergency-kit-for-meshtastic/releases/download/v0.2.10/Meshtastic-Emergency-Kit-Setup-v0.2.10.zip)** (about 5 MB), from the [latest release](https://github.com/doktordeathray/emergency-kit-for-meshtastic/releases/latest).

Before opening it, compare its SHA-256 fingerprint with the one in the release notes:

| Computer | Command (run in the folder with the zip) |
|---|---|
| Windows (PowerShell) | `Get-FileHash .\Meshtastic-Emergency-Kit-Setup.zip` |
| Mac | `shasum -a 256 Meshtastic-Emergency-Kit-Setup.zip` |
| Linux / Raspberry Pi | `sha256sum Meshtastic-Emergency-Kit-Setup.zip` |

## How it works

**Before: while you still have internet**

1. Unzip the kit and run the setup file for your computer:
   - **Windows:** double-click `SETUP-WINDOWS.bat`.
   - **Mac:** macOS blocks double-clicking downloaded scripts ("may contain malware"). Open Terminal, type `bash` and a space, drag `SETUP-MAC.command` into the window, and press Enter. Setup removes the block from everything it installs, so `START-HERE-MAC.command` then opens with a double-click.
   - **Linux / Raspberry Pi:** right-click `SETUP-LINUX.sh` → Run as a Program, or run `bash SETUP-LINUX.sh`.
2. Choose **where** (a USB drive, this computer, or this Raspberry Pi) and **what**: the standard kit (about 1.5 GB), or the standard kit plus extras you pick. If the USB drive isn't exFAT, setup offers to erase it and format it as exFAT so every computer can read it. It only erases after you type ERASE.
3. Setup downloads the current releases from their official sources. To make more drives, run setup on a finished drive. It copies what it has, with no download needed.

**When there's no connection**

Plug the drive into any computer and double-click `START-HERE-WINDOWS.bat` or `START-HERE-MAC.command`. On Linux, right-click `START-HERE-LINUX.sh` and choose Run as a Program. A menu opens and your browser shows the web flasher and web client, served from the drive.

| Key | What it does |
|---|---|
| 1 | Open Meshtastic in the browser (web client and flasher) |
| 2 | Install the Meshtastic desktop app (extra) |
| 3 | Put the Android app on a phone: QR code over Wi-Fi, USB cable, or file copy |
| 4 | Make a Raspberry Pi SD card (extra) |
| 6 | Install USB drivers for radios (Windows) |
| C | Install a browser that works with radios (Mac, Linux) |
| U | Update the drive, when you're online again: the kit itself and every part on it |
| R | Restart the start window, e.g. after an update, without closing it |

## What setup downloads

**Standard kit (about 1.7 GB)**
- Meshtastic documentation: an offline copy of [meshtastic.org/docs](https://meshtastic.org/docs) (GPL-3.0), built by `make_docs.py` and published as the `offline-docs` download
- Meshtastic firmware (stable) for every supported board, laid out for the offline flasher
- Meshtastic web client
- Meshtastic Android app (F-Droid build)
- Chromium browser for Mac and Linux, from [ungoogled-chromium](https://github.com/ungoogled-software)
- Device pictures for the flasher, a local web server ([miniserve](https://github.com/svenstaro/miniserve)) and a portable Python ([python-build-standalone](https://github.com/astral-sh/python-build-standalone)) for the updater

**Optional extras**
- Meshtastic Desktop apps (Windows, Mac, Linux)
- Raspberry Pi images: [mPWRD-OS](https://github.com/mPWRD-OS/mPWRD-OS), and Raspberry Pi OS Lite with an offline install of `meshtasticd`
- Raspberry Pi Imager
- Newest alpha firmware
- [esptool](https://github.com/espressif/esptool)
- Offline map of an area you choose (a town or city and a distance around it), so the web app shows nodes on a map with no internet. Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), via [Protomaps](https://protomaps.com).

The kit also fixes the web app's map: the Meshtastic web client release bundles MapLibre 6 without the worker files it needs, so its map can't draw. Setup adds the official files for that MapLibre version (see `_system/webclient/CHANGES-BY-THE-KIT.txt` on a finished drive).

**Windows USB drivers** (CH340, CP210x): their makers' sites (WCH and Silicon Labs) block automatic downloads, so at the end setup opens both download pages in your browser. Download the two files and drag them into the setup window (on a Mac, Safari unzips the CP210x .zip by itself: Control-click the link and choose Download Linked File to keep it, or just drag in the unzipped folder); setup checks they're the real driver files (not a web page) and puts them on the drive. Before installing, the kit checks each driver's digital signature (WCH, and Microsoft WHQL for CP210x) and won't install one that fails.

Nothing from those projects is stored in this repository. Each person's computer downloads them from the official source.

## What's in this repository

- `SETUP-*`: sets up a drive. Double-click on Windows; on a Mac run it from Terminal (see above); on Linux run it as a program or with `bash`
- `START-HERE-*`: starts the kit on a finished drive. Double-click on Windows and Mac; on Linux run it as a program
- `_system/launcher.sh`, `_system/launcher.ps1`: the menus (Mac/Linux and Windows)
- `_system/maintenance/setup.py`: asks where and what, then copies or downloads
- `_system/maintenance/drives.py`: finds USB drives and formats one as exFAT (only after the person types ERASE)
- `_system/maintenance/build_usb.py`: downloads and updates every part (also used by `U`)
- `_system/maintenance/make_setup_kit.py`: builds the release zip from a full drive
- `_system/hub/`: the start page and offline guide
- `_system/flasher/`: a build of the [Meshtastic Web Flasher](https://github.com/meshtastic/web-flasher) (GPL-3.0), changed to read firmware from the drive and with usage tracking removed. See `_system/flasher/SOURCE-AND-CHANGES.txt`.
- `3-Raspberry-Pi/.../install.sh`: the one-command offline `meshtasticd` installer for Raspberry Pi OS

## Status

Early release. Built and tested on macOS. Windows, Linux and Raspberry Pi have been checked by reading the scripts, not yet on real machines. Please try your drive on each kind of computer you plan to use, and [report problems](https://github.com/doktordeathray/emergency-kit-for-meshtastic/issues).

## How this was made

This project is a collaboration between [doktordeathray](https://github.com/doktordeathray) and [Claude Code](https://claude.com/claude-code), Anthropic's AI coding assistant. AI was used throughout: it wrote most of the scripts, the offline guide, the web page and this README, with a person deciding what to build, testing it and reviewing the results. Treat it like any early-release software and check it on your own computers before you rely on it.

## Licence

GPL-3.0 (see `LICENSE`), the same licence as the Meshtastic Web Flasher included here. Downloaded parts keep their own licences.
