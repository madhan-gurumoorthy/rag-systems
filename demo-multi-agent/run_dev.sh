#!/usr/bin/env bash
# Local development server with hot-reload.
#
# Presents an interactive menu to choose the Dynaconf environment, pack,
# agent name, and port before starting uvicorn.  All prompts can be
# bypassed via flags or pre-set environment variables.
#
# Requirements:
#   • Python ≥ 3.11   (stdlib tomllib used for the Akeyless secrets merge)
#   • macOS: Xcode Command Line Tools; Homebrew is offered to install
#     Python and Node if either is missing.
#   • Linux: a python3.11+ binary on PATH and a working `venv` module.
#
# Usage:
#   ./run_dev.sh [OPTIONS]
#
# Options:
#   --env=ENV       Dynaconf environment (development|stage|production)
#   --pack=ID       Pack ID to load (must exist under packs/)
#   --agent=NAME    DYNACONF_AGENT_NAME override  [default: <pack_id>_agent]
#   --port=PORT     uvicorn listen port            [default: 8000]
#   --host=HOST     uvicorn bind address           [default: 0.0.0.0]
#   --no-reload     Disable uvicorn --reload
#   --skip-venv     Skip virtual environment creation and dependency sync
#   --skip-secrets  Skip the Akeyless secret sync step
#   --with-console  Mount the local-only /console SPA (skip the prompt)
#   --skip-console  Do NOT mount the local-only /console SPA
#   --rebuild-console  Wipe static/dist + node_modules and rebuild the SPA
#   --skip-landing     Do NOT build the landing-page SPA (frontend/dist/)
#   --rebuild-landing  Wipe frontend/dist + node_modules and rebuild the SPA
#   --yes, -y       Non-interactive — skip all prompts, use defaults/flags
#   --help, -h      Show this help and exit
#
# Akeyless secret sync:
#   Pulls canonical secrets.toml from
#   /Prod/WCNP/homeoffice/MATBOT_developers/agent-factory/config and merges it
#   into agent_factory/infrastructure/secrets.toml — Akeyless sections win,
#   local-only sections preserved. CLI resolved from repo root (./akeyless)
#   first, then $PATH. On a fresh machine the script offers to install the CLI
#   (Homebrew on macOS) and configure Walmart's shared SAML profile; identity
#   comes from browser SAML at first fetch. Requires MATBOT_developers AD-group
#   membership — request access via the ServiceNow link printed on failure.
#
# Landing page (/):
#   A Vite + React + TypeScript SPA at frontend/ that FastAPI mounts at
#   the site root via mount_homepage() in app.py. The mount is automatic
#   whenever frontend/dist/index.html exists — there is no env-var gate.
#   The script builds the dist directory on demand (first run, or when
#   sources are newer than the build) and skips the build when current.
#   Use --skip-landing to leave the existing dist untouched, or
#   --rebuild-landing to force a clean wipe-and-rebuild.
#
# Local console (/console):
#   A Vite + React SPA that exercises POST /a2a/invoke and
#   POST /a2a/invoke-stream against the running server. The script asks
#   whether to mount it (default Y) and builds the dist directory on
#   demand. The mount is opt-in via the MATBOT_ENABLE_CONSOLE env var
#   so deployed instances never expose it.
#
#   Node ≥ 18 is required for both Vite builds (landing + console). The
#   script auto-detects the active node, falls back to sourcing
#   ~/.nvm/nvm.sh, and — when no compatible Node is found — offers to
#   install one via (in order) an existing nvm, Homebrew on macOS, or a
#   fresh nvm install. Dependencies are installed with `npm ci` when
#   package-lock.json is present.
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
RESET=$'\033[0m'
readonly RED GREEN YELLOW CYAN BOLD RESET

# ── Helpers ───────────────────────────────────────────────────────────────────
banner() { printf "\n${BOLD}${CYAN}▶  %s${RESET}\n\n" "$*"; }
ok()     { printf "${GREEN}✔  %s${RESET}\n" "$*"; }
info()   { printf "${YELLOW}ℹ  %s${RESET}\n" "$*"; }
err()    { printf "${RED}✗  %s${RESET}\n" "$*" >&2; }

# Prompt without newline. printf (not read -rp) keeps stale ANSI bytes out of
# readline's cursor model so escape sequences don't bleed into the read var.
prompt() { printf "%s" "$1"; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
REQS_FILE="$SCRIPT_DIR/requirements.txt"
SECRETS_FILE="$SCRIPT_DIR/agent_factory/infrastructure/secrets.toml"

# ── Akeyless ─────────────────────────────────────────────────────────────────
AKEYLESS_SECRET_PATH="/Prod/WCNP/homeoffice/MATBOT_developers/agent-factory/config"
AKEYLESS_AD_GROUP="MATBOT_developers"
AKEYLESS_ACCESS_REQUEST_URL="https://walmartglobal.service-now.com/wm_sp?id=sc_cat_item_guide&sys_id=b3234c3b4fab8700e4cd49cf0310c7d7"

# Walmart's shared SAML access-id and corporate gateway endpoints. Corporate-wide,
# not per-user; identity is bound at first fetch via the browser SAML flow.
AKEYLESS_WALMART_ACCESS_ID="p-0vujs7ur39a3"
AKEYLESS_GATEWAY_URL_DEFAULT="https://akeyless.gw.prod.glb.us.walmart.net:8080"
AKEYLESS_GATEWAY_CONFIG_URL_DEFAULT="akeyless.gw.prod.glb.us.walmart.net:8000"
AKEYLESS_SETUP_DOC="https://wibey.walmart.com/loop/reply/view/How-to-configure-Akeyless-Vault-CLI-SOR3163"

readonly AKEYLESS_SECRET_PATH AKEYLESS_AD_GROUP AKEYLESS_ACCESS_REQUEST_URL
readonly AKEYLESS_WALMART_ACCESS_ID AKEYLESS_GATEWAY_URL_DEFAULT AKEYLESS_GATEWAY_CONFIG_URL_DEFAULT AKEYLESS_SETUP_DOC

# Populated by _resolve_akeyless_bin(): CLI path and display label.
AKEYLESS_BIN=""
AKEYLESS_BIN_LABEL=""

# ── Defaults (honour pre-set env vars so CI can skip menus) ──────────────────
OPT_ENV="${ENV_FOR_DYNACONF:-}"
OPT_PACK="${DEFAULT_PACK_ID:-}"
OPT_AGENT="${DYNACONF_AGENT_NAME:-}"
OPT_PORT="${DEV_PORT:-8000}"
OPT_HOST="0.0.0.0"
OPT_RELOAD="--reload"
OPT_YES=false
OPT_SKIP_VENV=false
OPT_SKIP_SECRETS=false
OPT_CONSOLE=""              # "", "yes", or "no" — empty means "ask interactively"
OPT_REBUILD_CONSOLE=false   # --rebuild-console wipes dist + node_modules
OPT_LANDING="yes"           # "yes" or "no" — landing page is built by default
OPT_REBUILD_LANDING=false   # --rebuild-landing wipes dist + node_modules

_DEFAULT_PACK="gif_tote_validation"
_DEFAULT_ENV="development"
readonly _DEFAULT_PACK _DEFAULT_ENV

# Temp files registered here are unlinked on every exit path.
TMP_FILES=()
_cleanup() {
    [[ ${#TMP_FILES[@]} -eq 0 ]] && return 0
    rm -f "${TMP_FILES[@]}" 2>/dev/null || true
}

trap '_cleanup; printf "\n"; info "Interrupted."; exit 130' INT
trap '_cleanup' EXIT

# ── Argument parsing ──────────────────────────────────────────────────────────
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --env=*)      OPT_ENV="${1#*=}" ;;
            --pack=*)     OPT_PACK="${1#*=}" ;;
            --agent=*)    OPT_AGENT="${1#*=}" ;;
            --port=*)     OPT_PORT="${1#*=}" ;;
            --host=*)     OPT_HOST="${1#*=}" ;;
            --no-reload)  OPT_RELOAD="" ;;
            --skip-venv)     OPT_SKIP_VENV=true ;;
            --skip-secrets)  OPT_SKIP_SECRETS=true ;;
            --skip-console)     OPT_CONSOLE="no" ;;
            --with-console)     OPT_CONSOLE="yes" ;;
            --rebuild-console)  OPT_REBUILD_CONSOLE=true; OPT_CONSOLE="yes" ;;
            --skip-landing)     OPT_LANDING="no" ;;
            --rebuild-landing)  OPT_REBUILD_LANDING=true; OPT_LANDING="yes" ;;
            --yes|-y)        OPT_YES=true ;;
            --help|-h)
                sed -n '4,/^set -euo/{ /^set -euo/d; p; }' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
                exit 0
                ;;
            *)
                err "Unknown option: $1  (try --help)"
                exit 1
                ;;
        esac
        shift
    done
}

