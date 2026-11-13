# Changelog

Every release of the Emergency Kit for Meshtastic, newest first. The version of the kit you have is in the file `VERSION`.

## 0.1.7 (2026-11-13)

- Windows drivers on a Mac: Safari unzips the CP210x driver's .zip into a folder by itself. Setup now says so when it opens the download page, and explains how to keep the .zip: Control-click (or right-click) the download link and choose Download Linked File.
- If it was already unzipped, drag the `CP210x_Universal_Windows_Driver` folder into setup instead. Setup checks the folder is complete and puts it back into a .zip, with exactly the same files.

## 0.1.6 (2026-11-13)

- Windows USB drivers: their makers' websites block automatic downloads, so at the end setup now offers to open both download pages in your browser. Download the files, drag them into the setup window and press Enter, and setup puts them on the drive. You can drag both at once.
- Setup checks each dropped file is really the driver (not a web page or another file) and saves it with the name the Windows start window expects, even if your browser renamed it (for example `CH341SER (1).EXE`).
- Skipped it, or only got one file? Run setup again on the drive any time to add the rest.

## 0.1.5 (2026-11-13)

- The kit now has a version number. It's in the file `VERSION`, in the name of the download (`Meshtastic-Emergency-Kit-Setup-v0.1.5.zip`) and of the folder inside it, and setup and the start window show it.
- This changelog is included in the kit.
- Unzipping a new version no longer lands in the same folder as an older one, so old and new files can't get mixed.

## 0.1.4 (2026-11-13)

- Fixed: on a Mac, setup to an exFAT USB drive could stop with `webclient FAILED: No such file or directory: ... ._manifest.webmanifest.gz`. macOS adds hidden `._` helper files on exFAT drives; setup and the updater now skip them and clean them up.
- Making a drive from another drive no longer copies `._` files.
- On Windows, the start window ignores `._` files when picking an installer, the Android app or a driver.

## 0.1.3 (2026-11-13)

- Setup now shows the format of each USB drive. If it isn't exFAT (the format every computer can read), setup shows what's on the drive and offers to erase it and format it as exFAT. Nothing is erased until you type ERASE. You can also keep the drive as it is.
- Only external / USB drives are listed. The computer's own disk, and the drive setup is running from, are never offered.
- Formatting on Windows asks for admin permission; on Linux and Raspberry Pi it asks for your password and offers to install `exfatprogs` if needed. (Tested on a Mac; not yet on real Windows or Linux machines.)

## 0.1.2 (2026-11-11)

- Instructions say how to run SETUP on each computer instead of "double-click" everywhere: Terminal on a Mac, Run as a Program on Linux.
- READ-ME-FIRST.txt says the kit was made by doktordeathray in collaboration with Claude Code, Anthropic's AI coding assistant.
- A "Report a problem" form on GitHub.

## 0.1.1 (2026-11-11)

- Mac: instructions to run SETUP from Terminal, because recent macOS blocks double-clicking a downloaded script ("may contain malware"). Setup removes the block from everything it installs.
- Mac: Chromium is unblocked from System Settings, Privacy & Security, Open Anyway.
- Setup offers the standard kit, or the standard kit plus extras you pick (the 4.6 GB "Everything" option is gone). Picking a Raspberry Pi image adds Raspberry Pi Imager automatically.
- Windows USB drivers are checked by digital signature (WCH for CH340, Microsoft WHQL for CP210x) before installing. A driver that fails isn't installed.
- The web flasher includes its GPL licence and a list of the changes made to it.

## 0.1.0 (2026-11-11)

First early release.

- Small setup kit that downloads everything onto a USB drive, this computer, or a Raspberry Pi, from the official sources.
- Works offline afterwards: Meshtastic web client and web flasher with stable firmware for every supported board, served from the drive.
- Android app with sideloading over Wi-Fi (QR code), USB cable or file copy.
- Optional extras: Meshtastic desktop apps, Raspberry Pi images (mPWRD-OS, and Raspberry Pi OS Lite with an offline `meshtasticd` installer), Raspberry Pi Imager, alpha firmware, esptool.
- Chromium browser for Macs and Linux PCs without Chrome or Edge.
- Windows USB drivers (CH340, CP210x).
- Start windows for Windows, Mac and Linux, and an update option (U) for when you're online again.
