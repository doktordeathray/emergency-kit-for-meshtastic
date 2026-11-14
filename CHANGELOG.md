# Changelog

Every release of the Emergency Kit for Meshtastic, newest first. The version of the kit you have is in the file `VERSION`.

## 0.2.14 (2026-11-13)

- Fixed: after a new kit came out, restarting the start window could still say nothing, because it reused the "up to date" answer from its last check (kept for 6 hours). Now every time the start window opens it also asks, with one quick request, whether a newer kit is out, and shows "UPDATES AVAILABLE: this kit (v…)" straight away. The full check of firmware and apps is still reused for 6 hours.

## 0.2.13 (2026-11-13)

- New in the start window's menu: **K  Copy this kit to another USB or external drive**. It copies everything on this drive to the other one (no internet needed), and offers "The same as this drive" so it copies the same parts and offline map area. It can format the other drive as exFAT first, like setup.
- Windows USB drivers during **U**: if both are already on the drive, the step is skipped ("both drivers already on the drive"). If one is missing, U no longer prints download errors; at the end it offers to open the download pages and lets you drag the files into the window, the same as setup.

## 0.2.12 (2026-11-13)

- The start window now checks for updates by itself when it opens (quietly, in the background, if the computer is online). If anything is newer, a flashing line appears right under the title, for example ">> UPDATES AVAILABLE: Firmware (stable), Web app. Press U (needs internet) <<". The answer is reused for 6 hours, so restarting doesn't ask GitHub again and again.
- Fixed: every update downloaded esptool again (about 320 MB) even when that version was already on the drive. It's now skipped when it's up to date, like the other parts.
- Start page: the Meshtastic documentation section is now below the quick links (First time, How to flash, Firmware files, Phones, Raspberry Pi, Something wrong?).

## 0.2.11 (2026-11-13)