# ── Port management ───────────────────────────────────────────────────────────
_port_in_use() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN &>/dev/null
}

_next_free_port() {
    # Scan up to 100 ports above the requested one.
    local p=$(( $1 + 1 ))
    local max=$(( $1 + 100 ))
    while (( p <= max )) && _port_in_use "$p"; do
        p=$(( p + 1 ))
    done
    if (( p > max )); then
        return 1
    fi
    echo "$p"
}

handle_port() {
    _port_in_use "$OPT_PORT" || return 0

    local pid pname next
    pid=$(lsof -nP -iTCP:"$OPT_PORT" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)
    pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
    if ! next=$(_next_free_port "$OPT_PORT"); then
        err "Port ${OPT_PORT} is occupied and no free port was found within 100 above it."
        exit 1
    fi

    echo ""
    err "Port ${OPT_PORT} is occupied by PID ${pid} (${pname})."

    if $OPT_YES; then
        info "Auto-selecting next free port: ${next}"
        OPT_PORT="$next"
        return 0
    fi

    printf "\n"
    printf "  [1] Kill PID %s (%s) and keep port %s\n" "$pid" "$pname" "$OPT_PORT"
    printf "  [2] Use next free port (%s)\n" "$next"
    printf "  [3] Abort\n\n"
    local _choice
    prompt "Choice [1-3]: "; read -r _choice || _choice=""

    case "${_choice:-}" in
        1)
            if ! kill "$pid" 2>/dev/null; then
                err "Could not kill PID ${pid}. Try: sudo kill ${pid}"
                exit 1
            fi
            ok "Sent SIGTERM to PID ${pid}"
            # Poll up to 3s, then SIGKILL.
            local waits=0
            while _port_in_use "$OPT_PORT"; do
                if (( waits >= 30 )); then
                    info "Port still busy after 3s — escalating to SIGKILL."
                    kill -9 "$pid" 2>/dev/null || true
                    sleep 0.5
                    break
                fi
                sleep 0.1
                waits=$(( waits + 1 ))
            done
            if _port_in_use "$OPT_PORT"; then
                err "Port ${OPT_PORT} did not free up. Aborting."
                exit 1
            fi
            ok "Port ${OPT_PORT} is free"
            ;;
        2)
            OPT_PORT="$next"
            ok "Using port ${OPT_PORT}"
            ;;
        3|"")
            info "Aborted."
            exit 0
            ;;
        *)
            err "Invalid choice."
            exit 1
            ;;
    esac
}

# ── Python / venv helpers ─────────────────────────────────────────────────────

# Minimum Python version required to run the project.  stdlib `tomllib`
# (used by the Akeyless secrets merge) is the binding constraint.
PY_MIN_MAJOR=3
PY_MIN_MINOR=11
readonly PY_MIN_MAJOR PY_MIN_MINOR

# First system Python ≥ PY_MIN_*.  No third-party module checks — pip,
# venv, and tomllib are all stdlib.  Used both for bootstrap (creating the
# venv) and as a fallback when no venv exists (e.g. for pack discovery,
# which guards its own `import yaml` failure).
_find_system_python() {
    # Versioned binaries — major.minor encoded in the name.
    for py in python3.14 python3.13 python3.12 python3.11; do
        if command -v "$py" &>/dev/null; then
            echo "$py"; return 0
        fi
    done
    # Unversioned fallback — verify ≥ floor at runtime.
    for py in python3 python; do
        if command -v "$py" &>/dev/null && \
           "$py" -c "import sys; sys.exit(0 if sys.version_info >= (${PY_MIN_MAJOR},${PY_MIN_MINOR}) else 1)" 2>/dev/null; then
            echo "$py"; return 0
        fi
    done
    return 1
}

# Alias kept for call-site clarity — the venv-bootstrap path used to have
# its own implementation that diverged on yaml availability.  Today the
# two needs are identical: a Python ≥ PY_MIN_* with pip and venv.
_find_venv_python() {
    _find_system_python
}

# Prefer the venv's Python; fall back to system Python.
_find_python() {
    [[ -x "$VENV_DIR/bin/python3" ]] && { echo "$VENV_DIR/bin/python3"; return 0; }
    _find_system_python
}

# Prefer the venv's uvicorn; fall back to PATH.
_uvicorn_bin() {
    [[ -x "$VENV_DIR/bin/uvicorn" ]] && { echo "$VENV_DIR/bin/uvicorn"; return 0; }
    local sys_uv
    sys_uv=$(command -v uvicorn 2>/dev/null || true)
    if [[ -n "$sys_uv" ]]; then
        echo "$sys_uv"; return 0
    fi
    err "uvicorn not found. Run: pip install -r requirements.txt"
    exit 1
}

# ── macOS Xcode Command Line Tools pre-flight ─────────────────────────────────
# On a fresh Mac, the first invocation of `python3` /`git` triggers a GUI
# install prompt for Xcode CLT.  Detect it up-front so the user sees one
# clear message instead of a hung script.
_ensure_xcode_clt() {
    [[ "$(uname -s)" != "Darwin" ]] && return 0
    if xcode-select -p &>/dev/null; then
        return 0
    fi
    err "Xcode Command Line Tools are not installed."
    info "Run ${BOLD}xcode-select --install${RESET} and approve the GUI prompt,"
    info "then re-run ./run_dev.sh after the install completes."
    exit 1
}

# Installs a recent Python via Homebrew (macOS only).  Pins to a known LTS
# minor so version drift across machines stays predictable.
PY_BREW_VERSION="3.12"
readonly PY_BREW_VERSION

_install_python_via_brew() {
    [[ "$(uname -s)" != "Darwin" ]] && return 1
    command -v brew >/dev/null 2>&1 || return 1

    info "Installing python@${PY_BREW_VERSION} via Homebrew …"
    if ! brew install "python@${PY_BREW_VERSION}" >/dev/null 2>&1; then
        err "Homebrew install of python@${PY_BREW_VERSION} failed."
        return 1
    fi
    local brew_prefix
    brew_prefix=$(brew --prefix "python@${PY_BREW_VERSION}" 2>/dev/null || true)
    if [[ -n "$brew_prefix" && -d "$brew_prefix/bin" ]]; then
        export PATH="$brew_prefix/bin:$PATH"
    fi
    if command -v "python${PY_BREW_VERSION}" >/dev/null 2>&1; then
        ok "Python ${PY_BREW_VERSION} installed via Homebrew"
        return 0
    fi
    err "Homebrew installed python@${PY_BREW_VERSION} but it's not on PATH for this session."
    return 1
}

# Prints the canonical "install Python yourself" message and exits 1.
# Called only after every automated path has been exhausted.
_die_no_python() {
    err "No Python ≥ ${PY_MIN_MAJOR}.${PY_MIN_MINOR} found on PATH."
    info "Install one of:"
    info "  • macOS:  ${BOLD}brew install python@${PY_BREW_VERSION}${RESET}"
    info "  • Linux:  ${BOLD}sudo apt install python${PY_BREW_VERSION} python${PY_BREW_VERSION}-venv${RESET}"
    info "Then re-run ./run_dev.sh"
    info "(Pass --skip-venv if you've already installed deps into a different interpreter.)"
    exit 1
}

