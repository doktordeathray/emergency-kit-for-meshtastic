#!/usr/bin/env bash
# Meshtastic Emergency USB - launcher for Mac and Linux.
# Started by START-HERE-MAC.command or START-HERE-LINUX.sh. Works fully offline.
# Written for bash 3.2 (the version macOS ships).

SYS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USB="$(dirname "$SYS")"
OS="$(uname -s)"
ARCH="$(uname -m)"
HUB_PORT=8470; CLIENT_PORT=8471; FLASHER_PORT=8472; SHARE_PORT=8473
WORK="${TMPDIR:-/tmp}/meshtastic-usb-$(id -u)"
mkdir -p "$WORK"
PIDS=""

B=$'\033[1m'; G=$'\033[1;32m'; Y=$'\033[1;33m'; R=$'\033[1;31m'; C=$'\033[1;36m'; N=$'\033[0m'

say()  { printf '%s\n' "$*"; }
ok()   { printf '%s\n' "${G}✔ $*${N}"; }
warn() { printf '%s\n' "${Y}! $*${N}"; }
fail() { printf '%s\n' "${R}✖ $*${N}"; }
pause(){ printf '\n%s' "Press Enter to go back to the menu..."; read -r _; }

# ---- find the right copy of a program for this computer --------------------
platform_suffix() {
  case "$OS-$ARCH" in
    Darwin-arm64)            echo "mac-arm64" ;;
    Darwin-*)                echo "mac-x64" ;;
    Linux-x86_64)            echo "linux-x64" ;;
    Linux-aarch64|Linux-arm64) echo "linux-arm64" ;;
    Linux-armv7l|Linux-armv6l) echo "linux-armv7" ;;
    *)                       echo "unknown" ;;
  esac
}
PLAT="$(platform_suffix)"

# USB drives are often mounted so programs can't run straight off them, and Macs
# quarantine files. So we copy small programs to a temp folder and run them there.
prepare_bin() {   # prepare_bin <source file>  -> prints runnable path
  local src="$1" dst="$WORK/$(basename "$1")"
  if [ ! -f "$dst" ] || [ "$src" -nt "$dst" ] || ! cmp -s "$src" "$dst"; then
    # Copy to a new file, then swap it in. Never overwrite a program in place: macOS
    # remembers a program it has run and kills it ("Killed: 9") if the file changes.
    cp "$src" "$dst.new.$$" 2>/dev/null || return 1
    mv -f "$dst.new.$$" "$dst" || return 1
  fi
  chmod +x "$dst" 2>/dev/null
  [ "$OS" = "Darwin" ] && xattr -d com.apple.quarantine "$dst" 2>/dev/null
  echo "$dst"
}

MINISERVE=""
server_runs() {   # quietly: does the prepared web server start at all?
  bash -c '"$0" --version; exit $?' "$MINISERVE" >/dev/null 2>&1
}
get_miniserve() {
  # Reuse the prepared copy only while it's still there (macOS clears temporary folders).
  [ -n "$MINISERVE" ] && [ -x "$MINISERVE" ] && return 0
  MINISERVE=""
  local src="$SYS/bin/miniserve-$PLAT"
  if [ ! -f "$src" ]; then
    if ! ls "$SYS/bin/"miniserve-* >/dev/null 2>&1; then
      fail "This kit isn't set up yet. Run SETUP first: in Terminal type  bash  and a space,"
      fail "drag SETUP-MAC.command into the window and press Enter"
      fail "(or SETUP-LINUX.sh on Linux) - it downloads everything (needs internet once)."
    else
      fail "This computer type ($OS $ARCH) isn't supported by the built-in server."
    fi
    return 1
  fi
  MINISERVE="$(prepare_bin "$src")" || { fail "Couldn't prepare the web server."; return 1; }
  if ! server_runs; then   # e.g. a broken copy left by an older version
    rm -f "$MINISERVE"
    MINISERVE="$(prepare_bin "$src")" || { fail "Couldn't prepare the web server."; return 1; }
    if ! server_runs; then
      fail "This computer won't run the kit's web server."; MINISERVE=""; return 1
    fi
  fi
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && { exec 3>&- 3<&-; return 0; }
  return 1
}

