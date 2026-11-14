# Emergency Kit for Meshtastic - launcher for Windows 10/11.
# Started by START-HERE-WINDOWS.bat. Works fully offline. PowerShell 5.1 compatible.
param([string]$RestartedFrom = '')

$ErrorActionPreference = 'Continue'
$SYS = Split-Path -Parent $MyInvocation.MyCommand.Path
$USB = Split-Path -Parent $SYS
$HUB_PORT = 8470; $CLIENT_PORT = 8471; $FLASHER_PORT = 8472; $SHARE_PORT = 8473; $DOCS_PORT = 8474
$WORK = Join-Path $env:TEMP 'meshtastic-usb'
New-Item -ItemType Directory -Force -Path $WORK | Out-Null
$script:Servers = @()
$Host.UI.RawUI.WindowTitle = 'Emergency Kit for Meshtastic - keep this window open'

function Say($t)  { Write-Host $t }
function Ok($t)   { Write-Host "  [OK] $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  [!] $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host "  [X] $t" -ForegroundColor Red }
function Pause-Menu { Write-Host ''; Read-Host 'Press Enter to go back to the menu' | Out-Null }

if (-not [Environment]::Is64BitOperatingSystem) {
    Fail 'This tool needs 64-bit Windows.'; Read-Host 'Press Enter to close'; exit 1
}

# Copy small programs off the USB first: faster, and avoids "file in use" when the USB is removed.
function Prepare-Bin($src) {
    $dst = Join-Path $WORK (Split-Path -Leaf $src)
    if (-not (Test-Path $dst) -or (Get-Item $src).LastWriteTime -gt (Get-Item $dst).LastWriteTime) {
        Copy-Item -Force $src $dst
    }
    Unblock-File -Path $dst -ErrorAction SilentlyContinue
    return $dst
}

$script:Miniserve = $null
function Get-Miniserve {
    if ($script:Miniserve) { return $true }
    $src = Join-Path $SYS 'bin\miniserve-windows-x64.exe'
    if (-not (Test-Path $src)) {
        Fail "This kit isn't set up yet. Close this window and double-click SETUP-WINDOWS.bat"
        Fail '- it downloads everything (needs internet once).'
        return $false
    }
    $script:Miniserve = Prepare-Bin $src
    return $true
}

function Test-Port($port) {
    # Short timeout: a refused connect on Windows otherwise retries for ~2 seconds.
    $c = New-Object Net.Sockets.TcpClient
    try {
        $t = $c.ConnectAsync('127.0.0.1', $port)
        if ($t.Wait(300) -and $c.Connected) { return $true }
        return $false
    } catch { return $false } finally { $c.Close() }
}

function Start-Server($port, $dir, [string[]]$extra) {
    if (Test-Port $port) { return }
    # no-cache: browsers always check for a newer page, so an updated drive shows up at once
    $argList = @('-i', '127.0.0.1', '-p', "$port", '--index', 'index.html', '-t', '"Meshtastic USB"',
                 '--header', '"Cache-Control: no-cache"') + $extra + @("`"$dir`"")
    $p = Start-Process -FilePath $script:Miniserve -ArgumentList $argList -NoNewWindow -PassThru `
         -RedirectStandardOutput (Join-Path $WORK "server-$port.log") -RedirectStandardError (Join-Path $WORK "server-$port.err")
    $script:Servers += $p
}

# Another start window (maybe from another copy of the kit) may already be serving on these
# ports; then this window's pages wouldn't be the ones shown. Say so.
function Test-StaleServer {
    try {
        $served = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://127.0.0.1:$HUB_PORT/index.html").Content
        $mine = [IO.File]::ReadAllText((Join-Path $SYS 'hub\index.html'))
        if ($served -ne $mine) {
            Warn 'Another Meshtastic window is already running, from a different copy of this kit.'
            Warn "The browser will show that copy's pages. Close the other window, then choose 1 again."
        }
    } catch { }
}

$KitVer = ''
try { $KitVer = ((Get-Content (Join-Path $USB 'VERSION') -TotalCount 1 -ErrorAction Stop) -replace '[^0-9.]', '') } catch { }

function Start-All {
    if (-not (Get-Miniserve)) { return $false }
    Start-Server $HUB_PORT (Join-Path $SYS 'hub') @()
    Start-Server $CLIENT_PORT (Join-Path $SYS 'webclient') @('--spa',
        '--header', '"Cross-Origin-Opener-Policy: same-origin"',
        '--header', '"Cross-Origin-Embedder-Policy: require-corp"')
    Start-Server $FLASHER_PORT (Join-Path $SYS 'flasher') @()
    if (Test-Path (Join-Path $SYS 'docs\index.html')) { Start-Server $DOCS_PORT (Join-Path $SYS 'docs') @() }
    Test-StaleServer
    for ($i = 0; $i -lt 30 -and -not (Test-Port $HUB_PORT); $i++) { Start-Sleep -Milliseconds 200 }
    if (Test-Port $HUB_PORT) { Ok 'Meshtastic is running on this computer (no internet needed).'; return $true }
    Fail "The local server didn't start. Details: $WORK"; return $false
}

function Stop-All {
    foreach ($p in $script:Servers) { try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {} }
    $script:Servers = @()
}

# Web Serial / Web Bluetooth need Chrome or Edge. Edge is on every Windows 10/11 PC.
function Open-Url($url) {
    $cands = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe")
    foreach ($c in $cands) { if ($c -and (Test-Path $c)) { Start-Process $c $url; return } }
    try { Start-Process "microsoft-edge:$url" } catch { Start-Process $url }
}

function Open-Folder($path) { Start-Process explorer.exe "`"$path`"" }

function Do-Open { if (Start-All) { Open-Url "http://localhost:$HUB_PORT/?v=$KitVer" } }

function Not-Included($what, $extra) {
    Warn "$what isn't included in this kit."
    Say  '   To add it (needs internet): run SETUP-WINDOWS.bat again, pick this same drive,'
    Say  "   choose '2 - plus extras', and select '$extra'."
}

function Do-Desktop {
    Clear-Host; Say 'Install the Meshtastic app on this computer'; Say ''
    $msi = Get-ChildItem (Join-Path $USB '1-Desktop-App\Windows') -Filter *.msi -ErrorAction SilentlyContinue | Where-Object { -not $_.Name.StartsWith('._') } | Select-Object -First 1
    if (-not $msi) { Not-Included 'The desktop app' 'Desktop apps'; Say '   Meanwhile, option 1 (the web app) does the same job.'; Pause-Menu; return }
    Say 'The installer is opening. Click Next / Install. If Windows asks "Do you want to allow", click Yes.'
    Start-Process msiexec.exe -ArgumentList "/i `"$($msi.FullName)`"" -Wait
    Ok 'Finished. Look for "Meshtastic" in the Start menu.'
    Say ''
    Say 'Radio not showing up? Most radios need a USB driver on Windows. Use option 6.'
    Pause-Menu
}

# Check a file's digital signature: it must be valid AND come from the expected company.
# This works for any version the chip maker releases, and fails if the file was altered.
# Returns $true when it is OK to install.
function Test-Signature($path, $mustContain, $who, $label) {
    $sig = Get-AuthenticodeSignature -LiteralPath $path
    $subject = ''
    if ($sig.SignerCertificate) { $subject = $sig.SignerCertificate.Subject }
    $fromExpected = $subject -like "*$mustContain*"
    if ($sig.Status -eq 'Valid' -and $fromExpected) {
        Ok "Verified: $label has a valid digital signature from $who."
        return $true
    }
    # With no internet, Windows sometimes can't confirm online that the certificate is still
    # current. The signature itself is fine, so accept it and say so.
    if ($fromExpected -and $sig.StatusMessage -match 'unable to check revocation|revocation server was offline') {
        Ok "Verified: $label is signed by $who."
        Say '     (Windows could not check online that the certificate is still current. Normal with no internet.)'
        return $true
    }
    Fail "$label did NOT pass the signature check, so it will not be installed."
    if (-not $sig.SignerCertificate) { Say '     The file has no digital signature.' }
    elseif (-not $fromExpected) { Say "     It is signed by someone else: $subject" }
    else { Say "     Windows says: $($sig.StatusMessage)" }
    Say "     Get a fresh copy from the maker's website (links in READ-ME.txt in the drivers folder)."
    return $false
}

# Extra information only: is this the exact copy that was looked up on VirusTotal?
function Show-VirusTotal($file) {
    try {
        $rec = Get-Content -Raw (Join-Path (Split-Path -Parent $file.FullName) 'checksums.json') | ConvertFrom-Json
        $entry = $rec.PSObject.Properties[$file.Name].Value
        $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLower()
        if ($entry -and $entry.sha256 -eq $sha) { Say "     This exact copy was also checked on VirusTotal: $($entry.virustotal)." }
    } catch {}
}

function Do-Drivers {
    Clear-Host; Say 'Install USB drivers for radios'; Say ''
    Say 'If Windows does not see your radio (no COM port), install the driver for its USB chip.'
    Say 'Not sure which? Install both - it does no harm.'
    Say 'Each driver is checked for a valid digital signature from its maker before it installs.'; Say ''
    $d = Join-Path $USB '5-Windows-USB-Drivers'
    $ch = Get-ChildItem $d -Filter 'CH34*.EXE' -ErrorAction SilentlyContinue | Where-Object { -not $_.Name.StartsWith('._') } | Select-Object -First 1
    $cp = Get-ChildItem $d -Filter 'CP210x*.zip' -ErrorAction SilentlyContinue | Where-Object { -not $_.Name.StartsWith('._') } | Select-Object -First 1
    Say '  1  CH340 / CH9102 driver  (Heltec V3/V4, many cheap ESP32 boards)'
    Say '  2  CP210x driver          (T-Beam, LILYGO, Station G2, older Heltec)'
    Say '  B  Back'
    $c = Read-Host "`nChoose"
    switch ($c) {
        '1' {
            if (-not $ch) { Fail 'The CH340 driver is not on this drive.'; Open-Folder $d }
            elseif (Test-Signature $ch.FullName 'Nanjing Qinheng Microelectronics' 'WCH (Nanjing Qinheng Microelectronics)' 'The CH340 driver') {
                Show-VirusTotal $ch
                Start-Process $ch.FullName -Wait
                Ok 'Done. Unplug and re-plug the radio.'
            }
        }
        '2' {
            if (-not $cp) { Fail 'The CP210x driver is not on this drive.'; Open-Folder $d }
            else {
                $x = Join-Path $WORK 'cp210x'
                if (Test-Path $x) { Remove-Item -Recurse -Force $x }
                Expand-Archive -Force $cp.FullName $x
                $cat = Get-ChildItem $x -Recurse -Filter *.cat | Where-Object { -not $_.Name.StartsWith('._') } | Select-Object -First 1
                $inf = Get-ChildItem $x -Recurse -Filter *.inf | Where-Object { -not $_.Name.StartsWith('._') } | Select-Object -First 1
                if (-not $cat -or -not $inf) { Fail 'The CP210x driver package looks incomplete. Get a fresh copy from Silicon Labs.' }
                elseif (Test-Signature $cat.FullName 'Microsoft Windows Hardware Compatibility Publisher' 'Microsoft (WHQL-certified driver)' 'The CP210x driver') {
                    Show-VirusTotal $cp
                    Say 'Installing (click Yes if Windows asks)...'
                    # pnputil also refuses any driver file that doesn't match the signed catalog.
                    Start-Process pnputil.exe -ArgumentList "/add-driver `"$($inf.FullName)`" /install" -Verb RunAs -Wait
                    Ok 'Done. Unplug and re-plug the radio.'
                }
            }
        }
    }
    if ($c -eq '1' -or $c -eq '2') { Pause-Menu }
}

function Do-Android {
    $apk = Get-ChildItem (Join-Path $USB '2-Android-Phone') -Filter *.apk -ErrorAction SilentlyContinue | Where-Object { -not $_.Name.StartsWith('._') } | Select-Object -First 1
    if (-not $apk) { Fail 'The Android app is missing from the USB drive.'; Pause-Menu; return }
    while ($true) {
        Clear-Host
        Say 'Put the Meshtastic app on an Android phone'
        Say "(iPhones can't install apps this way - iPhone users need the App Store.)"; Say ''
        Say '  1  Over Wi-Fi - phone scans a QR code   (easiest)'
        Say "  2  With a USB cable (needs 'USB debugging' turned on)"
        Say '  3  Copy the file myself (opens the folder)'
        Say '  B  Back'
        $c = Read-Host "`nChoose"
        switch ($c) {
            '1' { Android-Wifi }
            '2' { Android-Adb $apk.FullName }
            '3' { Open-Folder (Join-Path $USB '2-Android-Phone')
                  Say ''; Say "Copy $($apk.Name) to the phone (USB file transfer or SD card),"
                  Say "then tap it in the phone's Files app and allow 'install unknown apps'."; Pause-Menu }
            default { return }
        }
    }
}

function Android-Wifi {
    if (-not (Get-Miniserve)) { Pause-Menu; return }
    Clear-Host
    Say 'Send the app over Wi-Fi'
    Say '1. The phone and this computer must be on the SAME Wi-Fi (or the phone''s hotspot).'
    Say '2. Scan one of the QR codes below with the phone''s camera.'
    Say "3. Tap the .apk file to download it, open it, and allow 'install unknown apps'."
    Warn 'If Windows Firewall pops up, tick "Private networks" and click Allow.'
    Say ''
    $ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } | Select-Object -ExpandProperty IPAddress)
    if ($ips.Count -gt 0) {
        Say "No QR code scanner? On the phone's browser, type one of these:"
        foreach ($ip in $ips) { Write-Host "   http://${ip}:$SHARE_PORT" -ForegroundColor Cyan }
    } else { Warn "This computer isn't on any network. Join Wi-Fi (or the phone's hotspot) first." }
    Say ''
    $sp = Start-Process -FilePath $script:Miniserve -NoNewWindow -PassThru -ArgumentList @(
        '-i', '0.0.0.0', '-p', "$SHARE_PORT", '--qrcode', '-t', '"Meshtastic app"', "`"$(Join-Path $USB '2-Android-Phone')`"")
    Start-Sleep 2
    Say ''
    Write-Host 'Sharing. When the phone has the app, press Enter to stop and go back to the menu.' -ForegroundColor Green
    # Ctrl+C (which the server's own message suggests) would close this whole window, so while
    # sharing it's read as a key instead: Enter, Esc or Ctrl+C all stop sharing.
    $oldCtrlC = [Console]::TreatControlCAsInput
    try {
        [Console]::TreatControlCAsInput = $true
        while ($true) {
            $k = [Console]::ReadKey($true)
            if ($k.Key -eq 'Enter' -or $k.Key -eq 'Escape' -or
                ($k.Key -eq 'C' -and ($k.Modifiers -band [ConsoleModifiers]::Control))) { break }
        }
    } catch {
        Read-Host | Out-Null      # no console keys available: fall back to Enter
    } finally {
        [Console]::TreatControlCAsInput = $oldCtrlC
    }
    try { Stop-Process -Id $sp.Id -Force -ErrorAction SilentlyContinue } catch {}
    Ok 'Stopped sharing.'
    Pause-Menu
}

function Android-Adb($apk) {
    $adbDir = Join-Path $SYS 'bin\adb-windows'
    if (-not (Test-Path "$adbDir\adb.exe")) { Fail 'adb is missing from the USB drive.'; Pause-Menu; return }
    $w = Join-Path $WORK 'adb'; New-Item -ItemType Directory -Force $w | Out-Null
    Copy-Item -Force "$adbDir\*" $w
    $adb = Join-Path $w 'adb.exe'
    Clear-Host
    Say 'Install with a USB cable'
    Say 'On the phone, once:'
    Say '  a. Settings > About phone > tap "Build number" 7 times.'
    Say '  b. Settings > System > Developer options > turn on "USB debugging".'
    Say '  c. Plug the phone into this computer. Tap "Allow" on the phone if asked.'
    Read-Host "`nPress Enter when the phone is plugged in" | Out-Null
    & $adb start-server 2>$null | Out-Null
    Say 'Waiting for the phone (up to 60 seconds)...'
    $found = $false
    for ($i = 0; $i -lt 30; $i++) {
        $lines = & $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "`tdevice$" }
        if ($lines) { $found = $true; break }
        Start-Sleep 2
    }
    if (-not $found) {
        Fail 'No phone found. Check the cable, USB debugging, and tap Allow on the phone.'
        Say 'Some phones also need their maker''s USB driver on Windows - if so, use Wi-Fi instead.'
        & $adb devices; & $adb kill-server; Pause-Menu; return
    }
    Say 'Installing (this takes a minute)...'
    & $adb install -r "$apk"
    if ($LASTEXITCODE -eq 0) { Ok 'Meshtastic is installed on the phone.' } else { Fail 'Install failed (see the message above).' }
    & $adb kill-server
    Pause-Menu
}

function Run-Imager {
    $installed = @("$env:ProgramFiles\Raspberry Pi Imager\rpi-imager.exe", "${env:ProgramFiles(x86)}\Raspberry Pi Imager\rpi-imager.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($installed) { Start-Process $installed; return }
    $exe = Get-ChildItem (Join-Path $USB '3-Raspberry-Pi\SD-Card-Writer\Windows') -Filter *.exe -ErrorAction SilentlyContinue | Where-Object { -not $_.Name.StartsWith('._') } | Select-Object -First 1
    if (-not $exe) { Fail 'Raspberry Pi Imager is missing from the USB drive.'; return }
    Say 'Installing Raspberry Pi Imager - click Yes / Install, and tick "Run" at the end.'
    Start-Process $exe.FullName -Wait
    $installed = @("$env:ProgramFiles\Raspberry Pi Imager\rpi-imager.exe", "${env:ProgramFiles(x86)}\Raspberry Pi Imager\rpi-imager.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($installed) { Start-Process $installed }
}

function Find-Bootfs {
    $v = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'bootfs' -and $_.DriveLetter } | Select-Object -First 1
    if ($v) { $p = "$($v.DriveLetter):\"; if (Test-Path "$p\config.txt") { return $p } }
    foreach ($d in [IO.DriveInfo]::GetDrives()) {
        try { if ($d.IsReady -and $d.VolumeLabel -eq 'bootfs') { return $d.RootDirectory.FullName } } catch {}
    }
    return $null
}

function Pi-CopyPackage {
    $pkg = Join-Path $USB '3-Raspberry-Pi\Option-B-Raspberry-Pi-OS-plus-Meshtastic\meshtastic-offline'
    Clear-Host
    Say 'Copy the Meshtastic package onto the SD card'
    Say 'Do this AFTER Raspberry Pi Imager has finished writing Raspberry Pi OS.'
    Say 'If Imager ejected the card, take it out and put it back in now.'
    Warn 'If Windows says "You need to format the disk", click CANCEL - never format it.'
    Read-Host "`nPress Enter when the SD card is plugged in" | Out-Null
    $boot = $null
    for ($i = 0; $i -lt 15 -and -not $boot; $i++) { $boot = Find-Bootfs; if (-not $boot) { Start-Sleep 2 } }
    if (-not $boot) {
        Fail "Couldn't find the SD card (a drive called 'bootfs')."
        Say "Re-insert it and try again, or copy this folder onto the 'bootfs' drive and name it 'meshtastic':"
        Say "  $pkg"; Open-Folder $pkg; Pause-Menu; return
    }
    Say "Found the SD card at $boot. Copying (about a minute)..."
    $dst = Join-Path $boot 'meshtastic'
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    try {
        Copy-Item -Recurse -Force $pkg $dst -ErrorAction Stop
        $cfg = Join-Path $boot 'config.txt'
        $txt = Get-Content -Raw $cfg
        $add = ''
        if ($txt -notmatch '(?m)^dtparam=spi=on') { $add += "`n# Meshtastic radio HAT`ndtparam=spi=on`n" }
        if ($txt -notmatch '(?m)^dtparam=i2c_arm=on') { $add += "dtparam=i2c_arm=on`n" }
        if ($add) { [IO.File]::AppendAllText($cfg, ($add -replace "`r", '')) }
        Ok 'Done. The card is ready. Eject it (right-click the drive > Eject) and put it in the Pi.'
        Say ''
        Say 'Power the Pi on, wait 2-3 minutes, log in (keyboard + screen, or SSH), and type:'
        Say ''
        Write-Host '   sudo bash /boot/firmware/meshtastic/install.sh' -ForegroundColor Cyan
    } catch { Fail "Copy failed - is the card full or read-only? $_" }
    Pause-Menu
}

function Do-Pi {
    if (-not (Get-ChildItem (Join-Path $USB '3-Raspberry-Pi') -Recurse -Filter *.img.xz -ErrorAction SilentlyContinue | Where-Object { -not $_.Name.StartsWith('._') })) {
        Clear-Host; Not-Included 'Raspberry Pi SD card making' 'the Raspberry Pi images and SD card writer'; Pause-Menu; return
    }
    while ($true) {
        Clear-Host
        Say 'Make a Raspberry Pi SD card  (Pi 3, 4, 5, 400, 500, Zero 2 W)'; Say ''
        Say '  1  Open the SD card writer (Raspberry Pi Imager)'
        Say '  2  Copy the Meshtastic package onto the card  (only for Option B, after step 1)'
        Say '  3  Show me the step-by-step guide'
        Say '  4  Open the folder with the Pi images'
        Say '  B  Back'; Say ''
        Say '  Option A (ready-made Meshtastic image): just write it in step 1. Done.'
        Say '  Option B (official Raspberry Pi OS): write it in step 1, then do step 2.'
        $c = Read-Host "`nChoose"
        switch ($c) {
            '1' { Run-Imager
                  Say ''; Say 'In Imager: pick your Pi > Choose OS > scroll to the bottom > "Use custom"'
                  Say 'then open the 3-Raspberry-Pi folder on this USB and pick the .img.xz file.'
                  Pause-Menu }
            '2' { Pi-CopyPackage }
            '3' { if (Start-All) { Open-Url "http://localhost:$HUB_PORT/guide.html#pi" } }
            '4' { Open-Folder (Join-Path $USB '3-Raspberry-Pi') }
            default { return }
        }
    }
}

function Get-Python {
    $tgz = Join-Path $SYS 'tools\python\python-windows-x64.tar.gz'
    if (-not (Test-Path $tgz)) { return $null }
    $dst = Join-Path $WORK 'python-runtime'
    $exe = Join-Path $dst 'python\python.exe'
    $stamp = (Get-Item $tgz).Length.ToString()
    $stampFile = Join-Path $dst '.stamp'
    if (-not (Test-Path $exe) -or -not (Test-Path $stampFile) -or (Get-Content $stampFile) -ne $stamp) {
        Say 'Preparing the updater (one time, about 20 seconds)...'
        if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
        New-Item -ItemType Directory -Force $dst | Out-Null
        & tar.exe -xzf "$tgz" -C "$dst"
        if (-not (Test-Path $exe)) { return $null }
        Set-Content -Path $stampFile -Value $stamp
    }
    return $exe
}

# ---- "updates available" notice ---------------------------------------------------
# When the start window opens it asks, in the background, whether anything newer is out
# (the same check U makes). The answer is kept for 6 hours (GitHub limits how often it may
# be asked). The menu then shows a flashing line.
$UpdRc = Join-Path $WORK 'update-check.rc'; $UpdOut = Join-Path $WORK 'update-check.txt'
$UpdKit = Join-Path $WORK 'update-check.kit'
$script:UpdProc = $null; $script:UpdShown = $false; $script:UpdRow = -1
function Start-UpdateCheck {
    try {
        if ((Test-Path $UpdRc) -and ((Get-Date) - (Get-Item $UpdRc).LastWriteTime).TotalHours -lt 6 -and
            (Get-Content $UpdKit -ErrorAction Stop) -eq $KitVer) { return }
    } catch { }
    Remove-Item $UpdRc, $UpdOut -ErrorAction SilentlyContinue
    $py = Get-Python
    if (-not $py) { return }
    $env:MESH_UPDATE_SUMMARY = $UpdOut
    try {
        $script:UpdProc = Start-Process -FilePath $py -PassThru -WindowStyle Hidden `
            -ArgumentList @("`"$(Join-Path $SYS 'maintenance\build_usb.py')`"", '--check') `
            -RedirectStandardOutput (Join-Path $WORK 'update-check.log') -RedirectStandardError (Join-Path $WORK 'update-check.err')
    } catch { $script:UpdProc = $null }
    Remove-Item Env:\MESH_UPDATE_SUMMARY -ErrorAction SilentlyContinue
}
function Get-UpdateSummary {
    if ($script:UpdProc -and $script:UpdProc.HasExited) {
        try { Set-Content $UpdRc $script:UpdProc.ExitCode; Set-Content $UpdKit $KitVer } catch { }
        $script:UpdProc = $null
    }
    try { if ((Get-Content $UpdRc -ErrorAction Stop) -ne '3') { return '' } } catch { return '' }
    try { $s = (Get-Content $UpdOut -Raw -ErrorAction Stop).Trim() } catch { $s = '' }
    if (-not $s) { $s = 'new versions' }
    return $s
}
function Write-UpdateLine($bright) {
    $s = Get-UpdateSummary
    if (-not $s) { return }
    $t = "  >> UPDATES AVAILABLE: $s.  Press U (needs internet) <<  "
    if ($bright) { Write-Host $t -ForegroundColor Black -BackgroundColor Yellow -NoNewline }
    else { Write-Host $t -ForegroundColor Yellow -NoNewline }
}
# Wait for the menu choice, flashing the update line meanwhile and showing it as soon as the
# background check finishes. The first key stops the flashing; the line is then read as usual.
function Read-Choice {
    $prompt = "`nType a number and press Enter: "
    Write-Host $prompt -NoNewline
    try {
        $tick = $false
        while (-not [Console]::KeyAvailable) {
            Start-Sleep -Milliseconds 500
            if (Get-UpdateSummary) {
                if (-not $script:UpdShown) { Show-Menu; Write-Host $prompt -NoNewline; continue }
                $tick = -not $tick
                $x = [Console]::CursorLeft; $y = [Console]::CursorTop
                [Console]::SetCursorPosition(0, $script:UpdRow)
                Write-UpdateLine $tick
                [Console]::SetCursorPosition($x, $y)
            }
        }
    } catch { }
    return $Host.UI.ReadLine()
}

function Do-Update {
    Clear-Host
    Say 'Update this drive  (needs internet)'
    Say 'Gets the newest version of this kit, firmware, web app, phone & desktop apps and'
    Say 'Raspberry Pi images, and replaces the old ones on this USB drive.'; Say ''
    $py = Get-Python
    if (-not $py) { Fail "Couldn't start the updater on this computer (needs Windows 10 or newer)."; Pause-Menu; return }
    $script = Join-Path $SYS 'maintenance\build_usb.py'
    Say "Checking what's new..."
    & $py $script --check
    $rc = $LASTEXITCODE
    if ($rc -eq 0) { Pause-Menu; return }
    if ($rc -ne 3) { Fail "Couldn't reach the internet. Connect and try again."; Pause-Menu; return }
    Warn "This can take 10-30 minutes. Don't unplug the drive while it runs."
    $a = Read-Host 'Download the updates now? [Y/n]'
    if ($a -match '^(n|no)$') { return }
    Say ''
    & $py $script --update-kit
    if ($LASTEXITCODE -eq 0) {
        Ok 'This drive is up to date.'
        Remove-Item $UpdRc, $UpdOut -ErrorAction SilentlyContinue; $script:UpdShown = $false
    }
    else { Fail 'Some parts did not update (see above). Run the update again to retry - the drive still works.' }
    $now = ''
    try { $now = ((Get-Content (Join-Path $USB 'VERSION') -TotalCount 1 -ErrorAction Stop) -replace '[^0-9.]', '') } catch { }
    if ($now -and $now -ne $KitVer) {
        $a = Read-Host "`nThe kit was updated to v$now. Restart this window now to use it? [Y/n]"
        if ($a -notmatch '^(n|no)$') { $script:Restart = $true; return }
    }
    Pause-Menu
}

function Show-Menu {
    Clear-Host
    Write-Host ''
    $kitVer = '?'
    try { $kitVer = (Get-Content (Join-Path $USB 'VERSION') -TotalCount 1 -ErrorAction Stop).Trim() } catch { }
    Write-Host '   =============================================' -ForegroundColor Green
    Write-Host ('   EMERGENCY KIT for Meshtastic   v' + $kitVer) -ForegroundColor Green
    Write-Host '   =============================================' -ForegroundColor Green
    if (Get-UpdateSummary) {
        $script:UpdShown = $true; $script:UpdRow = [Console]::CursorTop
        Write-UpdateLine $true; Write-Host ''
    }
    Write-Host ''
    Say '   1  Open Meshtastic in the browser  (talk on the mesh / flash a radio)'
    Say '   2  Install the Meshtastic app on this computer'
    Say '   3  Put the Meshtastic app on an Android phone'
    Say '   4  Make a Raspberry Pi SD card'
    Say '   5  Help guide'
    Say '   6  Radio not detected? Install USB drivers'
    Say '   U  Update this drive  (needs internet)'
    Say '   R  Restart this window  (use after an update)'
    Say '   Q  Quit'
    Write-Host ''
    Write-Host '   Keep this window open while you use Meshtastic. Closing it stops everything.' -ForegroundColor Yellow
}

try {
    if ($RestartedFrom -and $RestartedFrom -eq $KitVer) {
        Say 'Restarted. Your browser tabs keep working (reload a page if it shows an error).'
        Start-All | Out-Null
    } else {
        Say 'Starting Meshtastic...'
        Do-Open
    }
    Start-UpdateCheck
    Start-Sleep 1
    while ($true) {
        Show-Menu
        $choice = Read-Choice
        switch ($choice) {
            '1' { Do-Open }
            ''  { Do-Open }
            '2' { Do-Desktop }
            '3' { Do-Android }
            '4' { Do-Pi }
            '5' { if (Start-All) { Open-Url "http://localhost:$HUB_PORT/guide.html" } }
            '6' { Do-Drivers }
            'u' { Do-Update }
            'r' { $script:Restart = $true }
            { $_ -in 'q', 'Q' } { Say 'Stopping Meshtastic. Bye!'; break }
        }
        if ($choice -in 'q', 'Q') { break }
        if ($script:Restart) { break }
    }
} finally {
    Stop-All
}
# Restart: start the launcher again from the drive, in this same window, so an updated kit
# takes effect. The browser is only reopened if the kit's version changed.
if ($script:Restart) {
    Say ''; Say 'Restarting...'
    Start-Sleep 1
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $SYS 'launcher.ps1') -RestartedFrom $KitVer
    exit $LASTEXITCODE
}