# ── Virtual environment creation ──────────────────────────────────────────────
_ensure_venv() {
    _ensure_xcode_clt

    # If a venv already exists, verify its Python meets the minimum version.
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        local venv_py="$VENV_DIR/bin/python3"
        if [[ -x "$venv_py" ]] && \
           ! "$venv_py" -c "import sys; sys.exit(0 if sys.version_info >= (${PY_MIN_MAJOR},${PY_MIN_MINOR}) else 1)" 2>/dev/null; then
            local old_ver
            old_ver=$("$venv_py" --version 2>&1 || echo "unknown")
            info "Existing .venv uses ${old_ver} — Python ≥ ${PY_MIN_MAJOR}.${PY_MIN_MINOR} is required."
            if ! $OPT_YES; then
                local _yn
                prompt "Recreate .venv with a newer Python? [Y/n]: "; read -r _yn || _yn=""
                case "${_yn:-Y}" in
                    [Yy]*|"") ;;
                    *) info "Keeping old .venv — some packages may fail to install."; return 0 ;;
                esac
            fi
            info "Removing old .venv …"
            rm -rf "$VENV_DIR"
        else
            return 0
        fi
    fi

    # Locate a usable Python, offering an automated brew install on macOS
    # when nothing on PATH satisfies the floor.
    local base_py
    if ! base_py=$(_find_venv_python 2>/dev/null); then
        info "No Python ≥ ${PY_MIN_MAJOR}.${PY_MIN_MINOR} on PATH."
        local install_ok=false
        if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
            local _ans
            if $OPT_YES; then
                _ans="Y"
            else
                echo ""
                prompt "Install python@${PY_BREW_VERSION} via Homebrew? [Y/n]: "
                read -r _ans || _ans=""
            fi
            case "${_ans:-Y}" in
                [Yy]*|"")
                    _install_python_via_brew && install_ok=true
                    ;;
            esac
        fi
        if $install_ok; then
            base_py=$(_find_venv_python 2>/dev/null) || _die_no_python
        else
            _die_no_python
        fi
    fi

    if ! $OPT_YES; then
        echo ""
        info "No virtual environment found at .venv"
        local _yn
        prompt "Create .venv with ${base_py}? [Y/n]: "; read -r _yn || _yn=""
        case "${_yn:-Y}" in
            [Yy]*|"") ;;
            *) info "Skipping venv — pip install will target ${base_py} (may hit PEP 668)."; return 0 ;;
        esac
    fi

    info "Creating virtual environment at .venv …"
    if ! "$base_py" -m venv "$VENV_DIR"; then
        err "venv creation failed.  Is the ${base_py} 'venv' module available?"
        info "  • Debian/Ubuntu:  sudo apt install $(basename "$base_py")-venv"
        info "  • macOS:          brew reinstall python@${PY_BREW_VERSION}"
        exit 1
    fi

    # Bring pip up to date so modern wheel resolution + PEP 660 editable
    # installs work.  Use the venv's own pip (not $base_py's) — they differ
    # right after `python -m venv`.
    info "Upgrading pip inside .venv …"
    local pip_args
    pip_args=$(_pip_index_args)
    # shellcheck disable=SC2086
    "$VENV_DIR/bin/python3" -m pip install $pip_args --upgrade pip -q || \
        info "pip upgrade failed — continuing with the bundled version."

    ok "Virtual environment ready: .venv  (${base_py})"
}

# ── Dependency sync ───────────────────────────────────────────────────────────

# Returns pip CLI flags to route through the Walmart Proximity PyPI mirror
# when the corporate proxy is active.  The proxy blocks direct downloads from
# files.pythonhosted.org (403 MediaTypeBlocked), so pip needs an alternate
# index that can serve the packages.
_pip_index_args() {
    if [[ "${HTTPS_PROXY:-}" == *wal-mart.com* ]]; then
        echo "--index-url https://repository.walmart.com/content/repositories/pypi-proxy/simple/ --trusted-host repository.walmart.com"
    fi
}

# True when running pip against $1 would hit PEP 668 ("externally-managed
# environment").  Skips the check for any venv (sys.prefix differs from
# sys.base_prefix) so we don't false-positive on a venv whose base
# interpreter happens to carry the marker.
_is_pep668_python() {
    local py="$1"
    [[ -z "$py" || ! -x "$py" ]] && return 1
    "$py" - <<'PY' 2>/dev/null
import os, sys, sysconfig
# Venvs are exempt from PEP 668 by design.
if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
    sys.exit(1)
stdlib = sysconfig.get_path("stdlib") or ""
marker = os.path.join(os.path.dirname(stdlib), "EXTERNALLY-MANAGED")
sys.exit(0 if os.path.exists(marker) else 1)
PY
}

# Runs pip only when requirements.txt is newer than the sentinel file.
_sync_deps() {
    [[ ! -f "$REQS_FILE" ]] && return 0

    local py_bin
    if ! py_bin=$(_find_python 2>/dev/null); then
        err "No Python found — cannot install dependencies."
        info "Re-run without --skip-venv, or install Python ≥ ${PY_MIN_MAJOR}.${PY_MIN_MINOR} first."
        exit 1
    fi

    # Sentinel lives in the venv; falls back to repo root when venv was skipped.
    local sentinel
    if [[ -d "$VENV_DIR" ]]; then
        sentinel="$VENV_DIR/.reqs_installed"
    else
        sentinel="$SCRIPT_DIR/.reqs_installed"
    fi

    if [[ -f "$sentinel" ]] && [[ ! "$REQS_FILE" -nt "$sentinel" ]]; then
        ok "Dependencies current  (requirements.txt unchanged)"
        return 0
    fi

    local pip_args
    pip_args=$(_pip_index_args)
    [[ -n "$pip_args" ]] && info "Corporate proxy detected — using Walmart PyPI mirror"

    # PEP 668: modern macOS/Debian system interpreters refuse `pip install`
    # without an opt-in flag.  Detect, warn loudly, and either bail or
    # forward --break-system-packages when the user has explicitly chosen
    # to install against system Python (e.g. via --skip-venv).
    local extra_pip_flags=""
    if _is_pep668_python "$py_bin"; then
        err "Pip would install into ${py_bin}, which is PEP 668 externally-managed."
        info "The correct fix is a virtualenv — re-run without --skip-venv."
        if $OPT_YES; then
            info "--yes mode: forwarding --break-system-packages (system Python will be modified)."
            extra_pip_flags="--break-system-packages"
        else
            local _ans
            echo ""
            prompt "Force install with --break-system-packages (mutates system Python)? [y/N]: "
            read -r _ans || _ans=""
            case "${_ans:-N}" in
                [Yy]*) extra_pip_flags="--break-system-packages" ;;
                *)     err "Aborting dependency sync."; exit 1 ;;
            esac
        fi
    fi

    info "Syncing dependencies from requirements.txt …"
    # shellcheck disable=SC2086
    "$py_bin" -m pip install $pip_args $extra_pip_flags -r "$REQS_FILE" -q
    touch "$sentinel"
    ok "Dependencies installed / up to date"
}

# ── Venv + deps orchestration ─────────────────────────────────────────────────
ensure_environment() {
    $OPT_SKIP_VENV && return 0
    banner "Python environment"
    _ensure_venv
    _sync_deps
}

# ── Akeyless secret sync ──────────────────────────────────────────────────────

# Resolves the akeyless CLI: $SCRIPT_DIR/akeyless wins, then `command -v akeyless`.
# Sets AKEYLESS_BIN + AKEYLESS_BIN_LABEL; returns 1 when nothing is found.
_resolve_akeyless_bin() {
    local repo_bin="$SCRIPT_DIR/akeyless"
    if [[ -f "$repo_bin" ]]; then
        chmod +x "$repo_bin" 2>/dev/null || true
        if [[ -x "$repo_bin" ]]; then
            AKEYLESS_BIN="$repo_bin"
            AKEYLESS_BIN_LABEL="./akeyless"
            return 0
        fi
    fi
    local path_bin
    if path_bin=$(command -v akeyless 2>/dev/null) && [[ -n "$path_bin" ]]; then
        AKEYLESS_BIN="$path_bin"
        AKEYLESS_BIN_LABEL="akeyless"
        return 0
    fi
    return 1
}

