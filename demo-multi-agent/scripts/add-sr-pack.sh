#!/usr/bin/env bash
# add-sr-pack.sh — append a Service Registry entry for a pack to sr.yaml.
#
# Contract:
#   - Lists packs/* without a matching `key: ITEM-OPS-MATBOT-<PACK_KEBAB>`
#     entry; refuses to edit existing entries.
#   - Prompts have defaults; Enter accepts, any value overrides.
#   - Stage consumerId + PEM path are required; prod block is optional and
#     emitted commented-out, mirroring the stage shape.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SR_YAML="$PROJECT_ROOT/sr.yaml"
PACKS_DIR="$PROJECT_ROOT/packs"

# ---------------------------------------------------------------------------
# Pretty output
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'
  YELLOW=$'\033[33m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; RESET=""
fi

die()  { echo "${RED}ERR:${RESET} $*" >&2; exit 1; }
info() { echo "${CYAN}info:${RESET} $*"; }
ok()   { echo "${GREEN}ok:${RESET}   $*"; }
warn() { echo "${YELLOW}warn:${RESET} $*"; }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# pack_to_key gif_tote_validation -> ITEM-OPS-MATBOT-GIF-TOTE-VALIDATION
pack_to_key() {
  echo "ITEM-OPS-MATBOT-$(echo "$1" | tr '[:lower:]_' '[:upper:]-')"
}

# pack_to_kebab gif_tote_validation -> gif-tote-validation
pack_to_kebab() {
  echo "$1" | tr '_' '-'
}

# prompt_default "Label" "default" -> echoes either user input or the default
prompt_default() {
  local label="$1" default="$2" answer
  if [[ -n "$default" ]]; then
    read -r -p "$label ${DIM}[${default}]${RESET}: " answer
    echo "${answer:-$default}"
  else
    read -r -p "$label: " answer
    echo "$answer"
  fi
}

# prompt_required "Label" -> loops until non-empty input
prompt_required() {
  local label="$1" answer
  while :; do
    read -r -p "$label ${RED}(required)${RESET}: " answer
    [[ -n "$answer" ]] && { echo "$answer"; return; }
    warn "value is required"
  done
}

# prompt_yes_no "Label" "y|n" -> echoes y or n
prompt_yes_no() {
  local label="$1" default="$2" answer
  local hint
  [[ "$default" == "y" ]] && hint="Y/n" || hint="y/N"
  read -r -p "$label ${DIM}[${hint}]${RESET}: " answer
  answer="${answer:-$default}"
  case "$answer" in
    y|Y|yes|YES) echo "y" ;;
    *)           echo "n" ;;
  esac
}

# pem_body /path/to/pub.pem -> single-line base64 (PEM headers stripped)
pem_body() {
  local path="$1"
  [[ -f "$path" ]] || die "PEM file not found: $path"
  local body
  body="$(grep -v '^-----' "$path" | tr -d '\n\r ')"
  [[ -n "$body" ]] || die "PEM file has no body after stripping headers: $path"
  echo "$body"
}

# entry_exists ITEM-OPS-MATBOT-FOO -> exit 0 if a `key: <KEY>` line exists
entry_exists() {
  local key="$1"
  grep -qE "^[[:space:]]*key:[[:space:]]*${key}[[:space:]]*\$" "$SR_YAML"
}

# generate_uuid -> a lowercase RFC 4122 UUID using uuidgen (or python fallback)
generate_uuid() {
  if command -v uuidgen >/dev/null 2>&1; then
    uuidgen | tr '[:upper:]' '[:lower:]'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import uuid; print(uuid.uuid4())'
  else
    die "neither uuidgen nor python3 available — install one to generate UUIDs"
  fi
}

# default_pem -> first uncommented, non-placeholder publicKey: in sr.yaml,
# or empty. Packs share the same key, so we lift it from an existing entry.
# `[[:alnum:]]` (vs. `[A-Za-z0-9+/=]`) sidesteps BSD awk on macOS.
default_pem() {
  awk '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*publicKey:[[:space:]]*[[:alnum:]]/ {
      sub(/^[[:space:]]*publicKey:[[:space:]]*/, "")
      if ($0 ~ /^REPLACE/) next
      print
      exit
    }
  ' "$SR_YAML"
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
[[ -f "$SR_YAML"   ]] || die "sr.yaml not found at $SR_YAML"
[[ -d "$PACKS_DIR" ]] || die "packs/ not found at $PACKS_DIR"

# ---------------------------------------------------------------------------
# Pack discovery
# ---------------------------------------------------------------------------
ALL_PACKS=()
while IFS= read -r -d '' d; do
  ALL_PACKS+=("$(basename "$d")")
