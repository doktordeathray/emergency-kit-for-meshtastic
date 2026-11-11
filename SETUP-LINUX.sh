#!/usr/bin/env bash
# Linux / Raspberry Pi: right-click > "Run as a Program" (or run:  bash SETUP-LINUX.sh)
if [ ! -t 0 ] && [ -z "$MESH_IN_TERM" ]; then
  export MESH_IN_TERM=1
  for t in x-terminal-emulator gnome-terminal konsole xfce4-terminal mate-terminal lxterminal tilix kitty alacritty xterm; do
    if command -v "$t" >/dev/null 2>&1; then
      case "$t" in gnome-terminal) exec "$t" -- bash "$0" ;; *) exec "$t" -e bash "$0" ;; esac
    fi
  done
fi
cd "$(dirname "$0")" || exit 1
exec bash "./_system/maintenance/bootstrap.sh"
