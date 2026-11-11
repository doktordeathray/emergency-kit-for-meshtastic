#!/usr/bin/env bash
# Meshtastic offline installer for Raspberry Pi OS (64-bit, trixie).
# Run on the Pi:   sudo bash /boot/firmware/meshtastic/install.sh
# Needs no internet: every package is in ./packages next to this script.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
G=$'\033[1;32m'; Y=$'\033[1;33m'; R=$'\033[1;31m'; B=$'\033[1m'; N=$'\033[0m'
ok()   { echo "${G}✔ $*${N}"; }
warn() { echo "${Y}! $*${N}"; }
die()  { echo "${R}✖ $*${N}"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Please run with sudo:   sudo bash $0"
[ "$(dpkg --print-architecture)" = "arm64" ] || \
  die "This needs 64-bit Raspberry Pi OS (the image on the USB drive). This Pi runs $(dpkg --print-architecture)."
. /etc/os-release
[ "${VERSION_CODENAME:-}" = "trixie" ] || \
  warn "Made for Raspberry Pi OS 'trixie'; this is '${VERSION_CODENAME:-unknown}'. Trying anyway."

echo
echo "${B}Meshtastic offline installer${N}"
echo "----------------------------"

# 1. Packages ---------------------------------------------------------------
if dpkg-query -W -f='${Status}' meshtasticd 2>/dev/null | grep -q "install ok installed"; then
  ok "Meshtastic is already installed ($(dpkg-query -W -f='${Version}' meshtasticd))."
else
  echo "Installing Meshtastic and the libraries it needs (no internet used)..."
  # Use the packages folder as a private apt repository: apt works out exactly
  # what this Pi is missing. Other (online) sources are ignored for this step.
  REPO=/var/cache/meshtastic-offline
  LIST=/etc/apt/sources.list.d/zz-meshtastic-offline.list
  rm -rf "$REPO"; mkdir -p "$REPO"
  cp "$HERE"/packages/* "$REPO"/
  echo "deb [trusted=yes] file:$REPO ./" > "$LIST"
  APTOPT=(-o Dir::Etc::sourcelist="$LIST" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0")
  {
    apt-get update "${APTOPT[@]}" &&
    apt-get install -y --no-install-recommends "${APTOPT[@]}" meshtasticd
  } >/tmp/meshtastic-install.log 2>&1
  rc=$?
  rm -f "$LIST"
  if [ $rc -ne 0 ]; then
    warn "apt couldn't do it; trying a direct install..."
    todo=()
    for deb in "$REPO"/*.deb; do
      pkg="$(dpkg-deb -f "$deb" Package)"
      dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed" || todo+=("$deb")
    done
    dpkg -i "${todo[@]}" >>/tmp/meshtastic-install.log 2>&1
  fi
  rm -rf "$REPO"
  dpkg-query -W -f='${Status}' meshtasticd 2>/dev/null | grep -q "install ok installed" || \
    die "Install failed. Details are in /tmp/meshtastic-install.log"
  ok "Meshtastic installed ($(dpkg-query -W -f='${Version}' meshtasticd))."
fi

# 2. SPI + I2C for radio HATs -------------------------------------------------
CFG=/boot/firmware/config.txt
need_reboot=0
if [ -f "$CFG" ]; then
  grep -q '^dtparam=spi=on' "$CFG"     || { echo 'dtparam=spi=on' >> "$CFG"; need_reboot=1; }
  grep -q '^dtparam=i2c_arm=on' "$CFG" || { echo 'dtparam=i2c_arm=on' >> "$CFG"; need_reboot=1; }
fi
[ -e /dev/spidev0.0 ] || need_reboot=1

# 3. Which radio? ---------------------------------------------------------------
AV=/etc/meshtasticd/available.d
CD=/etc/meshtasticd/config.d
mkdir -p "$CD"
# Only show configs that fit a Raspberry Pi (hide other single-board computers).
mapfile -t radios < <(ls "$AV" 2>/dev/null | grep -E '^lora-.*\.yaml$' | \
  grep -vE 'ecb41|lyra|ok3506|luckfox|femtofox|raxda|orangepi|pico-max' | sort)

echo
echo "${B}Which radio is connected to this Pi?${N}"
echo "   0) I'm not sure / try to auto-detect"
i=1
for r in "${radios[@]}"; do
  name="${r#lora-}"; name="${name%.yaml}"
  printf "  %2d) %s\n" "$i" "$name"
  i=$((i+1))
done
current="$(ls "$CD" 2>/dev/null | grep '^lora-' | head -1)"
[ -n "$current" ] && echo "  (currently set: ${current})  - press Enter to keep it"
printf "\nType a number and press Enter: "
read -r pick
if [ -z "$pick" ] && [ -n "$current" ]; then
  ok "Keeping $current"
elif [ "$pick" = "0" ] || [ -z "$pick" ]; then
  rm -f "$CD"/lora-*.yaml
  ok "Auto-detect. (If the radio isn't found, run this script again and pick it.)"
elif [ "$pick" -ge 1 ] 2>/dev/null && [ "$pick" -le "${#radios[@]}" ]; then
  rm -f "$CD"/lora-*.yaml
  cp "$AV/${radios[$((pick-1))]}" "$CD/"
  ok "Using ${radios[$((pick-1))]}"
else
  warn "Not a valid choice - using auto-detect."
fi

# 4. Built-in web app on https://<pi>:9443 ----------------------------------------
Y_CFG=/etc/meshtasticd/config.yaml
if grep -q '^#  Port: 9443' "$Y_CFG"; then
  sed -i 's|^#  Port: 9443|  Port: 9443|; s|^#  RootPath: /usr/share/meshtasticd/web|  RootPath: /usr/share/meshtasticd/web|' "$Y_CFG"
fi
ok "Web app enabled on port 9443."

# 5. Start it -------------------------------------------------------------------
systemctl enable meshtasticd >/dev/null 2>&1
ips="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.' | head -3)"
echo
if [ "$need_reboot" -eq 1 ]; then
  ok "All set. The Pi must restart once to switch on the radio connections."
  echo
  echo "After it restarts (about 1 minute), Meshtastic starts by itself."
else
  systemctl restart meshtasticd
  sleep 3
  if systemctl is-active --quiet meshtasticd; then ok "Meshtastic is running."
  else warn "Meshtastic didn't start. See:  journalctl -u meshtasticd -b"; fi
fi
echo
echo "${B}How to use it:${N}"
for ip in $ips; do
  echo "  • In a browser on the same network:  ${B}https://$ip:9443${N}  (accept the security warning)"
  echo "  • In the phone/desktop app: add a ${B}Network / TCP${N} connection to  ${B}$ip${N}"
done
[ -z "$ips" ] && echo "  • Connect the Pi to a network, then browse to https://<pi-address>:9443"
echo "  • First, set your ${B}Region${N} (Settings > LoRa) or the radio won't transmit."
echo
echo "Run this script again any time to change the radio type."
if [ "$need_reboot" -eq 1 ]; then
  printf "\nPress Enter to restart now (or Ctrl+C to restart later)... "
  read -r _ && reboot
fi