done < <(find "$PACKS_DIR" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

[[ ${#ALL_PACKS[@]} -gt 0 ]] || die "no pack folders under $PACKS_DIR"

echo "${BOLD}Discovered packs in $PACKS_DIR:${RESET}"
AVAILABLE=()
for pack in "${ALL_PACKS[@]}"; do
  key="$(pack_to_key "$pack")"
  if entry_exists "$key"; then
    printf "  ${DIM}[%s]${RESET} %s -> %s ${YELLOW}(already in sr.yaml — blocked)${RESET}\n" "skip" "$pack" "$key"
  else
    printf "  ${GREEN}[%s]${RESET} %s -> %s\n" " ok " "$pack" "$key"
    AVAILABLE+=("$pack")
  fi
done
echo

if [[ ${#AVAILABLE[@]} -eq 0 ]]; then
  ok "every pack already has an SR entry — nothing to do"
  exit 0
fi

# ---------------------------------------------------------------------------
# Pack selection
# ---------------------------------------------------------------------------
echo "${BOLD}Select a pack to add:${RESET}"
for i in "${!AVAILABLE[@]}"; do
  printf "  %d) %s\n" "$((i + 1))" "${AVAILABLE[$i]}"
done

while :; do
  read -r -p "Choice [1-${#AVAILABLE[@]}]: " choice
  if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#AVAILABLE[@]} )); then
    PACK="${AVAILABLE[$((choice - 1))]}"
    break
  fi
  warn "invalid choice"
done

PACK_KEY="$(pack_to_key "$PACK")"
PACK_KEBAB="$(pack_to_kebab "$PACK")"

echo
info "configuring SR entry for ${BOLD}${PACK}${RESET} (${PACK_KEY})"
info "press Enter to accept defaults shown in brackets"
echo

# ---------------------------------------------------------------------------
# Defaults (mirror existing GIF-tote entry — keep these in sync with sr.yaml)
# ---------------------------------------------------------------------------
DEF_DESC="${PACK} SOP pack — ships as a standalone WCNP service built on the matbot multi-agent runtime."
DEF_PRODUCT_ID="5772"
DEF_APM="APM0019161"
DEF_CRITICALITY="MAJOR"
DEF_SLACK="matbot-kitt-agent-factory"
DEF_EMAIL_1="HPL_Pipeline_Support@email.wal-mart.com"
DEF_EMAIL_2="muthukrishnan.gurusamy@walmart.com"
DEF_MEMBER_1="homeoffice\\m0g0m5q"
DEF_MEMBER_2="homeoffice\\r0m08w0"
DEF_MEMBER_3="homeoffice\\s0s0f76"
DEF_STAGE_HOST="stage.${PACK_KEBAB}.matbot.walmart.com"
DEF_PROD_HOST="${PACK_KEBAB}.matbot.walmart.com"
DEF_PORT="8000"
DEF_TIMEOUT="300000"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
echo "${BOLD}-- metadata --${RESET}"
DESC="$(prompt_default        "description"            "$DEF_DESC")"
PRODUCT_ID="$(prompt_default  "teamRostersProductId"   "$DEF_PRODUCT_ID")"
APM="$(prompt_default         "serviceNowApmId"        "$DEF_APM")"
CRITICALITY="$(prompt_default "businessCriticality"    "$DEF_CRITICALITY")"

echo
echo "${BOLD}-- communication --${RESET}"
SLACK="$(prompt_default       "slack channel"          "$DEF_SLACK")"
EMAIL_1="$(prompt_default     "email #1"               "$DEF_EMAIL_1")"
EMAIL_2="$(prompt_default     "email #2 (blank = skip)" "$DEF_EMAIL_2")"

echo
echo "${BOLD}-- members --${RESET}"
MEMBER_1="$(prompt_default    "member #1"              "$DEF_MEMBER_1")"
MEMBER_2="$(prompt_default    "member #2 (blank = skip)" "$DEF_MEMBER_2")"
MEMBER_3="$(prompt_default    "member #3 (blank = skip)" "$DEF_MEMBER_3")"

echo
echo "${BOLD}-- stage environment --${RESET}"
STAGE_HOST="$(prompt_default  "stage hostname"         "$DEF_STAGE_HOST")"
PORT="$(prompt_default        "applicationPort"        "$DEF_PORT")"
TIMEOUT="$(prompt_default     "ingress requestTimeout (ms)" "$DEF_TIMEOUT")"

DEF_STAGE_CID="$(generate_uuid)"
STAGE_CID="$(prompt_default   "stage consumerId (UUID)" "$DEF_STAGE_CID")"

DEF_PEM="$(default_pem)"
STAGE_PEM=""
STAGE_PEM_SOURCE=""
if [[ -n "$DEF_PEM" ]]; then
  read -r -p "stage public-key PEM path ${DIM}[blank = reuse key from sr.yaml]${RESET}: " pem_path
  if [[ -z "$pem_path" ]]; then
    STAGE_PEM="$DEF_PEM"
    STAGE_PEM_SOURCE="reused from sr.yaml"
  else
    pem_path="${pem_path/#\~/$HOME}"
    STAGE_PEM="$(pem_body "$pem_path")"
    STAGE_PEM_SOURCE="$pem_path"
  fi
else
  pem_path="$(prompt_required "stage public-key PEM path")"
  pem_path="${pem_path/#\~/$HOME}"
  STAGE_PEM="$(pem_body "$pem_path")"
  STAGE_PEM_SOURCE="$pem_path"
fi

echo
echo "${BOLD}-- prod environment --${RESET} ${DIM}(will be appended commented-out)${RESET}"
INCLUDE_PROD="$(prompt_yes_no "include a commented prod block?" "y")"
PROD_HOST=""; PROD_CID=""; PROD_PEM=""; PROD_PEM_SOURCE=""
if [[ "$INCLUDE_PROD" == "y" ]]; then
  PROD_HOST="$(prompt_default "prod hostname" "$DEF_PROD_HOST")"
  DEF_PROD_CID="$(generate_uuid)"
  PROD_CID="$(prompt_default  "prod consumerId (UUID)" "$DEF_PROD_CID")"
  read -r -p "prod public-key PEM path ${DIM}[blank = reuse stage key]${RESET}: " prod_pem_path
  if [[ -z "$prod_pem_path" ]]; then
    PROD_PEM="$STAGE_PEM"
    PROD_PEM_SOURCE="reused from stage"
  else
    prod_pem_path="${prod_pem_path/#\~/$HOME}"
    PROD_PEM="$(pem_body "$prod_pem_path")"
    PROD_PEM_SOURCE="$prod_pem_path"
  fi
fi

# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------
echo
echo "${BOLD}Summary${RESET}"
echo "  pack          : $PACK"
echo "  key           : $PACK_KEY"
echo "  stage host    : $STAGE_HOST"
echo "  stage cid     : $STAGE_CID"
echo "  stage pem     : ${STAGE_PEM_SOURCE} (${#STAGE_PEM} chars)"
if [[ "$INCLUDE_PROD" == "y" ]]; then
  echo "  prod block    : included (commented)"
  echo "  prod host     : $PROD_HOST"
  echo "  prod cid      : $PROD_CID"
  echo "  prod pem      : ${PROD_PEM_SOURCE} (${#PROD_PEM} chars)"
fi
echo

if [[ "$(prompt_yes_no "append to sr.yaml?" "n")" != "y" ]]; then
  warn "aborted by user — no changes written"
  exit 0
fi

# ---------------------------------------------------------------------------
# Re-check the block is still missing — guards against concurrent edits
# ---------------------------------------------------------------------------
if entry_exists "$PACK_KEY"; then
  die "$PACK_KEY now exists in sr.yaml (added since we started) — refusing to duplicate"
fi

# ---------------------------------------------------------------------------
# Emit YAML block
# ---------------------------------------------------------------------------
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

{
  printf '\n'
  printf '  - name: %s\n' "$PACK_KEY"
  printf '    key: %s\n'  "$PACK_KEY"
  printf '    description: >\n'
  printf '      %s\n' "$DESC"
  printf '    teamRostersProductId: %s\n' "$PRODUCT_ID"
  printf '    serviceNowApmId: %s\n'      "$APM"
  printf '    businessCriticality: %s\n'  "$CRITICALITY"
  printf '    communication:\n'
  printf '      slack:\n'
  printf '        - channel: %s\n' "$SLACK"
  printf '      email:\n'
  printf '        - address: %s\n' "$EMAIL_1"
  [[ -n "$EMAIL_2" ]] && printf '        - address: %s\n' "$EMAIL_2"
  printf '    members:\n'
  printf '      - %s\n' "$MEMBER_1"
  [[ -n "$MEMBER_2" ]] && printf '      - %s\n' "$MEMBER_2"
  [[ -n "$MEMBER_3" ]] && printf '      - %s\n' "$MEMBER_3"
  printf '\n'
  printf '    environments:\n'
  printf '      - name: stage\n'
  printf '        type: STAGING\n'
  printf '        description: Staging Service\n'
  printf '        externalCatalog: false\n'
  printf '        serviceType: REST\n'
  printf '        properties:\n'
  printf '          swaggerEndpoint:\n'
  printf '            - https://%s/openapi.json\n' "$STAGE_HOST"
  printf '        soaIntegration:\n'
  printf '          serviceVersion: 1.0.0\n'
  printf '          endPoint: https://%s\n'        "$STAGE_HOST"
  printf '          contract: https://%s/openapi.json\n' "$STAGE_HOST"
  printf '          environmentName: stage\n'
  printf '        serviceMeshConfig:\n'
  printf '          deploymentType: WCNP\n'
  printf '          defaultIngressConfig:\n'
  printf '            requestTimeout: %s\n' "$TIMEOUT"
  printf '          ingressListeners:\n'
  printf '            - protocol: HTTP\n'
  printf '              applicationHost: 127.0.0.1\n'
  printf '              applicationPort: %s\n' "$PORT"
  printf '              enablePolicyEngine: true\n'
  printf '              passthroughURIs:\n'
  printf '                - uri: "/openapi.json"\n'
  printf '                  methods:\n'
  printf '                    - GET\n'
  printf '                - uri: "/docs"\n'
  printf '                  methods:\n'
  printf '                    - GET\n'
  printf '                - uri: "/redoc"\n'
  printf '                  methods:\n'
  printf '                    - GET\n'
  printf '                - uri: "/.well-known/agents.json"\n'
  printf '                  methods:\n'
  printf '                    - GET\n'
  printf '                - uri: "/healthz"\n'
  printf '                  methods:\n'
  printf '                    - GET\n'
  printf '                - uri: "/readyz"\n'
  printf '                  methods:\n'
  printf '                    - GET\n'
  printf '                - uri: "/metrics"\n'
  printf '                  methods:\n'
  printf '                    - GET\n'
  printf '                - uri: "/.*"\n'
  printf '                  methods:\n'
  printf '                    - OPTIONS\n'
  printf '        consumerIdInfos:\n'
  printf '          - consumerId: %s\n'  "$STAGE_CID"
  printf '            publicKey: %s\n'   "$STAGE_PEM"

  if [[ "$INCLUDE_PROD" == "y" ]]; then
    prod_cid_line="$PROD_CID"
    prod_pem_line="$PROD_PEM"
    printf '\n'
    printf '      # - name: prod\n'
    printf '      #   type: PRODUCTION\n'
    printf '      #   description: Production Service\n'
    printf '      #   externalCatalog: false\n'
    printf '      #   serviceType: REST\n'
    printf '      #   properties:\n'
    printf '      #     swaggerEndpoint:\n'
    printf '      #       - https://%s/openapi.json\n' "$PROD_HOST"
    printf '      #   soaIntegration:\n'
    printf '      #     serviceVersion: 1.0.0\n'
    printf '      #     endPoint: https://%s\n'        "$PROD_HOST"
    printf '      #     contract: https://%s/openapi.json\n' "$PROD_HOST"
    printf '      #     environmentName: prod\n'
    printf '      #   serviceMeshConfig:\n'
    printf '      #     deploymentType: WCNP\n'
    printf '      #     defaultIngressConfig:\n'
    printf '      #       requestTimeout: %s\n' "$TIMEOUT"
    printf '      #     ingressListeners:\n'
    printf '      #       - protocol: HTTP\n'
    printf '      #         applicationHost: 127.0.0.1\n'
    printf '      #         applicationPort: %s\n' "$PORT"
    printf '      #         enablePolicyEngine: true\n'
    printf '      #         passthroughURIs:\n'
    printf '      #           - uri: "/healthz"\n'
    printf '      #             methods:\n'
    printf '      #               - GET\n'
    printf '      #           - uri: "/readyz"\n'
    printf '      #             methods:\n'
    printf '      #               - GET\n'
    printf '      #           - uri: "/metrics"\n'
    printf '      #             methods:\n'
    printf '      #               - GET\n'
    printf '      #           - uri: "/.*"\n'
    printf '      #             methods:\n'
    printf '      #               - OPTIONS\n'
    printf '      #   consumerIdInfos:\n'
    printf '      #     - consumerId: %s\n' "$prod_cid_line"
    printf '      #       publicKey: %s\n'  "$prod_pem_line"
  fi
} > "$TMP"

cat "$TMP" >> "$SR_YAML"

ok "appended SR entry for ${BOLD}${PACK}${RESET} to $SR_YAML"
info "review with: git diff sr.yaml"