# Downloads the akeyless CLI binary directly from the official S3 bucket.
# Places the binary at $SCRIPT_DIR/akeyless so _resolve_akeyless_bin() finds it.
#
# Corporate networks block direct access to amazonaws.com, so the download is
# routed through the Walmart dev-tools proxy (proxy.wal-mart.com:9080).  If
# that fails, a second attempt uses the session's HTTPS_PROXY (if any).
_download_akeyless_binary() {
    local os arch url dest
    os=$(uname -s)
    arch=$(uname -m)
    dest="$SCRIPT_DIR/akeyless"

    case "${os}-${arch}" in
        Darwin-arm64)  url="https://akeyless-cli.s3.us-east-2.amazonaws.com/cli/latest/cli-darwin-arm64" ;;
        Darwin-x86_64) url="https://akeyless-cli.s3.us-east-2.amazonaws.com/cli/latest/production/cli-darwin-amd64" ;;
        Linux-x86_64)  url="https://akeyless-cli.s3.us-east-2.amazonaws.com/cli/latest/production/cli-linux-amd64" ;;
        *)
            err "No pre-built akeyless binary for ${os}-${arch}."
            return 1
            ;;
    esac

    info "Downloading akeyless CLI from S3 (~170 MB, may take a few minutes) …"
    info "  ${CYAN}${url}${RESET}"

    # Shared curl flags: follow redirects, show progress, retry on transient
    # errors, generous timeout for the ~170 MB binary.
    local curl_flags=( -fSL --progress-bar --retry 3 --retry-delay 5
                       --retry-connrefused --max-time 600 -o "$dest" )

    # Strategy 1: Walmart dev-tools proxy (non-authenticating, works for
    # most external HTTPS sites on the corporate network).
    local dev_proxy="http://proxy.wal-mart.com:9080"
    info "Trying Walmart dev-tools proxy (${dev_proxy}) …"
    if https_proxy="$dev_proxy" http_proxy="$dev_proxy" \
       curl "${curl_flags[@]}" "$url"; then
        chmod +x "$dest"
        ok "akeyless CLI downloaded → ./akeyless"
        return 0
    fi
    rm -f "$dest"

    # Strategy 2: session proxy (HTTPS_PROXY from the environment, if set
    # and different from the dev-tools proxy already tried).
    if [[ -n "${HTTPS_PROXY:-}" && "${HTTPS_PROXY:-}" != "$dev_proxy" ]]; then
        info "Retrying with session proxy (${HTTPS_PROXY}) …"
        if curl "${curl_flags[@]}" "$url"; then
            chmod +x "$dest"
            ok "akeyless CLI downloaded → ./akeyless"
            return 0
        fi
        rm -f "$dest"
    fi

    err "Download failed.  Check your network connection or proxy settings."
    info "Manual install: ${CYAN}${AKEYLESS_SETUP_DOC}${RESET}"
    return 1
}

# Installs akeyless CLI via brew, falling back to direct S3 binary download.
# Works in --yes mode (auto-installs without prompting).
_offer_install_akeyless() {
    local os _ans brew_ok=false
    os=$(uname -s)

    # ── Try Homebrew first (macOS only) ──────────────────────────────────
    if [[ "$os" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
        if ! $OPT_YES; then
            echo ""
            prompt "Install akeyless via ${BOLD}brew install akeylesslabs/tap/akeyless${RESET}? [Y/n]: "
            read -r _ans || _ans=""
            case "${_ans:-Y}" in
                [Yy]*|"") brew_ok=true ;;
            esac
        else
            brew_ok=true
        fi

        if $brew_ok; then
            info "Installing akeyless via Homebrew …"
            if brew tap akeylesslabs/tap 2>/dev/null && brew install akeyless 2>/dev/null; then
                ok "akeyless CLI installed via Homebrew"
                return 0
            fi
            err "Homebrew install failed — falling back to direct binary download."
        fi
    fi

    # ── Fallback: direct binary download from S3 ─────────────────────────
    if ! $OPT_YES; then
        echo ""
        prompt "Download akeyless CLI binary directly? [Y/n]: "
        read -r _ans || _ans=""
        case "${_ans:-Y}" in
            [Yy]*|"") ;;
            *)
                info "Skipped akeyless install."
                return 1
                ;;
        esac
    fi

    _download_akeyless_binary
}

# Ensures ~/.akeyless/settings points to Walmart's internal vault DNS.
# The default (vault.akeyless.io) is unreachable from the corporate network,
# causing "connection reset by peer" during auth.
_ensure_akeyless_settings() {
    local settings_file="$HOME/.akeyless/settings"
    local walmart_dns="vault.wmt.akeyless.io"

    if [[ -f "$settings_file" ]] && grep -q "dns=\"${walmart_dns}\"" "$settings_file" 2>/dev/null; then
        return 0
    fi

    mkdir -p "$HOME/.akeyless"
    cat > "$settings_file" <<EOF
dns="${walmart_dns}"
protocol="https"
EOF
    ok "Akeyless settings → dns=${walmart_dns}"
}

# Writes ~/.akeyless/profiles/default.toml with the shared SAML access-id and
# gateway URL. Identity is bound later by the browser SAML flow.
_configure_default_profile() {
    $OPT_YES && return 1

    echo ""
    info "No default Akeyless profile found at ${BOLD}~/.akeyless/profiles/default.toml${RESET}"
    info "Walmart's shared SAML access-id will be used (${BOLD}${AKEYLESS_WALMART_ACCESS_ID}${RESET})."
    info "Your identity is established at first secret fetch via browser SAML."
    echo ""
    local _ans
    prompt "Configure default profile now? [Y/n]: "; read -r _ans || _ans=""
    case "${_ans:-Y}" in
        [Yy]*|"") ;;
        *) return 1 ;;
    esac

    info "Running: ${AKEYLESS_BIN_LABEL} configure --access-id ${AKEYLESS_WALMART_ACCESS_ID} --access-type saml --profile default …"
    if "$AKEYLESS_BIN" configure \
        --access-id "$AKEYLESS_WALMART_ACCESS_ID" \
        --access-type saml \
        --profile default \
        --gateway-url "$AKEYLESS_GATEWAY_URL_DEFAULT" >/dev/null 2>&1; then
        ok "Default profile written: ~/.akeyless/profiles/default.toml"
        # akeyless configure writes dns="vault.akeyless.io" by default — fix it.
        _ensure_akeyless_settings
        return 0
    fi
    err "akeyless configure failed. Follow the SOP manually:"
    info "  ${CYAN}${AKEYLESS_SETUP_DOC}${RESET}"
    return 1
}

# Ensures the akeyless CLI and a default profile are in place, exports the
# corporate gateway URLs, and returns 0 when ready for `get-secret-value`.
# Fast path when CLI + profile are both already present.
ensure_akeyless_ready() {
    local need_install=false need_configure=false

    if ! _resolve_akeyless_bin; then
        need_install=true
    fi
    [[ -f "$HOME/.akeyless/profiles/default.toml" ]] || need_configure=true

    # Always export gateway URLs so hand-rolled profiles that omit them still work.
    export AKEYLESS_GATEWAY_URL="${AKEYLESS_GATEWAY_URL:-$AKEYLESS_GATEWAY_URL_DEFAULT}"
    export AKEYLESS_GATEWAY_CONFIG_URL="${AKEYLESS_GATEWAY_CONFIG_URL:-$AKEYLESS_GATEWAY_CONFIG_URL_DEFAULT}"

    # Ensure the settings file always points to Walmart's internal vault DNS,
    # even if the CLI was installed/configured outside this script.
    _ensure_akeyless_settings

    $need_install || $need_configure || return 0

    banner "Akeyless CLI bootstrap"

    if $need_install; then
        if ! _offer_install_akeyless; then
            err "akeyless CLI is required to fetch secrets."
            info "Walmart SOP: ${CYAN}${AKEYLESS_SETUP_DOC}${RESET}"
            return 1
        fi
        if ! _resolve_akeyless_bin; then
            err "Installed akeyless but cannot find it on PATH — check your shell config."
            return 1
        fi
        need_configure=true
    fi

    if $need_configure; then
        if ! _configure_default_profile; then
            err "Akeyless profile is required to fetch secrets."
            return 1
        fi
    fi

    info "First secret fetch will open your browser for Walmart SAML login."
    return 0
}

