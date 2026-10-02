#!/usr/bin/env bash

# chmod +x scripts/setup-sp-oidc.sh
# ./scripts/setup-sp-oidc.sh \
#   --app-name        sp-gh-hotel-lab \
#   --resource-group  rg-hotel-streaming-lab \
#   --gh-org          rkvarma1845 \
#   --gh-repo         hotel-streaming-lab \
#   --gh-env          main
#
# Optional (needed only if the repo is private and the GitHub API lookup fails):
#   --github-org-id   <numeric id> \
#   --github-repo-id  <numeric id>

set -euo pipefail

# ─── Input ────────────────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 --app-name <name> --resource-group <rg> \\"
  echo "          --gh-org <org> --gh-repo <repo> --gh-env <env> \\"
  echo "          [--github-org-id <id>] [--github-repo-id <id>]"
  exit 1
}

GITHUB_ORG_ID=""
GITHUB_REPO_ID=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --app-name)            APP_NAME=$2;           shift 2 ;;
    --resource-group)      RESOURCE_GROUP=$2;     shift 2 ;;
    --gh-org)              GH_ORG=$2;             shift 2 ;;
    --gh-repo)             GH_REPO=$2;            shift 2 ;;
    --gh-env)              GH_ENV=$2;             shift 2 ;;
    --github-org-id)       GITHUB_ORG_ID=$2;      shift 2 ;;
    --github-repo-id)      GITHUB_REPO_ID=$2;     shift 2 ;;
    *) echo "Unknown argument: $1"; usage ;;
  esac
done

[[ -z "${APP_NAME:-}"       ]] && { echo "Missing --app-name";       usage; }
[[ -z "${RESOURCE_GROUP:-}" ]] && { echo "Missing --resource-group"; usage; }
[[ -z "${GH_ORG:-}"         ]] && { echo "Missing --gh-org";         usage; }
[[ -z "${GH_REPO:-}"        ]] && { echo "Missing --gh-repo";        usage; }
[[ -z "${GH_ENV:-}"         ]] && { echo "Missing --gh-env";         usage; }

# ─── Resolve subscription ─────────────────────────────────────────────────────
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)

echo ""
echo "Subscription  : $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"
echo "Resource group: $RESOURCE_GROUP"
echo ""

# ─── App Registration ─────────────────────────────────────────────────────────
echo "▶ Checking app registration..."

EXISTING_APP=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv 2>/dev/null || true)

if [[ -n "$EXISTING_APP" ]]; then
  echo "  Already exists, skipping create."
  APP_ID="$EXISTING_APP"
  OBJECT_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)
else
  SP=$(az ad app create --display-name "$APP_NAME" -o json)
  APP_ID=$(echo "$SP" | jq -r '.appId')
  OBJECT_ID=$(echo "$SP" | jq -r '.id')
  echo "  Created: $APP_ID"
fi

# ─── Service Principal ────────────────────────────────────────────────────────
echo ""
echo "▶ Checking service principal..."

EXISTING_SP=$(az ad sp show --id "$APP_ID" --query id -o tsv 2>/dev/null || true)

if [[ -n "$EXISTING_SP" ]]; then
  echo "  Already exists, skipping create."
  SP_OBJECT_ID="$EXISTING_SP"
else
  az ad sp create --id "$APP_ID" -o none
  SP_OBJECT_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)
  echo "  Created: $SP_OBJECT_ID"
fi

TENANT_ID=$(az account show --query tenantId -o tsv)

echo "  App ID       : $APP_ID"
echo "  Tenant ID    : $TENANT_ID"
echo "  SP Object ID : $SP_OBJECT_ID"

# ─── Federated Identity Credential ───────────────────────────────────────────
echo ""
echo "▶ Checking federated identity credential..."

ISSUER="https://token.actions.githubusercontent.com"
AUDIENCE="api://AzureADTokenExchange"
REPO_FULL="${GH_ORG}/${GH_REPO}"

# Helper: idempotently create a single federated identity credential by name.
# Skips creation if a FIC with the same name already exists.
add_federated_credential() {
  local name="$1"
  local subject="$2"
  local issuer="$3"
  local audience="$4"

  local existing
  existing=$(az ad app federated-credential list \
    --id "$OBJECT_ID" \
    --query "[?name=='${name}'].name" \
    -o tsv 2>/dev/null || true)

  if [[ -n "$existing" ]]; then
    echo "  Already exists, skipping: ${name}"
  else
    az ad app federated-credential create \
      --id "$OBJECT_ID" \
      --parameters "{
        \"name\": \"${name}\",
        \"issuer\": \"${issuer}\",
        \"subject\": \"${subject}\",
        \"audiences\": [\"${audience}\"]
      }" -o none
    echo "  ✓ Created: ${name} (subject: ${subject})"
  fi
}

