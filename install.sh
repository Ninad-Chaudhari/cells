#!/usr/bin/env bash
# Installs cells for the current user. Safe to run again: it updates what is there and keeps your config.
#
#   ./install.sh [--with-codex] [--with-chromium] [--with-knowledge] [--yes]
#
# It checks the system packages, installs the Node pieces into $CELLS_HOME/opt (no global npm),
# writes ~/.config/cells/config, links `cell` into ~/.local/bin, starts the dashboard as a systemd
# user service, and finishes with `cell doctor`.
set -euo pipefail

PLAYWRIGHT_MCP_VERSION=0.0.84
CODEX_VERSION=0.167.0
OPENCONTEXT_VERSION=0.2.2

APP="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
WITH_CODEX=0 WITH_CHROMIUM=0 WITH_KNOWLEDGE=0 YES=0
for arg in "$@"; do
    case "$arg" in
        --with-codex) WITH_CODEX=1 ;;
        --with-chromium) WITH_CHROMIUM=1 ;;
        --with-knowledge) WITH_KNOWLEDGE=1 ;;
        --yes|-y) YES=1 ;;
        -h|--help) sed -n 2,9p "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $arg (see --help)" >&2; exit 2 ;;
    esac
done

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
note() { printf '  \033[33m•\033[0m %s\n' "$*"; }
die() { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }
npm_into() { local dir="$1"; shift; mkdir -p "$dir"; npm install --prefix "$dir" --no-fund --no-audit --loglevel=error "$@" >/dev/null; }

[ "$(uname -s)" = Linux ] || die "cells runs on Linux (Xvfb, bubblewrap, systemd). On a Mac, use a Linux VM such as OrbStack or Multipass."
command -v systemctl >/dev/null || die "cells needs systemd."