_print_akeyless_access_help() {
    echo ""
    info "Akeyless sync requires membership in the AD group: ${BOLD}${AKEYLESS_AD_GROUP}${RESET}"
    info "Request access via ServiceNow:"
    printf "  ${CYAN}%s${RESET}\n" "$AKEYLESS_ACCESS_REQUEST_URL"
    echo ""
}

_continue_without_secrets() {
    $OPT_YES && { info "Continuing without secret sync (--yes mode)."; return 0; }
    local _ans
    prompt "Continue without secret sync? [y/N]: "; read -r _ans || _ans=""
    case "${_ans:-N}" in
        [Yy]*) return 0 ;;
        *)     err "Aborted at secret sync."; exit 1 ;;
    esac
}

sync_akeyless_secrets() {
    $OPT_SKIP_SECRETS && return 0

    banner "Akeyless secret sync"

    # Confirm before pulling so a working local secrets.toml isn't
    # blindly overwritten on every run.  --yes / -y keeps auto-pull
    # behaviour for CI / non-interactive callers.
    if ! $OPT_YES; then
        local _ans
        prompt "Pull latest secrets from Akeyless? [Y/n]: "; read -r _ans
        case "${_ans:-Y}" in
            [Nn]*)
                info "Skipping Akeyless sync — using existing ${SECRETS_FILE}"
                return 0
                ;;
            *) ;;
        esac
    fi

    if ! ensure_akeyless_ready; then
        _print_akeyless_access_help
        _continue_without_secrets
        return 0
    fi

    info "akeyless CLI: ${AKEYLESS_BIN}"
    info "Source: ${AKEYLESS_SECRET_PATH}"
    info "Target: ${SECRETS_FILE}"

    local remote err_file
    err_file=$(mktemp -t akeyless-err.XXXXXX)
    TMP_FILES+=("$err_file")
    if ! remote=$("$AKEYLESS_BIN" get-secret-value --name "$AKEYLESS_SECRET_PATH" 2>"$err_file"); then
        err "Could not fetch ${AKEYLESS_SECRET_PATH}"
        [[ -s "$err_file" ]] && sed 's/^/    /' "$err_file" >&2
        if [[ -s "$err_file" ]] && grep -qiE 'profile|config.*not found|failed to load' "$err_file"; then
            info "Akeyless has no profile configured yet. Run:"
            printf "  ${BOLD}${CYAN}${AKEYLESS_BIN_LABEL} configure${RESET}\n"
            info "When prompted, set Access ID and choose auth method (e.g. SAML/LDAP for Walmart SSO)."
        elif [[ -s "$err_file" ]] && grep -qiE 'auth|token|login|unauthor|forbidden|denied|expired' "$err_file"; then
            info "Hint: run ${BOLD}${AKEYLESS_BIN_LABEL} configure${RESET} to (re)set your access profile."
        fi
        rm -f "$err_file"
        _print_akeyless_access_help
        _continue_without_secrets
        return 0
    fi
    rm -f "$err_file"

    if [[ -z "$remote" ]]; then
        err "Akeyless returned an empty secret — refusing to merge."
        _continue_without_secrets
        return 0
    fi

    if [[ ! -f "$SECRETS_FILE" ]]; then
        mkdir -p "$(dirname "$SECRETS_FILE")"
        # Subshell umask 077 ensures the file is born 0600.
        ( umask 077 && printf "%s" "$remote" > "$SECRETS_FILE" )
        ok "Recreated secrets.toml from Akeyless"
        return 0
    fi

    local py
    py=$(_find_python 2>/dev/null) || { err "No Python available for TOML merge."; return 1; }

    local merge_out
    if ! merge_out=$(REMOTE_TOML="$remote" LOCAL_PATH="$SECRETS_FILE" "$py" - <<'PY'
import os, re, sys
try:
    import tomllib
except ImportError:
    sys.stderr.write("tomllib unavailable (need Python 3.11+)\n")
    sys.exit(2)

remote_text = os.environ["REMOTE_TOML"]
local_path  = os.environ["LOCAL_PATH"]

try:
    remote_doc = tomllib.loads(remote_text)
except tomllib.TOMLDecodeError as exc:
    sys.stderr.write(f"Akeyless payload is not valid TOML: {exc}\n")
    sys.exit(3)

with open(local_path, "rb") as fh:
    try:
        tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        sys.stderr.write(f"Local secrets.toml is not valid TOML: {exc}\n")
        sys.exit(4)

with open(local_path, "r", encoding="utf-8") as fh:
    local_lines = fh.readlines()

def walk_tables(d, prefix=""):
    out = []
    for k, v in d.items():
        if isinstance(v, dict):
            path = f"{prefix}.{k}" if prefix else k
            out.append(path)
            out.extend(walk_tables(v, path))
    return out

remote_sections = set(walk_tables(remote_doc))

section_re = re.compile(r'^\s*\[([^\]]+)\]\s*$')

# For each [section] header, return the slice covering one leading-comment
# block + the header + its body, excluding trailing blank/comment lines.
# Orphan inter-section comments are dropped so re-sync is idempotent.
def kept_block(header_idx):
    b = header_idx - 1
    if b >= 0 and local_lines[b].strip() == "":
        b -= 1
    leading_start = header_idx
    while b >= 0 and local_lines[b].lstrip().startswith("#"):
        leading_start = b
        b -= 1
    body_end = header_idx + 1
    while body_end < len(local_lines) and not section_re.match(local_lines[body_end]):
        body_end += 1
    while body_end > header_idx + 1 and (
        local_lines[body_end - 1].strip() == ""
        or local_lines[body_end - 1].lstrip().startswith("#")
    ):
        body_end -= 1
    return leading_start, body_end

sections = []
for i, line in enumerate(local_lines):
    m = section_re.match(line)
    if not m:
        continue
    path = m.group(1).strip()
    s, e = kept_block(i)
    sections.append((path, s, e))

local_only_blocks = []
local_only_paths  = []
for path, s, e in sections:
    if path not in remote_sections:
        local_only_paths.append(path)
        local_only_blocks.append("".join(local_lines[s:e]))

parts = []
if not remote_text.endswith("\n"):
    remote_text += "\n"
parts.append(remote_text)
if local_only_blocks:
    parts.append("\n")
    parts.append("# " + "═" * 68 + "\n")
    parts.append("# Local-only sections — preserved by run_dev.sh secret sync\n")
    parts.append("# " + "═" * 68 + "\n\n")
    for block in local_only_blocks:
        parts.append(block.rstrip() + "\n\n")

merged = "".join(parts)

tmp = local_path + ".sync.tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    fh.write(merged)
os.chmod(tmp, 0o600)
os.replace(tmp, local_path)

print(f"REMOTE_COUNT={len(remote_sections)}")
print(f"PRESERVED_COUNT={len(local_only_paths)}")
print(f"PRESERVED_PATHS={','.join(local_only_paths)}")
PY
    ); then
        err "TOML merge failed."
        return 1
    fi

    local remote_count preserved_count preserved_paths
    remote_count=$(echo "$merge_out"    | awk -F= '/^REMOTE_COUNT=/    {print $2}')
    preserved_count=$(echo "$merge_out" | awk -F= '/^PRESERVED_COUNT=/ {print $2}')
    preserved_paths=$(echo "$merge_out" | awk -F= '/^PRESERVED_PATHS=/ {print $2}')

    ok "secrets.toml synced — Akeyless sections: ${remote_count}, preserved locally: ${preserved_count}"
    [[ -n "$preserved_paths" ]] && info "Preserved: ${preserved_paths}"
    return 0
}

