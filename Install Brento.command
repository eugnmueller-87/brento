#!/bin/sh
# Double-click this on a Mac. It installs Brento for you and opens the setup in your browser. No admin rights.
cd "$(dirname "$0")" || exit 1
sh ./install.sh
echo
echo "Done. You can close this window."
