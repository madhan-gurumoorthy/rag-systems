#!/usr/bin/env bash
# add-pack-kitt.sh — scaffold a child kitt for a pack and wire it into the
# parent kitt's `build.postBuild` as a `deployApp` task.
#
# Contract:
#   - Lists packs/* without a kitt.yml; refuses to edit existing children.
#   - Prompts have defaults; Enter accepts, any value overrides.
#   - Emits stage active, prod commented; appends one `deployApp` task to
#     parent postBuild (no-op if already wired).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PARENT_KITT="$PROJECT_ROOT/kitt.yml"
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

# pack_has_kitt gif_tote_validation -> exit 0 if packs/<pack>/kitt.yml exists
pack_has_kitt() {
  [[ -f "$PACKS_DIR/$1/kitt.yml" ]]
}

# deployapp_listed packs/foo/kitt.yml -> exit 0 if a deployApp task in
# build.postBuild already references that kittFilePath.
deployapp_listed() {
  local path="$1"
  grep -qE "^[[:space:]]*kittFilePath:[[:space:]]*${path}[[:space:]]*\$" "$PARENT_KITT"
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
[[ -f "$PARENT_KITT" ]] || die "parent kitt not found at $PARENT_KITT"
[[ -d "$PACKS_DIR"   ]] || die "packs/ not found at $PACKS_DIR"

grep -qE "^[[:space:]]+postBuild:[[:space:]]*\$" "$PARENT_KITT" || \
  die "parent kitt has no \`postBuild:\` key under \`build:\` — refusing to scaffold"

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
  if pack_has_kitt "$pack"; then
    printf "  ${DIM}[%s]${RESET} %s ${YELLOW}(already has kitt.yml — blocked)${RESET}\n" "skip" "$pack"
  else
    printf "  ${GREEN}[%s]${RESET} %s\n" " ok " "$pack"
    AVAILABLE+=("$pack")
  fi
done
echo

if [[ ${#AVAILABLE[@]} -eq 0 ]]; then
  ok "every pack already has a kitt.yml — nothing to do"
  exit 0
fi

# ---------------------------------------------------------------------------
# Pack selection
# ---------------------------------------------------------------------------
echo "${BOLD}Select a pack to scaffold:${RESET}"
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
CHILD_KITT="$PACKS_DIR/$PACK/kitt.yml"
CHILD_REL_PATH="packs/$PACK/kitt.yml"

echo
info "scaffolding child kitt for ${BOLD}${PACK}${RESET} (${PACK_KEY})"
info "press Enter to accept defaults shown in brackets"
echo

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEF_ARTIFACT="matbot-${PACK_KEBAB}"
DEF_APM="APM0019161"
DEF_SLACK="matbot-kitt-agent-factory"
DEF_NAMESPACE="matbot-stg"
DEF_TENANT="USGM"
DEF_STAGE_CLUSTERS='["uscentral-stage-wmt-005", "useast-stage-wmt-004"]'
DEF_PROD_CLUSTERS='["eus2-prod-a15", "uswest-prod-az-004"]'
DEF_STAGE_HOST="stage.${PACK_KEBAB}.matbot.walmart.com"
DEF_PROD_HOST="${PACK_KEBAB}.matbot.walmart.com"
DEF_AKEYLESS_COMMON_PATH="/Prod/WCNP/homeoffice/Hyperloop-monitoring/matbot-multi-agents"
DEF_AKEYLESS_PACK_SUBPATH="matbot-${PACK_KEBAB}"
DEF_STAGE_MIN_CPU="200m"
DEF_STAGE_MIN_MEM="512Mi"
DEF_STAGE_MAX_CPU="1000m"
DEF_STAGE_MAX_MEM="1280Mi"
DEF_STAGE_SCALE_PCT="50"
DEF_STAGE_SCALE_MIN="2"
DEF_STAGE_SCALE_MAX="4"
DEF_PROD_SCALE_PCT="40"
DEF_PROD_SCALE_MIN="2"
DEF_PROD_SCALE_MAX="5"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
echo "${BOLD}-- identity --${RESET}"
ARTIFACT="$(prompt_default "build.artifact name" "$DEF_ARTIFACT")"
APM="$(prompt_default      "managedNamespace.apmId" "$DEF_APM")"
SLACK="$(prompt_default    "notify.slack.channelName" "$DEF_SLACK")"

echo
echo "${BOLD}-- deploy target --${RESET}"
NAMESPACE="$(prompt_default      "deploy.namespace" "$DEF_NAMESPACE")"
TENANT="$(prompt_default         "deploy.tenantSite" "$DEF_TENANT")"
STAGE_CLUSTERS="$(prompt_default "stage cluster_id list (YAML inline)" "$DEF_STAGE_CLUSTERS")"
PROD_CLUSTERS="$(prompt_default  "prod cluster_id list (YAML inline; commented in scaffold)" "$DEF_PROD_CLUSTERS")"

echo
echo "${BOLD}-- hostnames --${RESET}"
STAGE_HOST="$(prompt_default "stage hostname" "$DEF_STAGE_HOST")"
PROD_HOST="$(prompt_default  "prod hostname (commented in scaffold)" "$DEF_PROD_HOST")"

echo
echo "${BOLD}-- akeyless --${RESET}"
echo "${DIM}  Common Akeyless path is shared across packs; the pack subpath sits beneath it.${RESET}"
AKEYLESS_COMMON_PATH="$(prompt_default "akeyless config.akeyless.path (shared)" "$DEF_AKEYLESS_COMMON_PATH")"
AKEYLESS_PACK_SUBPATH="$(prompt_default "akeyless pack subpath (prepended to /{stage}/config)" "$DEF_AKEYLESS_PACK_SUBPATH")"

echo
echo "${BOLD}-- stage resources --${RESET}"
STAGE_MIN_CPU="$(prompt_default   "stage min cpu"    "$DEF_STAGE_MIN_CPU")"
STAGE_MIN_MEM="$(prompt_default   "stage min memory" "$DEF_STAGE_MIN_MEM")"
STAGE_MAX_CPU="$(prompt_default   "stage max cpu"    "$DEF_STAGE_MAX_CPU")"
STAGE_MAX_MEM="$(prompt_default   "stage max memory" "$DEF_STAGE_MAX_MEM")"
STAGE_SCALE_PCT="$(prompt_default "stage scaling cpuPercent" "$DEF_STAGE_SCALE_PCT")"
STAGE_SCALE_MIN="$(prompt_default "stage scaling min"  "$DEF_STAGE_SCALE_MIN")"
STAGE_SCALE_MAX="$(prompt_default "stage scaling max"  "$DEF_STAGE_SCALE_MAX")"

echo
echo "${BOLD}-- prod resources --${RESET} ${DIM}(commented block; values still substituted)${RESET}"
PROD_SCALE_PCT="$(prompt_default "prod scaling cpuPercent" "$DEF_PROD_SCALE_PCT")"
PROD_SCALE_MIN="$(prompt_default "prod scaling min"  "$DEF_PROD_SCALE_MIN")"
PROD_SCALE_MAX="$(prompt_default "prod scaling max"  "$DEF_PROD_SCALE_MAX")"

# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------
echo
echo "${BOLD}Summary${RESET}"
echo "  pack          : $PACK"
echo "  child path    : $CHILD_REL_PATH"
echo "  wm.app        : $PACK_KEY"
echo "  artifact      : $ARTIFACT"
echo "  namespace     : $NAMESPACE ($TENANT)"
echo "  stage host    : $STAGE_HOST"
echo "  stage clusters: $STAGE_CLUSTERS"
echo "  prod host     : $PROD_HOST (commented)"
echo "  prod clusters : $PROD_CLUSTERS (commented)"
echo "  common path   : $AKEYLESS_COMMON_PATH"
echo "  pack subpath  : $AKEYLESS_PACK_SUBPATH"
echo "  stage cpu     : $STAGE_MIN_CPU – $STAGE_MAX_CPU"
echo "  stage memory  : $STAGE_MIN_MEM – $STAGE_MAX_MEM"
echo "  stage scaling : ${STAGE_SCALE_MIN}-${STAGE_SCALE_MAX} @ ${STAGE_SCALE_PCT}% cpu"
echo "  prod scaling  : ${PROD_SCALE_MIN}-${PROD_SCALE_MAX} @ ${PROD_SCALE_PCT}% cpu (commented)"
echo

if [[ "$(prompt_yes_no "write child kitt and append deployApp task to parent postBuild?" "n")" != "y" ]]; then
  warn "aborted by user — no changes written"
  exit 0
fi

# ---------------------------------------------------------------------------
# Re-check the pack is still missing — guards against concurrent edits
# ---------------------------------------------------------------------------
if pack_has_kitt "$PACK"; then
  die "$CHILD_REL_PATH now exists (added since we started) — refusing to overwrite"
fi

# ---------------------------------------------------------------------------
# Emit child kitt
# ---------------------------------------------------------------------------
cat > "$CHILD_KITT" <<EOF
# Pack child — deploy-only. The parent kitt.yml builds the shared
# matbot-multi-agents image and triggers this deployment via postBuild.deployApp.
# No build section needed; the parent passes tag: "" so this reuses the
# parent-built image version automatically.
#
# Secrets: layers /etc/secrets/secrets-pack.toml on top of the parent's
# secrets-common.toml; settings.py merges via Dynaconf so pack overrides
# common on key conflict.

profiles:
  - stage-gates
  - test-executors-testhub
  - git://item-ops:matbot-multi-agents:main:kitt-stageGates

owner:
  group: Hyperloop-monitoring

managedNamespace:
  apmId: ${APM}

notify:
  slack:
    channelName: ${SLACK}

setup:
  changePaths:
    - packs/${PACK}/
    - agent_factory/
    - storage/
    - app.py
    - requirements.txt
    - Dockerfile

build:
  artifact: ${ARTIFACT}
  skip: true

deploy:
  skip: false
  tenantSite: ${TENANT}
  namespace: ${NAMESPACE}
  releaseType:
    strategy: normal
    rollbackOnError: false
    waitForReady: true
    deployTimeout: 900

  gslb:
    enabled: true
    strategy: stage
    lbRoutings:
      stage:
        cnames: [${STAGE_HOST}]
        matchStages: [stage]
      # prod:
      #   cnames: [${PROD_HOST}]
      #   matchStages: [prod]

  helm:
    values:
      container:
        image: item-ops-docker/matbot-multi-agents
        tag: "{{\$.kitt.build.version}}"
      env:
        CLUSTER_ID: "{{\$.kittExec.currentCluster.clusterId}}"
      metadata:
        labels:
          wm.app: ${PACK_KEY}
        annotations:
          sidecar.istio.io/inject: "true"
          traffic.sidecar.istio.io/excludeOutboundPorts: "8080,8300,15020,8200,15000,15001,15004,15006,15008,15009,15021,15053,15090"
          sidecar.istio.io/proxyCPU: 100m
          sidecar.istio.io/proxyCPULimit: 100m
          sidecar.istio.io/proxyMemory: 200M
          sidecar.istio.io/proxyMemoryLimit: 200M
      networking:
        internalPort: "8000"
        externalPort: "8000"
        httpsEnabled: true
      readinessProbe:
        enabled: "true"
        path: "/readyz"
        port: 8000
        headers: "*/*"
        wait: 10
        failureThreshold: 3
        probeInterval: 20
      livenessProbe:
        enabled: "true"
        path: "/healthz"
        port: 8000
        headers: "*/*"
        failureThreshold: 5
        probeInterval: 20
        wait: 10
      global:
        metrics:
          remoteWriteSampleLimit: 500

  stages:
    - name: stage
      refs: [main]
      target:
        cluster_id: ${STAGE_CLUSTERS}
      helm:
        values:
          env:
            PACK_ID: ${PACK}
            DEFAULT_PACK_ID: ${PACK}
          min:
            cpu: ${STAGE_MIN_CPU}
            memory: ${STAGE_MIN_MEM}
          max:
            cpu: ${STAGE_MAX_CPU}
            memory: ${STAGE_MAX_MEM}
          scaling:
            cpuPercent: ${STAGE_SCALE_PCT}
            min: ${STAGE_SCALE_MIN}
            max: ${STAGE_SCALE_MAX}
          # Two Akeyless static secrets at /etc/secrets:
          #   secrets-common.toml — framework bundle
          #   secrets-pack.toml   — pack bundle
          secrets:
            akeyless: true
            config:
              akeyless:
                path: ${AKEYLESS_COMMON_PATH}
              path: /etc/secrets
            files:
              - destination: secrets-common.toml
                content: '{{\$.kittExec.currentStage.name}}/config'
              - destination: secrets-pack.toml
                content: ${AKEYLESS_PACK_SUBPATH}/{{\$.kittExec.currentStage.name}}/config
      preDeploy:
        - task:
            name: messageSlack
            text: "Deployment of ${PACK} pack to stage is starting"
        - task:
            name: messageSlack
            text: "Starting Functional Tests"
        - concord:
            name: Functional Test
            enabled: true
            arguments:
              config:
                git:
                  orgName: '{{\$.kitt.build.commitEvent.repo.org}}'
                  repoName: '{{\$.kitt.build.commitEvent.repo.name}}'
                  branchName: '{{\$.kitt.build.commitEvent.currentBranch}}'
                  looperFile: 'looper.yml'
                functionalTesting:
                  call: 'functional_tests'
                  mode: Passive
                  env: "{{\$.kittExec.currentStage.profile}}"
                  teamChannel: "{{\$.kitt.notify.slack.channelName}}"
                  timestamp: "{{\$.kitt.notify.slack.threadTS}}"
                  threshHold: 10
        - task:
            name: messageSlack
            text: "Functional tests completed, starting Integration Tests"
        - concord:
            name: Integration Test
            enabled: true
            arguments:
              config:
                git:
                  orgName: '{{\$.kitt.build.commitEvent.repo.org}}'
                  repoName: '{{\$.kitt.build.commitEvent.repo.name}}'
                  branchName: '{{\$.kitt.build.commitEvent.currentBranch}}'
                  looperFile: 'looper.yml'
                integrationTesting:
                  call: 'integration_tests'
                  mode: Passive
                  env: "{{\$.kittExec.currentStage.profile}}"
                  teamChannel: "{{\$.kitt.notify.slack.channelName}}"
                  timestamp: "{{\$.kitt.notify.slack.threadTS}}"
                  threshHold: 10
        - task:
            name: messageSlack
            text: "Integration tests completed, deployment to stage in-progress.."
      postDeploy:
        - task:
            name: messageSlack
            text: "${PACK} pack deployed to https://${STAGE_HOST}"
        - task:
            name: messageSlack
            text: "Starting End to End Tests"
        - concord:
            name: End To End Test
            enabled: true
            arguments:
              config:
                git:
                  orgName: '{{\$.kitt.build.commitEvent.repo.org}}'
                  repoName: '{{\$.kitt.build.commitEvent.repo.name}}'
                  branchName: '{{\$.kitt.build.commitEvent.currentBranch}}'
                  looperFile: 'looper.yml'
                endToEndTesting:
                  call: 'e2e_tests'
                  mode: Passive
                  threshHold: 10
                  env: "{{\$.kittExec.currentStage.profile}}"
                  teamChannel: "{{\$.kitt.notify.slack.channelName}}"
                  timestamp: "{{\$.kitt.notify.slack.threadTS}}"
        - task:
            name: messageSlack
            text: "End to End tests completed. Starting R2C Contract Tests"
        - concord:
            name: R2C
            enabled: true
            arguments:
              config:
                spec:
                  apiSpecUrl: ''
                  specPath: 'specs/api-spec.json'
                contractTest:
                  cname: "${STAGE_HOST}"
                  threshHold: 10
                  mode: Passive
                  appName: matbot-multi-agents
        - task:
            name: messageSlack
            text: "R2C Contract Tests completed"

    # - name: prod
    #   refs: [main]
    #   target:
    #     cluster_id: ${PROD_CLUSTERS}
    #   approvers:
    #     groups:
    #       - "Hyperloop-monitoring"
    #   helm:
    #     values:
    #       env:
    #         PACK_ID: ${PACK}
    #         DEFAULT_PACK_ID: ${PACK}
    #       min:
    #         cpu: ${STAGE_MIN_CPU}
    #         memory: ${STAGE_MIN_MEM}
    #       max:
    #         cpu: ${STAGE_MAX_CPU}
    #         memory: ${STAGE_MAX_MEM}
    #       scaling:
    #         cpuPercent: ${PROD_SCALE_PCT}
    #         min: ${PROD_SCALE_MIN}
    #         max: ${PROD_SCALE_MAX}
    #       secrets:
    #         akeyless: true
    #         config:
    #           akeyless:
    #             path: ${AKEYLESS_COMMON_PATH}
    #           path: /etc/secrets
    #         files:
    #           - destination: secrets-common.toml
    #             content: '{{\$.kittExec.currentStage.name}}/config'
    #           - destination: secrets-pack.toml
    #             content: ${AKEYLESS_PACK_SUBPATH}/{{\$.kittExec.currentStage.name}}/config
    #   preDeploy:
    #     - task:
    #         name: messageSlack
    #         text: "Deploying ${PACK} pack to prod"
    #   postDeploy:
    #     - task:
    #         name: messageSlack
    #         text: "${PACK} pack deployed to https://${PROD_HOST}"
EOF

ok "wrote child kitt: ${CHILD_REL_PATH}"

# ---------------------------------------------------------------------------
# Append deployApp task to parent build.postBuild.
# Splice before the `^deploy:` anchor (postBuild lives above it under build:).
# ---------------------------------------------------------------------------
if deployapp_listed "$CHILD_REL_PATH"; then
  info "${CHILD_REL_PATH} already wired into parent postBuild — left as is"
else
  DEPLOY_LINE="$(grep -nE '^deploy:[[:space:]]*$' "$PARENT_KITT" | head -1 | cut -d: -f1)"
  [[ -n "$DEPLOY_LINE" ]] || die "no top-level \`deploy:\` anchor in $PARENT_KITT — cannot locate postBuild insertion point"

  TMP_PARENT="$(mktemp)"
  trap 'rm -f "$TMP_PARENT"' EXIT
  head -n "$((DEPLOY_LINE - 1))" "$PARENT_KITT" > "$TMP_PARENT"
  cat >> "$TMP_PARENT" <<EOF
    - task:
        name: deployApp
        kittFilePath: ${CHILD_REL_PATH}
        tag: ""
        branch: "{{\$.kitt.build.commitEvent.currentBranch}}"
        sync: false
EOF
  tail -n "+${DEPLOY_LINE}" "$PARENT_KITT" >> "$TMP_PARENT"

  if ! grep -qE "^[[:space:]]*kittFilePath:[[:space:]]*${CHILD_REL_PATH}[[:space:]]*\$" "$TMP_PARENT"; then
    die "failed to insert deployApp task into parent kitt (splice produced no kittFilePath line)"
  fi
  cat "$TMP_PARENT" > "$PARENT_KITT"
  ok "appended deployApp task to parent build.postBuild: $PARENT_KITT"
fi

echo
info "review with: git diff $PARENT_KITT $CHILD_REL_PATH"
info "next: register the pack in sr.yaml via scripts/add-sr-pack.sh"