# ── Environment selection ─────────────────────────────────────────────────────
select_environment() {
    [[ -n "$OPT_ENV" ]] && return 0

    banner "Dynaconf environment"

    local envs=("development" "stage" "production")
    local i=1
    for e in "${envs[@]}"; do
        if [[ "$e" == "$_DEFAULT_ENV" ]]; then
            printf "  [%d] %s  ${YELLOW}(default)${RESET}\n" "$i" "$e"
        else
            printf "  [%d] %s\n" "$i" "$e"
        fi
        i=$(( i + 1 ))
    done
    echo ""

    local _choice
    prompt "Choice [1-3, Enter = development]: "; read -r _choice || _choice=""
    case "${_choice:-1}" in
        1) OPT_ENV="development" ;;
        2) OPT_ENV="stage" ;;
        3) OPT_ENV="production" ;;
        *)
            err "Invalid choice — defaulting to development."
            OPT_ENV="development"
            ;;
    esac
    ok "Environment → ${OPT_ENV}"
}

# ── Pack discovery (inline Python for reliable YAML parsing) ──────────────────
_discover_packs() {
    local py
    py=$(_find_python 2>/dev/null) || { return 1; }
    "$py" - <<'PY'
import sys, glob
try:
    import yaml
except ImportError:
    sys.exit(1)

packs = []
for path in sorted(glob.glob("packs/*/pack.yaml")):
    try:
        with open(path) as fh:
            d = yaml.safe_load(fh)
        pid  = (d.get("id") or "").strip()
        name = (d.get("name") or pid).strip()
        dflt = "1" if d.get("default") else "0"
        if pid:
            packs.append(f"{pid}|{name}|{dflt}")
    except Exception:
        pass

print("\n".join(packs))
PY
}

# ── Pack + agent selection ────────────────────────────────────────────────────
select_pack() {
    if [[ -n "$OPT_PACK" ]]; then
        [[ -z "$OPT_AGENT" ]] && OPT_AGENT="${OPT_PACK}_agent"
        return 0
    fi

    banner "Select pack"

    local raw_packs
    raw_packs=$(_discover_packs 2>/dev/null || true)

    if [[ -z "$raw_packs" ]]; then
        err "No packs found under packs/ (PyYAML installed?). Falling back to default."
        OPT_PACK="$_DEFAULT_PACK"
        [[ -z "$OPT_AGENT" ]] && OPT_AGENT="${OPT_PACK}_agent"
        return 0
    fi

    # Parse into parallel arrays (bash 3.2-compatible, no mapfile).
    local pack_ids=() pack_names=() pack_defaults=()
    local i=0 default_idx=0

    while IFS='|' read -r _pid _nm _dflt; do
        pack_ids+=("$_pid")
        pack_names+=("$_nm")
        pack_defaults+=("$_dflt")
        [[ "$_dflt" == "1" ]] && default_idx=$i
        i=$(( i + 1 ))
    done <<< "$raw_packs"

    # Reset terminal attributes so stale colour doesn't bleed into the menu.
    printf "${RESET}"

    local total=${#pack_ids[@]}
    for (( j=0; j<total; j++ )); do
        if [[ "${pack_defaults[$j]}" == "1" ]]; then
            printf "  [%d] %-32s %s  ${YELLOW}(default)${RESET}\n" \
                "$(( j+1 ))" "${pack_ids[$j]}" "${pack_names[$j]}"
        else
            printf "  [%d] %-32s %s\n" \
                "$(( j+1 ))" "${pack_ids[$j]}" "${pack_names[$j]}"
        fi
    done
    echo ""

    local display_default=$(( default_idx + 1 ))
    local _choice
    prompt "Choice [1-${total}, Enter = ${display_default}]: "; read -r _choice || _choice=""

    _choice="${_choice//[^0-9]/}"

    local idx=$(( ${_choice:-$display_default} - 1 ))

    if (( idx < 0 || idx >= total )); then
        err "Out of range — using default."
        idx=$default_idx
    fi

    OPT_PACK="${pack_ids[$idx]}"
    ok "Pack → ${OPT_PACK}  (${pack_names[$idx]})"

    if [[ -z "$OPT_AGENT" ]]; then
        OPT_AGENT="${OPT_PACK}"
    fi
    ok "Agent → ${OPT_AGENT}"
}

# ── Launch summary ────────────────────────────────────────────────────────────
confirm_launch() {
    local reload_label="yes"
    [[ -z "$OPT_RELOAD" ]] && reload_label="no"
    local console_label="no"
    [[ "$OPT_CONSOLE" == "yes" ]] && console_label="yes  (http://${OPT_HOST}:${OPT_PORT}/console)"

    # Landing label reflects what the running server will actually serve at `/`:
    # "yes" when a dist exists (built this run or persisted from a prior run),
    # "no" only when dist is absent — matches mount_homepage()'s gate in app.py.
    local landing_label="no"
    if [[ -f "$LANDING_DIST/index.html" ]]; then
        landing_label="yes  (http://${OPT_HOST}:${OPT_PORT}/)"
    fi

    printf "\n${BOLD}┌─────────────────────────────────────────────────────────────┐${RESET}\n"
    printf "${BOLD}│                  dev server configuration                  │${RESET}\n"
    printf "${BOLD}├─────────────────────────────────────────────────────────────┤${RESET}\n"
    printf "${BOLD}│${RESET}  %-16s  %-43s${BOLD}│${RESET}\n" "Environment:"  "$OPT_ENV"
    printf "${BOLD}│${RESET}  %-16s  %-43s${BOLD}│${RESET}\n" "Pack ID:"      "$OPT_PACK"
    printf "${BOLD}│${RESET}  %-16s  %-43s${BOLD}│${RESET}\n" "Agent name:"   "$OPT_AGENT"
    printf "${BOLD}│${RESET}  %-16s  %-43s${BOLD}│${RESET}\n" "Host:port:"    "${OPT_HOST}:${OPT_PORT}"
    printf "${BOLD}│${RESET}  %-16s  %-43s${BOLD}│${RESET}\n" "Hot-reload:"   "$reload_label"
    printf "${BOLD}│${RESET}  %-16s  %-43s${BOLD}│${RESET}\n" "Landing /:"    "$landing_label"
    printf "${BOLD}│${RESET}  %-16s  %-43s${BOLD}│${RESET}\n" "/console SPA:" "$console_label"
    printf "${BOLD}└─────────────────────────────────────────────────────────────┘${RESET}\n\n"

    $OPT_YES && return 0

    local _confirm
    prompt "Start server? [Y/n]: "; read -r _confirm || _confirm=""
    case "${_confirm:-Y}" in
        [Yy]*|"") return 0 ;;
        *)
            info "Aborted."
            exit 0
            ;;
    esac
}

# ── Node / npm bootstrap ──────────────────────────────────────────────────────
# Vite 5 requires Node ≥ 18. We auto-detect what's on PATH, fall back to
# sourcing nvm, and — when nothing satisfies — offer to install Node via
# (in order) an already-installed nvm, Homebrew on macOS, or a fresh nvm
# install routed through Walmart's dev-tools proxy.

NODE_MIN_MAJOR=18
NODE_INSTALL_VERSION="20"   # Pinned LTS for reproducible installs.
NVM_INSTALL_URL="https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh"

readonly NODE_MIN_MAJOR NODE_INSTALL_VERSION NVM_INSTALL_URL

# Echoes the major version of the active `node`, or empty when absent.
_node_major() {
    local ver
    ver=$(node --version 2>/dev/null) || return 1
    ver="${ver#v}"
    echo "${ver%%.*}"
}

# True when `node` is present and major ≥ NODE_MIN_MAJOR.
_node_ok() {
    local major
    major=$(_node_major 2>/dev/null) || return 1
    [[ -n "$major" && "$major" -ge "$NODE_MIN_MAJOR" ]]
}