start_server() {  # start_server <port> <folder> <extra args...>
  local port="$1" dir="$2"; shift 2
  if port_in_use "$port"; then return 0; fi    # already running (another window)
  "$MINISERVE" -i 127.0.0.1 -p "$port" --index index.html -t "Meshtastic USB" "$@" "$dir" \
      >"$WORK/server-$port.log" 2>&1 &
  PIDS="$PIDS $!"
}

start_all() {
  get_miniserve || return 1
  start_server $HUB_PORT     "$SYS/hub"
  start_server $CLIENT_PORT  "$SYS/webclient" --spa \
      --header "Cross-Origin-Opener-Policy: same-origin" \
      --header "Cross-Origin-Embedder-Policy: require-corp"
  start_server $FLASHER_PORT "$SYS/flasher"
  local i=0
  while ! port_in_use $HUB_PORT && [ $i -lt 30 ]; do sleep 0.2; i=$((i+1)); done
  if port_in_use $HUB_PORT; then ok "Meshtastic is running on this computer (no internet needed)."
  else fail "The local server didn't start. Details: $WORK/server-$HUB_PORT.log"; return 1; fi
}

stop_all() {
  [ -n "$PIDS" ] && kill $PIDS 2>/dev/null
}
trap 'stop_all; exit 0' INT TERM HUP
trap 'stop_all' EXIT

# ---- open a web page in a browser that can talk to radios -------------------
# Web Serial / Web Bluetooth only exist in Chromium-family browsers. If the computer
# has none, we offer the open-source Chromium that's on this drive.
CHROMIUM_HOME="$HOME/.local/share/meshtastic-usb-chromium"

chromium_bin() {   # Linux: the copy we unpacked from the drive
  find "$CHROMIUM_HOME" -maxdepth 3 -type f -name chrome -perm -u+x 2>/dev/null | head -1
}

run_linux_chromium() {   # run_linux_chromium <url>
  local bin; bin="$(chromium_bin)"; [ -n "$bin" ] || return 1
  local opts=(--user-data-dir="$CHROMIUM_HOME/profile" --no-first-run --no-default-browser-check)
  nohup "$bin" "${opts[@]}" "$1" >"$WORK/chromium.log" 2>&1 &
  local pid=$!; sleep 4
  if ! kill -0 $pid 2>/dev/null; then
    # Some Linux setups (e.g. Ubuntu 24.04) block Chromium's sandbox for apps outside the
    # package manager. Only our own local pages are opened, so run without it.
    nohup "$bin" "${opts[@]}" --no-sandbox "$1" >"$WORK/chromium.log" 2>&1 &
  fi
  return 0
}

install_chromium() {   # returns 0 when a Chromium is ready to use
  say "Installing the Chromium browser from this drive (no internet needed)..."
  if [ "$OS" = "Darwin" ]; then
    local pat="arm64"; [ "$ARCH" = "arm64" ] || pat="x86_64"
    local dmg; dmg="$(ls "$USB/4-Chromium-Browser/Mac/"*"_${pat}-macos.dmg" 2>/dev/null | head -1)"
    [ -z "$dmg" ] && { fail "Chromium for this Mac isn't on the drive."; return 1; }
    local mnt; mnt="$(hdiutil attach -nobrowse -readonly "$dmg" 2>/dev/null | awk -F'\t' '/\/Volumes\//{print $NF}' | tail -1)"
    local app; app="$(ls -d "$mnt"/*.app 2>/dev/null | head -1)"
    [ -z "$app" ] && { fail "Couldn't open the Chromium installer."; return 1; }
    local dest="/Applications"; [ -w "$dest" ] || { dest="$HOME/Applications"; mkdir -p "$dest"; }
    rm -rf "$dest/Chromium.app"
    say "Copying Chromium to $dest (about 30 seconds)..."
    ditto "$app" "$dest/Chromium.app"; local rc=$?
    hdiutil detach "$mnt" -quiet 2>/dev/null
    [ $rc -ne 0 ] && { fail "Copy failed - is the disk full?"; return 1; }
    xattr -dr com.apple.quarantine "$dest/Chromium.app" 2>/dev/null
    ok "Chromium installed in $dest."
    return 0
  else
    local pat
    case "$PLAT" in linux-x64) pat="x86_64" ;; linux-arm64) pat="arm64" ;;
      *) fail "No Chromium on the drive for this computer type ($ARCH)."; return 1 ;; esac
    local tarf; tarf="$(ls "$USB/4-Chromium-Browser/Linux/"*"-${pat}_linux.tar.xz" 2>/dev/null | head -1)"
    [ -z "$tarf" ] && { fail "Chromium for this computer isn't on the drive."; return 1; }
    mkdir -p "$CHROMIUM_HOME"
    find "$CHROMIUM_HOME" -mindepth 1 -maxdepth 1 ! -name profile -exec rm -rf {} + 2>/dev/null
    say "Unpacking (about a minute)..."
    tar xJf "$tarf" -C "$CHROMIUM_HOME" || { fail "Unpacking failed - is the disk full?"; return 1; }
    local bin; bin="$(chromium_bin)"; [ -z "$bin" ] && { fail "Chromium didn't unpack correctly."; return 1; }
    mkdir -p "$HOME/.local/share/applications"
    printf '%s\n' "[Desktop Entry]" "Type=Application" "Name=Chromium (Meshtastic USB)" \
      "Exec=$bin --user-data-dir=$CHROMIUM_HOME/profile --no-first-run %U" \
      "Terminal=false" "Categories=Network;WebBrowser;" \
      > "$HOME/.local/share/applications/meshtastic-usb-chromium.desktop"
    ok "Chromium is ready (installed just for you, in your home folder)."
    return 0
  fi
}

