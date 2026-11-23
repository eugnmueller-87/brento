#!/bin/sh
# Installs Brento for the person running it, on a Mac or on Linux. No admin rights, no package manager.
# On a Mac it also starts Brento at every login (a launchd agent) and puts a Brento app in ~/Applications.
#   sh install.sh                 install, start at login, open the setup
#   sh install.sh --no-autostart  install without the start at login
#   sh install.sh --remove        take it out again (the settings folder stays)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LABEL="app.brento.server"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
APP="$HOME/Applications/Brento.app"
BIN="$HOME/.local/bin"
MAC=0; [ "$(uname)" = "Darwin" ] && MAC=1
# The same folder settings.py picks: BRENTO_HOME, else an existing ~/.leitstand, else ~/.brento.
DIR="${BRENTO_HOME:-}"
if [ -z "$DIR" ]; then if [ -d "$HOME/.leitstand" ]; then DIR="$HOME/.leitstand"; else DIR="$HOME/.brento"; fi; fi

AUTOSTART=1
case "${1:-}" in
  --remove)
    if [ $MAC = 1 ]; then
      launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
      rm -f "$AGENT"; rm -rf "$APP"
    fi
    rm -f "$BIN/brento"
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
    echo "When it is done, double-click Install Brento again."
  else
    echo "Brento needs Python 3.9 or newer. Install it with your package manager (for example: sudo apt install python3), then run this again."
  fi
  exit 1
fi
echo "Python: $PY"
if ! "$PY" -c 'import urllib.request; urllib.request.urlopen("https://api.github.com", timeout=10)' >/dev/null 2>&1; then
  echo "Note: this Python could not open an https page (no internet, or missing certificates)."
  echo "      Python from python.org: open Applications, the Python folder, and double-click Install Certificates.command."
fi
mkdir -p "$DIR" "$BIN"

# The brento command: opens Brento, and starts it first when nothing answers on port 8770.
cat > "$BIN/brento" <<EOF
#!/bin/sh
# Opens Brento. Starts it first when nothing answers on port 8770. Written by install.sh.
up() { "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8770/api/tools', timeout=2)" >/dev/null 2>&1; }
if ! up; then
  if [ -f "$AGENT" ]; then
    launchctl kickstart "gui/\$(id -u)/$LABEL" >/dev/null 2>&1 || true
  else
    nohup "$PY" "$HERE/server.py" >> "$DIR/server.log" 2>&1 &
  fi
  i=0
  while [ \$i -lt 30 ] && ! up; do sleep 0.5; i=\$((i + 1)); done
fi
if command -v open >/dev/null 2>&1; then open http://127.0.0.1:8770/; else xdg-open http://127.0.0.1:8770/ >/dev/null 2>&1 & fi
EOF
chmod +x "$BIN/brento"
echo "Command: $BIN/brento"

xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
if [ $MAC = 1 ] && [ $AUTOSTART = 1 ]; then
  # Starts at every login. A crash restarts it; a clean stop (another Brento already answers) does not.
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$(xml "$PY")</string><string>$(xml "$HERE/server.py")</string></array>
  <key>WorkingDirectory</key><string>$(xml "$HERE")</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$(xml "$DIR/server.log")</string>
  <key>StandardErrorPath</key><string>$(xml "$DIR/server.log")</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$(xml "$BIN:$DIR/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")</string></dict>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  sleep 1
  if launchctl bootstrap "gui/$(id -u)" "$AGENT" >/dev/null 2>&1; then
    echo "Start at login: on"
  else
    echo "Start at login: set up, it takes effect at your next login."
  fi
elif [ $MAC = 1 ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  rm -f "$AGENT"
  echo "Start at login: off"
fi

if [ $MAC = 1 ]; then
  # A small app, so Spotlight and Launchpad find Brento. Made on this Mac, so macOS has nothing to block.
  mkdir -p "$HOME/Applications"
  rm -rf "$APP"
  if osacompile -o "$APP" -e "do shell script quoted form of \"$BIN/brento\" & \" >/dev/null 2>&1 &\"" >/dev/null 2>&1; then
    if sips -s format icns "$HERE/web/icon-512.png" --out "$APP/Contents/Resources/applet.icns" >/dev/null 2>&1; then
      codesign --force --sign - "$APP" >/dev/null 2>&1 || true
      touch "$APP"
    fi
    echo "App: ~/Applications/Brento (Spotlight finds it)"
  fi
fi

"$BIN/brento"
echo "Brento opens in your browser. The first page is the setup."