# Sources nvm into the current shell when it's installed. Some nvm versions
# reference unset vars, so -u is relaxed across the source.
_source_nvm() {
    local nvm_sh="${NVM_DIR:-$HOME/.nvm}/nvm.sh"
    [[ -s "$nvm_sh" ]] || return 1
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    set +u
    # shellcheck disable=SC1090
    . "$nvm_sh" --no-use >/dev/null 2>&1
    local rc=$?
    set -u
    return $rc
}

# Installs Node via an already-sourced nvm.
_install_node_via_nvm() {
    info "Installing Node ${NODE_INSTALL_VERSION} via nvm …"
    set +u
    if nvm install "$NODE_INSTALL_VERSION" >/dev/null 2>&1 && \
       nvm use "$NODE_INSTALL_VERSION" >/dev/null 2>&1; then
        set -u
        ok "Node $(node --version 2>/dev/null) ready via nvm"
        return 0
    fi
    set -u
    err "nvm install failed."
    return 1
}

# Installs Node via Homebrew (macOS only). Links node@N onto PATH for this
# session because brew keg-only versions aren't on PATH by default.
_install_node_via_brew() {
    info "Installing node@${NODE_INSTALL_VERSION} via Homebrew …"
    if ! brew install "node@${NODE_INSTALL_VERSION}" >/dev/null 2>&1; then
        err "Homebrew install failed."
        return 1
    fi
    local brew_prefix
    brew_prefix=$(brew --prefix "node@${NODE_INSTALL_VERSION}" 2>/dev/null || true)
    if [[ -n "$brew_prefix" && -d "$brew_prefix/bin" ]]; then
        export PATH="$brew_prefix/bin:$PATH"
    fi
    if _node_ok; then
        ok "Node $(node --version) ready via Homebrew"
        return 0
    fi
    err "Homebrew installed Node but it's not on PATH for this session."
    return 1
}

# Downloads + runs the official nvm install script. Routes through the
# Walmart dev-tools proxy first (same strategy as akeyless), falls back to
# the session HTTPS_PROXY, then a direct connection.
_install_nvm() {
    info "Installing nvm (~1 MB) from raw.githubusercontent.com …"

    local install_script
    install_script=$(mktemp -t nvm-install.XXXXXX)
    TMP_FILES+=("$install_script")

    local dev_proxy="http://proxy.wal-mart.com:9080"
    local curl_flags=( -fSL --retry 3 --max-time 120 -o "$install_script" )

    if https_proxy="$dev_proxy" http_proxy="$dev_proxy" \
         curl "${curl_flags[@]}" "$NVM_INSTALL_URL" 2>/dev/null; then
        :
    elif [[ -n "${HTTPS_PROXY:-}" && "${HTTPS_PROXY:-}" != "$dev_proxy" ]] && \
         curl "${curl_flags[@]}" "$NVM_INSTALL_URL" 2>/dev/null; then
        :
    elif curl "${curl_flags[@]}" "$NVM_INSTALL_URL" 2>/dev/null; then
        :
    else
        err "Could not download nvm install script."
        return 1
    fi

    # The install script edits ~/.bashrc / ~/.zshrc to load nvm in future
    # shells. That's the right behaviour — we want next-time-they-open-a-
    # terminal Node to keep working. Run it, then source for this session.
    if ! bash "$install_script" >/dev/null 2>&1; then
        err "nvm install script failed."
        return 1
    fi
    ok "nvm installed → ~/.nvm"

    if _source_nvm; then
        return 0
    fi
    err "nvm installed but cannot be sourced — open a fresh shell and re-run."
    return 1
}

# Asks Y/n; returns 0 when accepted (default Y) or in --yes mode.
_ask_install() {
    $OPT_YES && return 0
    local msg="$1" _ans
    echo ""
    prompt "${msg} [Y/n]: "; read -r _ans || _ans=""
    case "${_ans:-Y}" in [Yy]*|"") return 0 ;; *) return 1 ;; esac
}

# Top-level: ensure a Node ≥ NODE_MIN_MAJOR is on PATH. Returns 0 on success.
ensure_node_ready() {
    if _node_ok; then
        ok "Node $(node --version) on PATH"
        return 0
    fi

    # Try sourcing nvm — many developers have nvm installed but their
    # non-interactive shell didn't source it.
    if _source_nvm; then
        # nvm may have a default version that already satisfies us.
        set +u
        nvm use default >/dev/null 2>&1 || true
        set -u
        if _node_ok; then
            ok "Node $(node --version) via existing nvm"
            return 0
        fi
        if _ask_install "Install Node ${NODE_INSTALL_VERSION} via your existing nvm?"; then
            _install_node_via_nvm && return 0
        fi
    fi

    # macOS + Homebrew path.
    if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
        local cur_label="not installed"
        _node_major >/dev/null 2>&1 && cur_label="$(node --version)"
        info "Node on PATH: ${cur_label} (need ≥ ${NODE_MIN_MAJOR})."
        if _ask_install "Install node@${NODE_INSTALL_VERSION} via Homebrew?"; then
            _install_node_via_brew && return 0
        fi
    fi

    # Last resort: install nvm itself, then Node.
    info "No automatic Node install path available yet."
    if _ask_install "Bootstrap nvm (~/.nvm) and install Node ${NODE_INSTALL_VERSION}?"; then
        if _install_nvm && _install_node_via_nvm; then
            return 0
        fi
    fi

    err "Could not install a compatible Node automatically."
    info "Install manually (one of):"
    info "  • nvm:           curl -o- ${NVM_INSTALL_URL} | bash  →  nvm install ${NODE_INSTALL_VERSION}"
    info "  • brew (macOS):  brew install node@${NODE_INSTALL_VERSION}"
    info "Then re-run ./run_dev.sh"
    return 1
}

# ── Landing page (/) ──────────────────────────────────────────────────────────
LANDING_DIR="$SCRIPT_DIR/frontend"
LANDING_DIST="$LANDING_DIR/dist"

# ── Local console (/console) ──────────────────────────────────────────────────
CONSOLE_DIR="$SCRIPT_DIR/dev/local_console"
CONSOLE_UI_DIR="$CONSOLE_DIR/ui"
CONSOLE_DIST="$CONSOLE_DIR/static/dist"

# Asks whether to mount the /console SPA. Default Y. Honours --with-console
# (forces yes), --skip-console (forces no), and --yes (no prompt, defaults yes).
_offer_console() {
    [[ ! -d "$CONSOLE_DIR" ]] && { OPT_CONSOLE="no"; return 0; }

    case "$OPT_CONSOLE" in
        yes|no) return 0 ;;
    esac

    if $OPT_YES; then
        OPT_CONSOLE="yes"
        return 0
    fi

    echo ""
    local _ans
    prompt "Mount the /console test SPA? [Y/n]: "; read -r _ans || _ans=""
    case "${_ans:-Y}" in
        [Yy]*|"") OPT_CONSOLE="yes" ;;
        *)        OPT_CONSOLE="no" ;;
    esac
}

# Marks the console as unavailable for this run. Called when Node bootstrap
# fails or the build can't finish — keeps the server starting without a
# half-mounted /console.
_disable_console() {
    OPT_CONSOLE="no"
    info "App will start without /console mounted."
}

# Marks the landing page as unavailable for this run. Called when Node
# bootstrap fails or the build can't finish — the app still starts but
# `/` will 404 (or serve a stale dist if one exists from a prior run).
_disable_landing() {
    OPT_LANDING="no"
    info "App will start without the landing page rebuilt — / may 404 if no prior build exists."
}