offer_chromium() {   # offer_chromium <url>
  warn "This computer has no browser that can talk to radios (needs Chrome, Edge or Chromium)."
  printf 'Install the free Chromium browser from this drive now? [Y/n] '
  local a; read -r a
  case "$a" in n|N|no|No) return 1 ;; esac
  install_chromium || return 1
  if [ "$OS" = "Darwin" ]; then open -a Chromium "$1"; else run_linux_chromium "$1"; fi
  return 0
}

open_url() {
  local url="$1" app
  if [ "$OS" = "Darwin" ]; then
    for app in "Google Chrome" "Microsoft Edge" "Brave Browser" "Chromium" "Opera" "Vivaldi"; do
      if [ -d "/Applications/$app.app" ] || [ -d "$HOME/Applications/$app.app" ]; then
        open -a "$app" "$url"; return
      fi
    done
    offer_chromium "$url" && return
    warn "Opening Safari - you can read the guides, but it can't connect to radios."
    open "$url"
  else
    for app in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge \
               microsoft-edge-stable brave-browser vivaldi opera; do
      if command -v "$app" >/dev/null 2>&1; then
        nohup "$app" "$url" >/dev/null 2>&1 & return
      fi
    done
    if command -v flatpak >/dev/null 2>&1; then
      for app in com.google.Chrome org.chromium.Chromium com.microsoft.Edge com.brave.Browser io.github.ungoogled_software.ungoogled_chromium; do
        if flatpak info "$app" >/dev/null 2>&1; then nohup flatpak run "$app" "$url" >/dev/null 2>&1 & return; fi
      done
    fi
    [ -n "$(chromium_bin)" ] && run_linux_chromium "$url" && return
    offer_chromium "$url" && return
    warn "Opening your default browser - it may not be able to connect to radios."
    xdg-open "$url" >/dev/null 2>&1 &
  fi
}

do_chromium() {
  clear
  say "${B}Install the Chromium browser${N}  (free, open-source; works with radios)"
  say "Only needed if this computer has no Chrome or Edge."
  say
  if install_chromium; then
    if [ "$OS" = "Darwin" ]; then open -a Chromium "http://localhost:$HUB_PORT/"
    else run_linux_chromium "http://localhost:$HUB_PORT/"; fi
  fi
  pause
}

open_folder() { if [ "$OS" = "Darwin" ]; then open "$1"; else xdg-open "$1" >/dev/null 2>&1 & fi; }

linux_serial_check() {
  [ "$OS" = "Linux" ] || return 0
  if ! id -nG 2>/dev/null | grep -qwE 'dialout|uucp'; then
    warn "Your Linux user may not be allowed to use USB radios."
    say  "   If the radio won't connect, run this once, then log out and back in:"
    say  "   ${B}sudo usermod -aG dialout \$USER${N}"
  fi
}

# ---- menu actions -------------------------------------------------------------
not_included() {   # not_included "<what>" "<extra name in setup>"
  warn "$1 isn't included in this kit."
  say  "   To add it (needs internet): run SETUP again, pick this same drive,"
  say  "   choose ${B}2 - plus extras${N}, and select ${B}$2${N}."
}

do_open() {
  start_all && open_url "http://localhost:$HUB_PORT/"
  linux_serial_check
}