bold "System packages"
declare -A APT=([bwrap]=bubblewrap [Xvfb]=xvfb [xdotool]=xdotool [xauth]=xauth [mcookie]=util-linux [python3]=python3 [git]=git [PIL]=python3-pil [wm]=xfwm4)
declare -A DNF=([bwrap]=bubblewrap [Xvfb]=xorg-x11-server-Xvfb [xdotool]=xdotool [xauth]=xorg-x11-xauth [mcookie]=util-linux [python3]=python3 [git]=git [PIL]=python3-pillow [wm]=xfwm4)
missing=()
for c in bwrap Xvfb xdotool xauth mcookie python3 git; do command -v "$c" >/dev/null || missing+=("$c"); done
python3 -c "import PIL.ImageGrab" 2>/dev/null || missing+=(PIL)
command -v xfwm4 >/dev/null || command -v openbox >/dev/null || command -v fluxbox >/dev/null || missing+=(wm)
if [ ${#missing[@]} -gt 0 ]; then
    if command -v apt-get >/dev/null; then pm="apt-get install -y"; pkgs=$(for m in "${missing[@]}"; do echo "${APT[$m]}"; done | sort -u)
    elif command -v dnf >/dev/null; then pm="dnf install -y"; pkgs=$(for m in "${missing[@]}"; do echo "${DNF[$m]}"; done | sort -u)
    else die "missing: ${missing[*]}. Install them with your package manager and run this again."; fi
    cmd="sudo $pm $(echo $pkgs)"
    note "missing: ${missing[*]}"
    if [ "$YES" = 1 ] || { [ -t 0 ] && read -rp "  Run: $cmd ? [y/N] " a && [[ "$a" =~ ^[Yy] ]]; }; then
        $cmd
    else
        die "install them with: $cmd"
    fi
fi
ok "bubblewrap, Xvfb, xdotool, xauth, Pillow, git, window manager"

command -v node >/dev/null && command -v npm >/dev/null || die "Node.js 18+ with npm is needed: https://nodejs.org (or your package manager)."
node_major=$(node -p 'process.versions.node.split(".")[0]')
[ "$node_major" -ge 18 ] || die "Node.js 18+ is needed (found $(node --version))."
ok "Node.js $(node --version)"

# shellcheck source=bin/cells-env
. "$APP/bin/cells-env"
mkdir -p "$CELLS_HOME/opt" "$(dirname "$CELLS_CONFIG")"
chmod 700 "$CELLS_HOME"

if [ ! -f "$CELLS_CONFIG" ]; then
    cat > "$CELLS_CONFIG" <<'EOF'
# cells config, read by every cell command and the dashboard. All lines are optional.
# CELLS_HOME="$HOME/cells"          # state, history and the shared knowledge base
# CELLS_MAX=20                      # agents working at once
# CELLS_OWNER="Sam"                 # how agents address you
# CELLS_RUNTIME=claude              # default runtime for new agents: claude or codex
# CELLS_CODEX_MODEL=                # model for Codex agents; empty = Codex's default
# CELLS_SCREEN_SIZE=1280x800        # each agent's screen
# CELLS_MEMORY_MAX=8G               # memory cap per agent
# CELLS_CHROME_PROFILE=             # copy this Chrome profile into each agent (keeps sign-ins); empty = fresh browser
# CELLS_DASH_TCP=127.0.0.1:6080     # also serve the dashboard on TCP; keep it on localhost
EOF
fi
set_config() {
    local key="$1" value
    value=$(printf '%q' "$2")
    if grep -q "^$key=" "$CELLS_CONFIG"; then sed -i "s|^$key=.*|$key=$value|" "$CELLS_CONFIG"
    else printf '%s=%s\n' "$key" "$value" >> "$CELLS_CONFIG"; fi
}
in_config() { grep -q "^$1=" "$CELLS_CONFIG"; }

bold "Agent runtime"
if [ -z "$CELLS_CLAUDE" ] || [ ! -x "$CELLS_CLAUDE" ]; then
    note "installing Claude Code into $CELLS_HOME/opt/claude-code"
    npm_into "$CELLS_HOME/opt/claude-code" @anthropic-ai/claude-code
    CELLS_CLAUDE="$CELLS_HOME/opt/claude-code/node_modules/.bin/claude"
fi
in_config CELLS_CLAUDE || set_config CELLS_CLAUDE "$(readlink -f "$CELLS_CLAUDE")"
in_config CELLS_NODE || set_config CELLS_NODE "$(readlink -f "$(command -v node)")"
ok "Claude Code $("$CELLS_CLAUDE" --version 2>/dev/null | head -1)"

if [ "$WITH_CODEX" = 1 ]; then
    npm_into "$CELLS_HOME/opt/codex" "@openai/codex@$CODEX_VERSION"
    set_config CELLS_CODEX "$CELLS_HOME/opt/codex/node_modules/.bin/codex"
    ok "Codex $CODEX_VERSION"
fi

npm_into "$CELLS_HOME/opt/playwright-mcp" "@playwright/mcp@$PLAYWRIGHT_MCP_VERSION"
ok "Playwright MCP $PLAYWRIGHT_MCP_VERSION"

if [ "$WITH_CHROMIUM" = 1 ] || [ -z "$CELLS_CHROME_BIN" ]; then
    note "downloading Playwright's Chromium"
    "$CELLS_HOME/opt/playwright-mcp/node_modules/.bin/playwright" install chromium >/dev/null
    chrome=$(find "$HOME/.cache/ms-playwright" -path '*/chromium-*/chrome-linux*/chrome' -type f 2>/dev/null | sort -V | tail -1)
    [ -n "$chrome" ] || die "Chromium download did not produce a browser; try: npx playwright install chromium"
    set_config CELLS_CHROME_BIN "$chrome"
    CELLS_CHROME_BIN="$chrome"
elif ! in_config CELLS_CHROME_BIN; then
    set_config CELLS_CHROME_BIN "$(readlink -f "$CELLS_CHROME_BIN")"
fi
ok "browser $CELLS_CHROME_BIN"

if [ "$WITH_KNOWLEDGE" = 1 ]; then
    npm_into "$CELLS_HOME/opt/opencontext" "@aicontextlab/cli@$OPENCONTEXT_VERSION"
    ok "OpenContext $OPENCONTEXT_VERSION (knowledge search)"
fi

bold "Command and dashboard"
mkdir -p "$HOME/.local/bin"
ln -sfn "$APP/bin/cell" "$HOME/.local/bin/cell"
ok "cell → ~/.local/bin/cell"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) note "add ~/.local/bin to your PATH" ;; esac

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
cat > "$unit_dir/$CELLS_UNIT-dash.service" <<EOF
[Unit]
Description=Cells dashboard (OS for agents)

[Service]
Environment=CELLS_CONFIG=$CELLS_CONFIG
ExecStart=$APP/bin/cell dashboard
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --quiet "$CELLS_UNIT-dash"
systemctl --user restart "$CELLS_UNIT-dash"
ok "service $CELLS_UNIT-dash"
if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != yes ]; then
    note "to keep agents running after you log out: sudo loginctl enable-linger $USER"
fi

bold "Check"
"$APP/bin/cell" doctor || true

bold "Next"
[ -s "$CELLS_TOKEN_FILE" ] || [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}" ] || \
    echo "  1. Sign in:  claude setup-token   then paste the token into:  cell auth claude"
[ "$WITH_CODEX" = 1 ] && echo "     Codex:    cell auth codex   (an OpenAI API key; or cell auth codex --access-token)"
echo "  2. Open the dashboard from your laptop:"
echo "       ssh -N -L 6080:$CELLS_HOME/run/dash.sock $(whoami)@$(hostname -f 2>/dev/null || hostname)"
echo "     then visit http://localhost:6080"
echo "  3. Start an agent:  cell up research \"Summarize the top stories on Hacker News\""