# Builds the landing-page SPA when not skipped and the dist directory
# is empty, stale, or --rebuild-landing was passed. The mount itself is
# automatic in app.py (no env var); this function only controls whether
# fresh build artefacts are emitted to frontend/dist/.
_build_landing() {
    [[ "$OPT_LANDING" != "yes" ]] && return 0
    [[ ! -d "$LANDING_DIR" ]] && { _disable_landing; return 0; }
    [[ ! -f "$LANDING_DIR/package.json" ]] && {
        info "frontend/package.json missing — skipping landing-page build."
        _disable_landing
        return 0
    }

    banner "Landing page (/)"

    if ! ensure_node_ready; then
        err "Landing page requires Node ≥ ${NODE_MIN_MAJOR} — skipping build."
        _disable_landing
        return 0
    fi

    if ! command -v npm >/dev/null 2>&1; then
        err "npm not found even after Node bootstrap — skipping landing build."
        _disable_landing
        return 0
    fi

    # Force-rebuild path: wipe dist + node_modules so the next install/build
    # starts from scratch.
    if $OPT_REBUILD_LANDING; then
        info "Force-rebuilding landing page (--rebuild-landing)…"
        rm -rf "$LANDING_DIST" "$LANDING_DIR/node_modules"
    elif [[ -f "$LANDING_DIST/index.html" ]]; then
        # Freshness check: rebuild only when a source file is newer than the
        # current dist/index.html. Mirrors _build_console's heuristic.
        local newest_src
        newest_src=$(find "$LANDING_DIR/src" "$LANDING_DIR/index.html" \
            "$LANDING_DIR/package.json" "$LANDING_DIR/package-lock.json" \
            "$LANDING_DIR/vite.config.ts" "$LANDING_DIR/tsconfig.json" \
            "$LANDING_DIR/tailwind.config.ts" "$LANDING_DIR/postcss.config.js" \
            -type f -newer "$LANDING_DIST/index.html" \
            -print -quit 2>/dev/null || true)
        if [[ -z "$newest_src" ]]; then
            ok "Landing build current"
            return 0
        fi
        info "Landing source changed — rebuilding…"
    else
        info "Building landing-page SPA (first run)…"
    fi

    # Install deps. Prefer `npm ci` when package-lock.json is present (faster
    # and fails loud on drift). Fall back to `npm install` otherwise.
    if [[ ! -d "$LANDING_DIR/node_modules" ]]; then
        if [[ -f "$LANDING_DIR/package-lock.json" ]]; then
            info "Installing landing UI deps via npm ci (one-time, ~30s)…"
            if ! ( cd "$LANDING_DIR" && npm ci --silent ); then
                err "npm ci failed for $LANDING_DIR"
                _disable_landing
                return 0
            fi
        else
            info "Installing landing UI deps via npm install (one-time, ~30s)…"
            if ! ( cd "$LANDING_DIR" && npm install --silent ); then
                err "npm install failed for $LANDING_DIR"
                _disable_landing
                return 0
            fi
        fi
    fi

    if ! ( cd "$LANDING_DIR" && npm run --silent build ); then
        err "Landing build failed — see the npm output above."
        _disable_landing
        return 0
    fi

    # Post-build assertion: `tsc -b && vite build` can exit 0 in rare
    # half-completion cases without emitting index.html. Guard against it.
    if [[ ! -f "$LANDING_DIST/index.html" ]]; then
        err "Build reported success but $LANDING_DIST/index.html is missing."
        _disable_landing
        return 0
    fi

    ok "Landing built → ${LANDING_DIST#$SCRIPT_DIR/}"
}

# Builds the SPA when /console is enabled and the dist directory is empty,
# stale, or --rebuild-console was passed. Ensures a compatible Node is on
# PATH before invoking npm. When the operator explicitly asked for the
# console (--with-console / --rebuild-console / answered Y to the prompt),
# a build failure is loud — but the server keeps starting so the operator
# can keep working with the API.
_build_console() {
    [[ "$OPT_CONSOLE" != "yes" ]] && return 0
    [[ ! -d "$CONSOLE_UI_DIR" ]] && { _disable_console; return 0; }

    banner "Local console (/console)"

    if ! ensure_node_ready; then
        err "/console requires Node ≥ ${NODE_MIN_MAJOR} — skipping build."
        _disable_console
        return 0
    fi

    if ! command -v npm >/dev/null 2>&1; then
        err "npm not found even after Node bootstrap — skipping build."
        _disable_console
        return 0
    fi

    # Force-rebuild path: wipe dist + node_modules so the next install/build
    # starts from scratch.
    if $OPT_REBUILD_CONSOLE; then
        info "Force-rebuilding console (--rebuild-console)…"
        rm -rf "$CONSOLE_DIST" "$CONSOLE_UI_DIR/node_modules"
    elif [[ -f "$CONSOLE_DIST/index.html" ]]; then
        # Freshness check: rebuild only when a source file is newer than the
        # current dist/index.html.
        local newest_src
        newest_src=$(find "$CONSOLE_UI_DIR/src" "$CONSOLE_UI_DIR/index.html" \
            "$CONSOLE_UI_DIR/package.json" "$CONSOLE_UI_DIR/package-lock.json" \
            -type f -newer "$CONSOLE_DIST/index.html" \
            -print -quit 2>/dev/null || true)
        if [[ -z "$newest_src" ]]; then
            ok "Console build current"
            return 0
        fi
        info "Console source changed — rebuilding…"
    else
        info "Building console SPA (first run)…"
    fi

    # Install deps. Prefer `npm ci` when package-lock.json is present (faster
    # and fails loud on drift). Fall back to `npm install` otherwise.
    if [[ ! -d "$CONSOLE_UI_DIR/node_modules" ]]; then
        if [[ -f "$CONSOLE_UI_DIR/package-lock.json" ]]; then
            info "Installing console UI deps via npm ci (one-time, ~30s)…"
            if ! ( cd "$CONSOLE_UI_DIR" && npm ci --silent ); then
                err "npm ci failed for $CONSOLE_UI_DIR"
                _disable_console
                return 0
            fi
        else
            info "Installing console UI deps via npm install (one-time, ~30s)…"
            if ! ( cd "$CONSOLE_UI_DIR" && npm install --silent ); then
                err "npm install failed for $CONSOLE_UI_DIR"
                _disable_console
                return 0
            fi
        fi
    fi

    if ! ( cd "$CONSOLE_UI_DIR" && npm run --silent build ); then
        err "Console build failed — see the npm output above."
        _disable_console
        return 0
    fi

    # Post-build assertion: Vite can exit 0 without emitting index.html in
    # rare half-completion cases (e.g. tsc errors with `tsc -b && vite build`
    # where tsc exits non-zero but the script still ran). Guard against it.
    if [[ ! -f "$CONSOLE_DIST/index.html" ]]; then
        err "Build reported success but $CONSOLE_DIST/index.html is missing."
        _disable_console
        return 0
    fi

    ok "Console built → ${CONSOLE_DIST#$SCRIPT_DIR/}"
}

# ── Entry point ───────────────────────────────────────────────────────────────
main() {
    parse_args "$@"

    printf "\n${BOLD}${CYAN}  matbot dev server${RESET}\n"
    printf "${CYAN}  ─────────────────────────────────────────────${RESET}\n"

    ensure_environment
    sync_akeyless_secrets
    select_environment
    select_pack
    _build_landing
    _offer_console
    _build_console
    handle_port
    confirm_launch

    export ENV_FOR_DYNACONF="$OPT_ENV"
    export DYNACONF_AGENT_NAME="$OPT_AGENT"
    export DEFAULT_PACK_ID="$OPT_PACK"
    # IS_PARENT marks this uvicorn as the user-facing runtime.  app.py reads
    # it to gate the dashboard router and the SPA landing page; child pack
    # runtimes leave it unset so they stay headless A2A backends.
    export IS_PARENT="true"
    [[ "$OPT_CONSOLE" == "yes" ]] && export MATBOT_ENABLE_CONSOLE="true"

    ok "Launching uvicorn on ${OPT_HOST}:${OPT_PORT}…"
    echo ""

    # shellcheck disable=SC2086
    exec "$(_uvicorn_bin)" app:app \
        --host "$OPT_HOST" \
        --port "$OPT_PORT" \
        $OPT_RELOAD
}

main "$@"