do_desktop() {
  clear; say "${B}Install the Meshtastic app on this computer${N}"; say
  if [ "$OS" = "Darwin" ]; then
    local dmg; dmg="$(ls "$USB/1-Desktop-App/Mac/"*.dmg 2>/dev/null | head -1)"
    [ -z "$dmg" ] && { not_included "The desktop app" "Desktop apps"; say "   Meanwhile, option 1 (the web app) does the same job."; pause; return; }
    if [ "$ARCH" != "arm64" ]; then
      warn "This Mac has an Intel chip. The desktop app may only run on Apple-chip Macs."
      warn "If it won't open, use option 1 (the web app) instead - it does the same job."
    fi
    say "Copying the app to your Applications folder..."
    local mnt; mnt="$(hdiutil attach -nobrowse -readonly "$dmg" 2>/dev/null | awk -F'\t' '/\/Volumes\//{print $NF}' | tail -1)"
    local app; app="$(ls -d "$mnt"/*.app 2>/dev/null | head -1)"
    if [ -n "$app" ] && cp -R "$app" /Applications/ 2>/dev/null; then
      local name; name="$(basename "$app")"
      hdiutil detach "$mnt" -quiet 2>/dev/null
      xattr -dr com.apple.quarantine "/Applications/$name" 2>/dev/null
      ok "Installed: /Applications/$name"
      open "/Applications/$name"
    else
      [ -n "$mnt" ] && open "$mnt"
      warn "Couldn't copy it automatically. A window opened: drag Meshtastic into Applications."
    fi
  else
    local pat="x86_64"; [ "$PLAT" = "linux-arm64" ] && pat="aarch64"
    local img; img="$(ls "$USB/1-Desktop-App/Linux/"*"$pat".AppImage 2>/dev/null | head -1)"
    if [ -z "$img" ]; then
      if ls "$USB/1-Desktop-App/Linux/"*.AppImage >/dev/null 2>&1; then
        fail "No desktop app for this computer type ($ARCH). Use option 1 (the web app)."
      else
        not_included "The desktop app" "Desktop apps"; say "   Meanwhile, option 1 (the web app) does the same job."
      fi
      pause; return
    fi
    mkdir -p "$HOME/Applications" "$HOME/.local/share/applications"
    say "Copying the app to ~/Applications (about 170 MB)..."
    cp -f "$img" "$HOME/Applications/Meshtastic.AppImage" && chmod +x "$HOME/Applications/Meshtastic.AppImage"
    cat > "$HOME/.local/share/applications/meshtastic.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Meshtastic
Comment=Meshtastic mesh radio app
Exec=env APPIMAGE_EXTRACT_AND_RUN=1 $HOME/Applications/Meshtastic.AppImage
Terminal=false
Categories=Network;
EOF
    ok "Installed. It's in your app menu as \"Meshtastic\"."
    say "Starting it now..."
    APPIMAGE_EXTRACT_AND_RUN=1 nohup "$HOME/Applications/Meshtastic.AppImage" >/dev/null 2>&1 &
    linux_serial_check
  fi
  pause
}

do_android() {
  local apk; apk="$(ls "$USB/2-Android-Phone/"*.apk 2>/dev/null | head -1)"
  [ -z "$apk" ] && { fail "The Android app is missing from the USB drive."; pause; return; }
  while true; do
    clear
    say "${B}Put the Meshtastic app on an Android phone${N}"
    say "(iPhones can't install apps this way - iPhone users need the App Store.)"
    say
    say "  ${C}1${N}  Over Wi-Fi  - phone scans a QR code   ${G}(easiest)${N}"
    say "  ${C}2${N}  With a USB cable  (needs 'USB debugging' turned on)"
    say "  ${C}3${N}  Copy the file myself  (opens the folder)"
    say "  ${C}B${N}  Back"
    printf '\nChoose: '; read -r c
    case "$c" in
      1) android_wifi "$apk" ;;
      2) android_adb "$apk" ;;
      3) open_folder "$USB/2-Android-Phone"
         say; say "Copy ${B}$(basename "$apk")${N} to the phone (USB file transfer or SD card),"
         say "then tap it in the phone's Files app and allow 'install unknown apps'."; pause ;;
      *) return ;;
    esac
  done
}

