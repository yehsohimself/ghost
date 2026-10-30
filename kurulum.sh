#!/bin/bash
# Ghost install (macOS 14+, Apple silicon). No sudo. Needs Homebrew (https://brew.sh) and Git.
# Kurulum (macOS 14+, Apple işlemci). Sudo istemez; Homebrew ve Git gerekir.
set -e
cd "$(dirname "$0")"
KOK="$(pwd)"

echo "1/4 Tools via Homebrew: ffmpeg, deno, uv"
if ! command -v brew >/dev/null; then echo "Homebrew not found. Install it first: https://brew.sh"; exit 1; fi
for p in ffmpeg deno uv; do brew list "$p" >/dev/null 2>&1 || brew install "$p"; done

echo "2/4 Python environment (.venv) and packages"
[ -d .venv ] || uv venv .venv --python 3.12
uv pip install --python .venv/bin/python --only-binary :all: -r requirements.txt

echo "3/4 Settings and folders"
[ -f ayarlar.json ] || cp ayarlar.ornek.json ayarlar.json
mkdir -p profil ghost kayitlar yuklemeler kareler indirilenler modeller .onbellek

echo "4/4 Start at login (LaunchAgent)"
LA="$HOME/Library/LaunchAgents"; mkdir -p "$LA"
ETIKET="com.yehso.transkript"   # the app restarts itself with this label (yeniden_baslat.py)
cat > "$LA/$ETIKET.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$ETIKET</string>
  <key>ProgramArguments</key><array><string>$KOK/.venv/bin/python</string><string>$KOK/site.py</string></array>
  <key>WorkingDirectory</key><string>$KOK</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin</string></dict>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$KOK/site.log</string><key>StandardErrorPath</key><string>$KOK/site.log</string>
</dict></plist>
PLIST
launchctl bootout "gui/$(id -u)/$ETIKET" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$LA/$ETIKET.plist"

echo
echo "Done. Open http://127.0.0.1:8767 (later: double-click Ghost.command) and set up your voice."
if ! command -v claude >/dev/null && [ ! -x "$HOME/.local/bin/claude" ]; then
  echo "Ghost writes with Claude through your own subscription. Install Claude Code and sign in once:"
  echo "    curl -fsSL https://claude.ai/install.sh | bash && claude auth login"
fi
echo "Optional: Chrome extension (reads your own X posts and stats, never posts):"
echo "    chrome://extensions → Developer mode → Load unpacked → the 'uzanti' folder"