- Fixed: **All docs** on the start page and the flasher's docs links showed a list of folders instead of the Meshtastic docs. meshtastic.org sends /docs/ on to the Introduction page from its server, which a drive can't do, so the kit now adds a small page that does it. Press U to fix an existing drive (the docs aren't downloaded again).
- Future offline docs builds also turn all of meshtastic.org's other redirects into pages, so old links inside the docs keep working.

## 0.2.10 (2026-11-13)

- The "offline copy" notice on the web flasher, web app and docs is now a yellow banner across the top of the page, in bold, so it's hard to miss: "OFFLINE COPY: from Emergency Kit for Meshtastic (an independent project), modified to work from this drive. Not an official Meshtastic service. Details". The page moves down to make room, so nothing is hidden behind it, and an × on the right closes it (until that browser tab is closed).

## 0.2.9 (2026-11-13)

- New in the standard kit: the **Meshtastic documentation** (meshtastic.org/docs) as an offline copy, about 210 MB. The start page has a new **Meshtastic documentation** section with quick links (getting started, radio settings, modules, supported radios, apps, FAQ, everything). The flasher's links to the docs open the copy on the drive. Existing drives get it the next time you press U.
- The docs are built from their open-source code (GPL-3.0) with usage tracking and the online search removed; inside them, links to Meshtastic's online flasher and web app go to the copies on the drive.
- The web flasher, web app and docs on the drive show a small notice: "Offline copy from Emergency Kit for Meshtastic (independent project), modified to work from this drive. Not an official Meshtastic service." with a Details link to the list of changes. It can be closed.

## 0.2.8 (2026-11-13)

- The kit is now called **Emergency Kit for Meshtastic** everywhere you see it: the start page, the guide, the start window's header and title, setup, and READ-ME-FIRST.txt (it used to say "Meshtastic Emergency USB" in places). It's an independent project, not made or endorsed by Meshtastic LLC, and the name makes that clearer.
- New start page icon: a USB drive, replacing an "M" mark that looked like Meshtastic's own logo.
- The download's file name is unchanged (Meshtastic-Emergency-Kit-Setup-…zip), so pressing U keeps working on existing drives.

## 0.2.7 (2026-11-13)

- New in the start window's menu: **R  Restart this window**. It stops the start window's servers and starts it again from the drive, in the same window, so an updated kit takes over without closing the window and running the start file again. Browser tabs keep working; the browser only opens the start page again when the kit's version changed.
- After **U** updates the kit itself, the start window offers to restart straight away.

## 0.2.6 (2026-11-13)

- Fixed: after an update, the browser could keep showing an old copy of the start page for days, so changes (like opening the web app in a new tab) didn't appear. The kit's local web server now tells the browser to always check for a newer page, and the start window opens the start page at an address that includes the kit version.
- **Use Meshtastic**, the **web flasher** and **Firmware files** open in a new tab, so the start page stays open in its own tab. (0.2.5's separate pop-up windows are replaced by plain new tabs.)
- If another start window is already running from a different copy of the kit, the start window now says so, instead of quietly showing that copy's pages.

## 0.2.5 (2026-11-13)

- On the start page, **Use Meshtastic** and the **web flasher** now open in their own browser windows, not as tabs, so the start page stays where it is. If the browser blocks new windows, they open as a new tab instead.
- The firmware pages now list the ESP32 radios too (Heltec V3/V4, T-Beam, T-Deck, Station G2 and the rest: 77 in stable, 92 in alpha), each with a link to the web flasher, which is how they're installed, and the file for esptool. The search box finds radios in both lists.
- Builds are explained where a radio has more than one: MUI (full colour touch-screen interface), InkHUD (for e-ink screens), OLED/TFT/e-ink display versions, battery sizes and board revisions. Boards newer than the flasher's device list still get a readable name.

## 0.2.4 (2026-11-13)

- Firmware files: instead of a bare list of hundreds of files, **Firmware files** on the start page now opens a page for each firmware version (stable first). It lists every drag-and-drop radio (nRF52 and Raspberry Pi Pico) by its real name, with its chip and a Download button, plus a search box, step-by-step instructions, which factory-erase file fits your radio, and what the other kinds of files are for. Radios with several builds (e.g. RAK4631 normal / e-ink / Ethernet, InkHUD versions) say which is which.
- On the start page, **Use Meshtastic**, the **flasher** and **Firmware files** now open in a new window, so the start page stays open.
- The pages are made on the drive from the flasher's device list, and are rebuilt whenever U updates the firmware.

## 0.2.3 (2026-11-13)

- Fixed (Mac and Linux): in 0.2.2, sending the Android app over Wi-Fi didn't show the QR codes. They're back. The server's own "Quit by pressing CTRL-C" line shows again too, but Ctrl+C (like Enter) still only stops sharing and goes back to the menu, and the last line says so.

## 0.2.2 (2026-11-13)

- Sending the Android app over Wi-Fi: the screen with the QR codes now ends with "press Enter to stop and go back to the menu". The server's own "Quit by pressing CTRL-C" message is gone, and pressing Ctrl+C (or Esc on Windows) also just stops sharing and goes back to the menu, instead of closing the whole start window.
- Offline map: the "Map © OpenStreetMap contributors" credit is no longer shown twice. The web app shows its own credit on the map, so the kit's extra one (which covered the page footer) only appears if that's missing.

## 0.2.1 (2026-11-13)

- U now updates the kit itself too: the start windows, setup, the updater and the guides. It downloads the newest release, checks it against the SHA-256 fingerprint GitHub publishes (and refuses it if it doesn't match), replaces only the kit's own files that changed, keeps this drive's settings and downloads, shows what's new, then updates the parts with the new updater.
- The start page's update notice also says when a newer kit is out.
- Drives made with a kit older than 0.2.1 can't do this yet: download the newest kit once, run its setup and pick the drive. From then on, U keeps the kit current.

## 0.2.0 (2026-11-13)

- New optional extra: **offline map**. In setup, type a town or city (or coordinates) and how far around it; setup shows the size, then saves a map of that area on the drive. The web app then shows your nodes on that map with no internet. Pressing U refreshes the map every few months. Map data © OpenStreetMap contributors, via Protomaps.
- Fixed the web app's map, with or without the offline map: the Meshtastic web client release (v2.7.2) bundles MapLibre 6 but leaves out the worker files it needs, so its map couldn't draw anything. Setup and U now add the official MapLibre files for that exact version. The changes are listed in `_system/webclient/CHANGES-BY-THE-KIT.txt` on the drive.
- The web app's own offline cache is switched off on the drive, so it always uses the files on the drive.

## 0.1.9 (2026-11-13)

- Fixed: if the start window had been open a while, sending the Android app over Wi-Fi (or reopening the browser pages) could fail with `miniserve-mac-arm64: No such file or directory`. macOS clears temporary folders, and the start window kept using a copy of the web server that was gone. It now checks the copy is still there and makes a new one if not.

## 0.1.8 (2026-11-13)

- Fixed: on a Mac, choosing 1 in the start window could fail with `Killed: 9` and no browser page. The start window copies the web server program to a temporary folder before running it, and replaced an older copy there in place, which macOS refuses to run. It now swaps in a fresh copy instead, and if a copy left by an older version won't start, it replaces it automatically.

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