android_wifi() {
  get_miniserve || { pause; return; }
  clear
  say "${B}Send the app over Wi-Fi${N}"
  say "1. The phone and this computer must be on the ${B}same Wi-Fi${N} (or the phone's hotspot)."
  say "2. Scan one of the QR codes below with the phone's camera."
  say "3. Tap the .apk file to download it, open it, and allow 'install unknown apps'."
  say "   ${Y}If your computer asks to allow incoming connections, click Allow.${N}"
  say
  say "When the phone has the app, come back here and press ${B}Enter${N} to stop sharing."
  say
  local ips
  if [ "$OS" = "Darwin" ]; then ips="$(ifconfig 2>/dev/null | awk '/inet /{print $2}')"
  else ips="$(hostname -I 2>/dev/null | tr ' ' '\n'; ip -4 -o addr 2>/dev/null | awk '{print $4}' | cut -d/ -f1)"; fi
  ips="$(printf '%s\n' $ips | grep -vE '^(127\.|169\.254\.)' | sort -u)"
  if [ -n "$ips" ]; then
    say "No QR code scanner? On the phone's browser, type one of these:"
    for ip in $ips; do say "   ${B}http://$ip:$SHARE_PORT${N}"; done
  else
    warn "This computer isn't on any network. Join Wi-Fi (or the phone's hotspot) first."
  fi
  say
  "$MINISERVE" -i 0.0.0.0 -p $SHARE_PORT --qrcode -t "Meshtastic app" "$USB/2-Android-Phone" &
  local sp=$!
  sleep 1
  read -r _
  kill $sp 2>/dev/null; wait $sp 2>/dev/null
  say; ok "Stopped sharing."; pause
}

android_adb() {
  local apk="$1" adbsrc
  case "$OS" in Darwin) adbsrc="$SYS/bin/adb-mac/adb" ;; *) adbsrc="$SYS/bin/adb-linux/adb" ;; esac
  if [ "$PLAT" = "linux-arm64" ] || [ "$PLAT" = "linux-armv7" ]; then
    fail "The USB-cable method isn't available on this computer type. Use Wi-Fi or copy the file."; pause; return
  fi
  local adb; adb="$(prepare_bin "$adbsrc")" || { fail "adb missing from the USB drive."; pause; return; }
  clear
  say "${B}Install with a USB cable${N}"
  say "On the phone, once:"
  say "  a. Settings > About phone > tap ${B}Build number${N} 7 times."
  say "  b. Settings > System > Developer options > turn on ${B}USB debugging${N}."
  say "  c. Plug the phone into this computer. Tap ${B}Allow${N} on the phone if asked."
  printf '\nPress Enter when the phone is plugged in...'; read -r _
  "$adb" start-server >/dev/null 2>&1
  say "Waiting for the phone (up to 60 seconds)..."
  local i=0
  while [ $i -lt 30 ]; do
    if "$adb" devices | awk 'NR>1 && $2=="device"' | grep -q .; then break; fi
    sleep 2; i=$((i+1))
  done
  if ! "$adb" devices | awk 'NR>1 && $2=="device"' | grep -q .; then
    fail "No phone found. Check the cable, USB debugging, and tap Allow on the phone."
    "$adb" devices; pause; return
  fi
  say "Installing (this takes a minute)..."
  if "$adb" install -r "$apk"; then ok "Meshtastic is installed on the phone."
  else fail "Install failed (see the message above)."; fi
  "$adb" kill-server >/dev/null 2>&1
  pause
}

run_imager() {
  if [ "$OS" = "Darwin" ]; then
    if [ -d "/Applications/Raspberry Pi Imager.app" ]; then open -a "Raspberry Pi Imager"; return; fi
    local dmg; dmg="$(ls "$USB/3-Raspberry-Pi/SD-Card-Writer/Mac/"*.dmg 2>/dev/null | head -1)"
    local mnt; mnt="$(hdiutil attach -nobrowse -readonly "$dmg" 2>/dev/null | awk -F'\t' '/\/Volumes\//{print $NF}' | tail -1)"
    local app; app="$(ls -d "$mnt"/*.app 2>/dev/null | head -1)"
    if [ -n "$app" ] && cp -R "$app" /Applications/ 2>/dev/null; then
      hdiutil detach "$mnt" -quiet 2>/dev/null
      xattr -dr com.apple.quarantine "/Applications/$(basename "$app")" 2>/dev/null
      open "/Applications/$(basename "$app")"
    else
      [ -n "$mnt" ] && open "$mnt"
      warn "Drag Raspberry Pi Imager into Applications, then open it."
    fi
  else
    local img; img="$(ls "$USB/3-Raspberry-Pi/SD-Card-Writer/Linux/"*.AppImage 2>/dev/null | head -1)"
    if [ "$PLAT" != "linux-x64" ]; then
      warn "The included SD card writer is for normal (x86) PCs. Use another computer, or"
      warn "any SD card tool (e.g. 'dd' or Disks) with the .img.xz file."; return
    fi
    local run; run="$(prepare_bin "$img")"
    APPIMAGE_EXTRACT_AND_RUN=1 nohup "$run" >/dev/null 2>&1 &
  fi
}

