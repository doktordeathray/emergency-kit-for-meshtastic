#!/usr/bin/env bash
# Finds (or downloads) a Python to run setup.py with. Mac, Linux, Raspberry Pi.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYS="$(dirname "$HERE")"
OS="$(uname -s)"; ARCH="$(uname -m)"
WORK="${TMPDIR:-/tmp}/meshtastic-setup-$(id -u)"
mkdir -p "$WORK"

case "$OS-$ARCH" in
  Darwin-arm64) PLAT=mac-arm64; TRIPLE=aarch64-apple-darwin ;;
  Darwin-*)     PLAT=mac-x64;   TRIPLE=x86_64-apple-darwin ;;
  Linux-x86_64) PLAT=linux-x64; TRIPLE=x86_64-unknown-linux-gnu ;;
  Linux-aarch64|Linux-arm64) PLAT=linux-arm64; TRIPLE=aarch64-unknown-linux-gnu ;;
  *) PLAT=other; TRIPLE="" ;;
esac

PY=""
# 1. A Python already on this kit (full drives carry one)
if [ -f "$SYS/tools/python/python-$PLAT.tar.gz" ]; then
  rm -rf "$WORK/py"; mkdir -p "$WORK/py"
  tar xzf "$SYS/tools/python/python-$PLAT.tar.gz" -C "$WORK/py" && PY="$WORK/py/python/bin/python3"
fi
# 2. Linux usually has one (Mac's /usr/bin/python3 may just be an installer prompt, so skip it there)
if [ -z "$PY" ] && [ "$OS" = "Linux" ] && command -v python3 >/dev/null 2>&1 \
   && python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>/dev/null; then
  PY="$(command -v python3)"
fi
# 3. Download a portable Python (about 25 MB)
if [ -z "$PY" ] && [ -n "$TRIPLE" ]; then
  echo "Getting a small helper (Python, about 25 MB)..."
  url="$(curl -fsSL --retry 3 --connect-timeout 20 https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest \
        | grep -oE "https://[^\"]*cpython-3\.12\.[0-9]+(\+|%2B)[0-9]+-$TRIPLE-install_only_stripped\.tar\.gz" | head -1)"
  if [ -n "$url" ] && curl -fL --retry 3 -o "$WORK/python.tar.gz" "$url"; then
    rm -rf "$WORK/py"; mkdir -p "$WORK/py"
    tar xzf "$WORK/python.tar.gz" -C "$WORK/py" && PY="$WORK/py/python/bin/python3"
  fi
fi
if [ -z "$PY" ]; then
  echo "Couldn't get Python on this computer. Check the internet connection and try again."
  echo "(On Linux you can also install it:  sudo apt install python3)"
  read -r -p "Press Enter to close." _; exit 1
fi
"$PY" -u "$HERE/setup.py" "$@"
rc=$?
echo; read -r -p "Press Enter to close." _
exit $rc