# Resolve GitHub org/repo numeric IDs, needed for the immutable-subject FIC
# now required by orgs that have "immutable identifier claims" enabled
# (otherwise OIDC login fails with AADSTS700213).
if [[ -z "$GITHUB_ORG_ID" || -z "$GITHUB_REPO_ID" ]]; then
  if command -v curl >/dev/null 2>&1; then
    echo "  Fetching org/repo IDs from GitHub API: https://api.github.com/repos/${REPO_FULL}"
    _gh_api=$(curl -sS -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/${REPO_FULL}" 2>/dev/null || true)
    if [[ -n "$_gh_api" ]]; then
      [[ -z "$GITHUB_ORG_ID"  ]] && GITHUB_ORG_ID=$(echo  "$_gh_api" | jq -r '.owner.id // empty' 2>/dev/null || true)
      [[ -z "$GITHUB_REPO_ID" ]] && GITHUB_REPO_ID=$(echo "$_gh_api" | jq -r '.id // empty'       2>/dev/null || true)
    fi
  fi
fi

if [[ -n "$GITHUB_ORG_ID" && -n "$GITHUB_REPO_ID" ]]; then
  REPO_FULL_IMMUT="${GH_ORG}@${GITHUB_ORG_ID}/${GH_REPO}@${GITHUB_REPO_ID}"
  echo "  GitHub IDs: org=${GITHUB_ORG_ID}, repo=${GITHUB_REPO_ID}"
  echo "  Immutable subject prefix: ${REPO_FULL_IMMUT}"
else
  REPO_FULL_IMMUT=""
  echo "  WARNING: could not resolve GitHub org/repo IDs (private repo? no curl/jq? no network?)." >&2
  echo "  WARNING: ID-suffixed FICs will NOT be created. If your org has immutable-identifier"      >&2
  echo "  WARNING: claims enabled (default now), workflow OIDC login WILL fail with AADSTS700213."  >&2
  echo "  WARNING: Look up IDs at https://api.github.com/repos/${REPO_FULL} and re-run with"        >&2
  echo "  WARNING:   --github-org-id <N> --github-repo-id <N>"                                      >&2
fi

# Helper: create BOTH name-based and (if we have IDs) ID-suffixed FIC
# for a single (subject-suffix, cred-suffix) pair. Idempotent — the
# inner add_federated_credential skips FICs that already exist by name.
add_github_fic_pair() {
  local cred_suffix="$1"   # e.g. "env-main" or "branch-master"
  local subject_tail="$2"  # e.g. "environment:main" or "ref:refs/heads/master"

  add_federated_credential \
    "github-${GH_ORG}-${GH_REPO}-${cred_suffix}" \
    "repo:${REPO_FULL}:${subject_tail}" \
    "$ISSUER" "$AUDIENCE"

  if [[ -n "$REPO_FULL_IMMUT" ]]; then
    add_federated_credential \
      "github-${GH_ORG}-${GH_REPO}-${cred_suffix}-immut" \
      "repo:${REPO_FULL_IMMUT}:${subject_tail}" \
      "$ISSUER" "$AUDIENCE"
  fi
}

add_github_fic_pair "env-${GH_ENV}" "environment:${GH_ENV}"

# ─── Role Assignments over Resource Group ────────────────────────────────────
echo ""
echo "▶ Checking role assignments..."

RG_SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"

for ROLE in "Contributor"; do
  EXISTING_ROLE=$(az role assignment list \
    --assignee "$APP_ID" \
    --role     "$ROLE"   \
    --scope    "$RG_SCOPE" \
    --query    "[0].id" -o tsv 2>/dev/null || true)

  if [[ -n "$EXISTING_ROLE" ]]; then
    echo "  Already assigned, skipping: $ROLE"
  else
    az role assignment create \
      --assignee "$APP_ID" \
      --role     "$ROLE"   \
      --scope    "$RG_SCOPE" -o none
    echo "  ✓ $ROLE"
  fi
done

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
echo " Done! Add these to GitHub Actions secrets:"
echo "═══════════════════════════════════════════════"
echo " SP Name               = $APP_NAME"
echo " SP Principal ID       = $SP_OBJECT_ID"
echo " AZURE_CLIENT_ID       = $APP_ID"
echo " AZURE_TENANT_ID       = $TENANT_ID"
echo " AZURE_SUBSCRIPTION_ID = $SUBSCRIPTION_ID"
echo "═══════════════════════════════════════════════"