find_bootfs() {
  local d
  for d in /Volumes/bootfs /media/"$USER"/bootfs /run/media/"$USER"/bootfs /media/bootfs; do
    [ -f "$d/config.txt" ] && { echo "$d"; return 0; }
  done
  return 1
}

pi_copy_package() {
  local pkg="$USB/3-Raspberry-Pi/Option-B-Raspberry-Pi-OS-plus-Meshtastic/meshtastic-offline"
  clear; say "${B}Copy the Meshtastic package onto the SD card${N}"
  say "Do this ${B}after${N} Raspberry Pi Imager has finished writing Raspberry Pi OS."
  say "If Imager ejected the card, take it out and put it back in now."
  printf '\nPress Enter when the SD card is plugged in...'; read -r _
  local boot i=0
  while ! boot="$(find_bootfs)" && [ $i -lt 15 ]; do sleep 2; i=$((i+1)); done
  if [ -z "$boot" ]; then
    fail "Couldn't find the SD card (a drive called 'bootfs')."
    say "Re-insert the card and try again, or copy this folder onto the 'bootfs' drive yourself"
    say "and name it 'meshtastic':"; say "  $pkg"; open_folder "$pkg"; pause; return
  fi
  say "Found the SD card at $boot. Copying (about a minute)..."
  rm -rf "$boot/meshtastic"
  if cp -R "$pkg" "$boot/meshtastic"; then
    grep -q '^dtparam=spi=on' "$boot/config.txt" || printf '\n# Meshtastic radio HAT\ndtparam=spi=on\n' >> "$boot/config.txt"
    grep -q '^dtparam=i2c_arm=on' "$boot/config.txt" || printf 'dtparam=i2c_arm=on\n' >> "$boot/config.txt"
    sync
    ok "Done. The card is ready."
    say
    say "Next: put the card in the Pi and power it on. Wait 2-3 minutes, then log in"
    say "(keyboard + screen, or SSH) and type this one command:"
    say
    say "   ${B}sudo bash /boot/firmware/meshtastic/install.sh${N}"
    say
    if [ "$OS" = "Darwin" ]; then diskutil eject "$boot" >/dev/null 2>&1 && ok "SD card ejected - you can remove it."; fi
  else
    fail "Copy failed - is the card full or read-only?"
  fi
  pause
}

