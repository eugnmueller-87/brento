#!/bin/sh
# Installs Brento for the person running it, on a Mac or on Linux. No admin rights, no package manager.
# On a Mac it also starts Brento at every login (a launchd agent) and puts a Brento app in ~/Applications.
# The Mac installer (Brento-Mac.pkg) runs this too, after it has unpacked everything.
#   sh install.sh                 install, start at login, open the setup
#   sh install.sh --no-autostart  install without the start at login
#   sh install.sh --remove        take it out again (the settings folder stays)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LABEL="app.brento.server"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
APP="$HOME/Applications/Brento.app"
UNAPP="$HOME/Applications/Uninstall Brento.app"
BASE="$HOME/Library/Application Support/Brento"
BIN="$HOME/.local/bin"
MAC=0; [ "$(uname)" = "Darwin" ] && MAC=1
# The same folder settings.py picks: BRENTO_HOME, else an existing ~/.leitstand, else ~/.brento.
DIR="${BRENTO_HOME:-}"
if [ -z "$DIR" ]; then if [ -d "$HOME/.leitstand" ]; then DIR="$HOME/.leitstand"; else DIR="$HOME/.brento"; fi; fi

AUTOSTART=1
case "${1:-}" in
  --remove)
    if [ $MAC = 1 ] && [ "$HERE" = "$BASE/app" ] && [ -x "$BASE/python/bin/Brento" ]; then
      "$BASE/python/bin/Brento" "$HERE/launcher.py" --stop >/dev/null 2>&1 || true
    fi
    if [ $MAC = 1 ]; then
      launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
      rm -f "$AGENT"; rm -rf "$APP" "$UNAPP"
    fi
    rm -f "$BIN/brento"
    if [ $MAC = 1 ] && [ "$HERE" = "$BASE/app" ]; then
      # Installed by the package: the program goes too. A team's setup file is kept with the settings.
      if [ -f "$HERE/team.json" ]; then mkdir -p "$DIR"; cp -p "$HERE/team.json" "$DIR/team.json"; fi
      rm -rf "$BASE"
    fi
    echo "Brento is removed. Your settings stay in $DIR; delete that folder too if you want them gone."
    exit 0 ;;
  --no-autostart) AUTOSTART=0 ;;
  "") ;;
  *) echo "Unknown option: $1"; exit 1 ;;
esac

ok_python() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; }
PY=""
# Homebrew's Python first, Apple's last: on a Mac without developer tools, /usr/bin/python3 only offers to install them.
for cand in "${BRENTO_PYTHON:-}" /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 2>/dev/null || true)" /usr/bin/python3; do
  if [ -n "$cand" ] && [ -x "$cand" ] && ok_python "$cand"; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  if [ $MAC = 1 ]; then
    xcode-select --install >/dev/null 2>&1 || true
    echo "Brento needs Python 3, which comes with Apple's free command line tools."
    echo "A window from Apple opened: click Install (no Xcode needed, a few minutes)."
    echo "When it is done, double-click Install Brento again. Or use Brento-Mac.pkg, which brings Python along."
  else
    echo "Brento needs Python 3.9 or newer. Install it with your package manager (for example: sudo apt install python3), then run this again."
  fi
  exit 1
fi
echo "Python: $PY"
if [ -z "${BRENTO_PACKAGED:-}" ] && ! "$PY" -c 'import urllib.request; urllib.request.urlopen("https://api.github.com", timeout=10)' >/dev/null 2>&1; then
  echo "Note: this Python could not open an https page (no internet, or missing certificates)."
  echo "      Python from python.org: open Applications, the Python folder, and double-click Install Certificates.command."
fi
mkdir -p "$DIR" "$BIN"
# Private links and the key to Brento lie in there. On a Mac other people's accounts could look into it otherwise.
chmod 700 "$DIR" 2>/dev/null || true

# The brento command: opens Brento, and starts it first when it is not running.
cat > "$BIN/brento" <<EOF
#!/bin/sh
# Opens Brento, and starts it first when it is not running. Written by install.sh.
exec "$PY" "$HERE/launcher.py" "\$@"
EOF
chmod +x "$BIN/brento"
echo "Command: $BIN/brento"

xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
if [ $MAC = 1 ]; then
  # An older Brento gives way before its login service is written anew.
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  rm -f "$AGENT"
fi
if [ $MAC = 1 ] && [ $AUTOSTART = 1 ]; then
  # Starts at every login. A crash restarts it; a clean stop (another Brento already answers) does not. Without
  # MaterializeDatalessFiles a login service may not fetch notes that lie only in iCloud (getiopolicy_np says off).
  mkdir -p "$HOME/Library/LaunchAgents"
  HOME_ENTRY=""
  if [ -n "${BRENTO_HOME:-}" ]; then HOME_ENTRY="<key>BRENTO_HOME</key><string>$(xml "$BRENTO_HOME")</string>"; fi
  cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$(xml "$PY")</string><string>-X</string><string>utf8</string><string>$(xml "$HERE/server.py")</string></array>
  <key>WorkingDirectory</key><string>$(xml "$HERE")</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>MaterializeDatalessFiles</key><true/>
  <key>StandardOutPath</key><string>$(xml "$DIR/server.log")</string>
  <key>StandardErrorPath</key><string>$(xml "$DIR/server.log")</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$(xml "$BIN:$DIR/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")</string>$HOME_ENTRY</dict>
</dict>
</plist>
EOF
  echo "Start at login: on"
elif [ $MAC = 1 ]; then
  echo "Start at login: off"
fi

# A small app, made on this Mac, so macOS has nothing to block.
make_app() {
  rm -rf "$1"
  osacompile -o "$1" "$2" >/dev/null 2>&1 || return 0
  if sips -s format icns "$HERE/web/icon-512.png" --out "$1/Contents/Resources/applet.icns" >/dev/null 2>&1; then
    codesign --force --sign - "$1" >/dev/null 2>&1 || true
    touch "$1"
  fi
}
quoted() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
if [ $MAC = 1 ]; then
  mkdir -p "$HOME/Applications"
  SCRIPTS=$(mktemp -d "${TMPDIR:-/tmp}/brento.XXXXXX")
  cat > "$SCRIPTS/open.applescript" <<EOF
do shell script quoted form of "$(quoted "$BIN/brento")" & " >/dev/null 2>&1 &"
EOF
  make_app "$APP" "$SCRIPTS/open.applescript"
  [ -d "$APP" ] && echo "App: ~/Applications/Brento (Spotlight finds it)"
  if [ -n "${BRENTO_PACKAGED:-}" ]; then
    # The settings are only offered for deletion where Brento itself put them.
    cat > "$SCRIPTS/remove.applescript" <<EOF
set answer to button returned of (display dialog "Remove Brento from this Mac?" & return & return & "Your notes, your board and your calendar stay as they are." with title "Brento" buttons {"Keep Brento", "Remove Brento"} default button "Keep Brento" with icon caution)
if answer is "Remove Brento" then
	do shell script "/bin/sh " & quoted form of "$(quoted "$HERE/install.sh")" & " --remove"
	set settingsFolder to "$(quoted "$DIR")"
	if settingsFolder is "$(quoted "$HOME/.brento")" then
		set more to button returned of (display dialog "Brento is removed." & return & return & "Delete its settings too? That is the folder .brento in your home folder, with your calendar link, the Slack link and the paired phones. If you may come back to Brento, keep them." & return & return & "Your sign-in to GitHub stays on this Mac. You can take it back under github.com/settings/applications." with title "Brento" buttons {"Delete the settings", "Keep the settings"} default button "Keep the settings")
		if more is "Delete the settings" then do shell script "/bin/rm -rf " & quoted form of settingsFolder
	else
		display dialog "Brento is removed." & return & return & "Your settings stay in your home folder." with title "Brento" buttons {"OK"} default button 1
	end if
end if
EOF
    make_app "$UNAPP" "$SCRIPTS/remove.applescript"
  fi
  rm -rf "$SCRIPTS"
fi

# Stops whichever Brento runs on this computer, starts this one and opens the setup in the browser.
"$PY" "$HERE/launcher.py" --replace || echo "Brento did not start yet. It starts at the next login, or open the Brento app."
echo "Brento opens in your browser. The first page is the setup."