do_pi() {
  if ! ls "$USB/3-Raspberry-Pi/"*/*.img.xz >/dev/null 2>&1; then
    clear; not_included "Raspberry Pi SD card making" "the Raspberry Pi images and SD card writer"; pause; return
  fi
  while true; do
    clear
    say "${B}Make a Raspberry Pi SD card${N}  (Pi 3, 4, 5, 400, 500, Zero 2 W)"
    say
    say "  ${C}1${N}  Open the SD card writer (Raspberry Pi Imager)"
    say "  ${C}2${N}  Copy the Meshtastic package onto the card  (only for Option B, after step 1)"
    say "  ${C}3${N}  Show me the step-by-step guide"
    say "  ${C}4${N}  Open the folder with the Pi images"
    say "  ${C}B${N}  Back"
    say
    say "  ${B}Option A${N} (ready-made Meshtastic image): just write it in step 1. Done."
    say "  ${B}Option B${N} (official Raspberry Pi OS): write it in step 1, then do step 2."
    printf '\nChoose: '; read -r c
    case "$c" in
      1) run_imager
         say; say "In Imager: pick your Pi > ${B}Choose OS${N} > scroll to the bottom > ${B}Use custom${N}"
         say "then open the ${B}3-Raspberry-Pi${N} folder on this USB and pick the .img.xz file."
         pause ;;
      2) pi_copy_package ;;
      3) start_all && open_url "http://localhost:$HUB_PORT/guide.html#pi" ;;
      4) open_folder "$USB/3-Raspberry-Pi" ;;
      *) return ;;
    esac
  done
}

# ---- update the drive (needs internet) ------------------------------------------
get_python() {   # prints a runnable python3, using the copy on the drive if possible
  local tgz="$SYS/tools/python/python-$PLAT.tar.gz" dst="$WORK/python-runtime"
  if [ -f "$tgz" ]; then
    local stamp; stamp="$(wc -c < "$tgz" | tr -d ' ')"
    if [ ! -x "$dst/python/bin/python3" ] || [ "$(cat "$dst/.stamp" 2>/dev/null)" != "$stamp" ]; then
      rm -rf "$dst"; mkdir -p "$dst"
      tar xzf "$tgz" -C "$dst" 2>/dev/null || { rm -rf "$dst"; return 1; }
      echo "$stamp" > "$dst/.stamp"
    fi
    echo "$dst/python/bin/python3"; return 0
  fi
  # No bundled copy for this computer type: use the system one (not the macOS installer stub)
  if [ "$OS" != "Darwin" ] && command -v python3 >/dev/null 2>&1; then command -v python3; return 0; fi
  return 1
}

do_update() {
  clear
  say "${B}Update this drive${N}  (needs internet)"
  say "Gets the newest firmware, web app, phone & desktop apps and Raspberry Pi images,"
  say "and replaces the old ones on this USB drive."
  say
  local py; py="$(get_python)" || { fail "Couldn't start the updater on this computer. Try a different computer."; pause; return; }
  say "Checking what's new..."
  "$py" "$SYS/maintenance/build_usb.py" --check
  local rc=$?
  if [ $rc -eq 0 ]; then pause; return; fi
  if [ $rc -ne 3 ]; then fail "Couldn't reach the internet. Connect and try again."; pause; return; fi
  say "This can take 10-30 minutes. ${Y}Don't unplug the drive while it runs.${N}"
  printf 'Download the updates now? [Y/n] '; read -r a
  case "$a" in n|N|no|No) return ;; esac
  say
  if "$py" "$SYS/maintenance/build_usb.py"; then
    ok "This drive is up to date."
  else
    fail "Some parts didn't update (see above). Run the update again to retry - the drive still works."
  fi
  pause
}

# ---- main ----------------------------------------------------------------------
menu() {
  clear
  say "${G}   __  __           _     _            _   _      ${N}"
  say "${G}  |  \\/  | ___  ___| |__ | |_ __ _ ___| |_(_) ___ ${N}"
  say "${G}  | |\\/| |/ _ \\/ __| '_ \\| __/ _\` / __| __| |/ __|${N}"
  say "${G}  | |  | |  __/\\__ \\ | | | || (_| \\__ \\ |_| | (__ ${N}"
  say "${G}  |_|  |_|\\___||___/_| |_|\\__\\__,_|___/\\__|_|\\___|${N}  ${B}EMERGENCY USB${N}  v$(head -1 "$USB/VERSION" 2>/dev/null || echo '?')"
  say
  say "  ${C}1${N}  Open Meshtastic in the browser  (talk on the mesh / flash a radio)"
  say "  ${C}2${N}  Install the Meshtastic app on this computer"
  say "  ${C}3${N}  Put the Meshtastic app on an Android phone"
  say "  ${C}4${N}  Make a Raspberry Pi SD card"
  say "  ${C}5${N}  Help guide"
  say "  ${C}C${N}  Install the Chromium browser  (if this computer has no Chrome/Edge)"
  say "  ${C}U${N}  Update this drive  (needs internet)"
  say "  ${C}Q${N}  Quit"
  say
  say "  ${Y}Keep this window open while you use Meshtastic. Closing it stops everything.${N}"
  printf '\nType a number and press Enter: '
}

clear
say "Starting Meshtastic..."
do_open
sleep 1
while true; do
  menu
  read -r choice || exit 0
  case "$choice" in
    1|"") do_open ;;
    2) do_desktop ;;
    3) do_android ;;
    4) do_pi ;;
    5) start_all && open_url "http://localhost:$HUB_PORT/guide.html" ;;
    u|U) do_update ;;
    c|C) start_all; do_chromium ;;
    q|Q) say "Stopping Meshtastic. Bye!"; exit 0 ;;
  esac
done
