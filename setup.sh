#!/usr/bin/env bash
# setup.sh — one-time setup for deploying Planetary API to AWS via CDK.
# Re-running this script is safe: it updates existing secrets and overwrites config.py.
set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

step()    { echo -e "\n${CYAN}==> $*${NC}"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}!${NC} $*"; }
err()     { echo -e "${RED}ERROR:${NC} $*" >&2; }

prompt() {
    # prompt VAR_NAME "Display text" "default value (empty string = required)"
    local var_name="$1" prompt_text="$2" default="$3" input
    if [[ -n "$default" ]]; then
        read -rp "${prompt_text} [${default}]: " input
        input="${input:-$default}"
    else
        while true; do
            read -rp "${prompt_text}: " input
            [[ -n "$input" ]] && break
            err "This field is required."
        done
    fi
    printf -v "$var_name" '%s' "$input"
}

prompt_secret() {
    local var_name="$1" prompt_text="$2" input
    while true; do
        read -rsp "${prompt_text}: " input
        echo
        [[ -n "$input" ]] && break
        err "This field is required."
    done
    printf -v "$var_name" '%s' "$input"
}

# ── Banner ─────────────────────────────────────────────────────────────────
echo -e "${CYAN}"
echo "================================================="
echo "  Planetary API — AWS CDK Setup"
echo "================================================="
echo -e "${NC}"
echo "This script will:"
echo "  1. Check prerequisites (aws, cdk, python3, node)"
echo "  2. Collect your configuration"
echo "  3. Create AWS Secrets Manager secrets"
echo "  4. Pause for a manual CodeStar connection step"
echo "  5. Generate infra/config.py"
echo "  6. Print deploy instructions"
echo

# ── 1. Prerequisites ───────────────────────────────────────────────────────
step "Checking prerequisites..."

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        err "$1 is not installed. Please install it and re-run."
        exit 1
    fi
    success "$1 found ($(command -v "$1"))"
}

check_cmd aws
check_cmd cdk
check_cmd python3
check_cmd node

# ── 2. Configuration ───────────────────────────────────────────────────────
step "AWS configuration"
prompt AWS_PROFILE "AWS CLI profile name" "default"
prompt AWS_REGION  "AWS region" "us-east-1"

echo "Detecting AWS account ID..."
if ! ACCOUNT_ID=$(aws sts get-caller-identity \
        --profile "$AWS_PROFILE" \
        --query Account \
        --output text 2>/dev/null); then
    err "Could not detect AWS account ID. Check your AWS profile and credentials."
    exit 1
fi
success "Account ID: $ACCOUNT_ID"

step "GitHub configuration"
prompt GITHUB_OWNER  "GitHub username or org" ""
prompt GITHUB_REPO   "GitHub repository name" "planetary-api"
prompt GITHUB_BRANCH "Branch to deploy from" "master"

step "Docker Hub credentials"
echo "  Used to avoid Docker Hub pull rate limits during CodeBuild runs."
prompt        DOCKER_USER "Docker Hub username" ""
prompt_secret DOCKER_PASS "Docker Hub password"

step "Security scanning tokens"
echo "  Snyk auth token — https://app.snyk.io → Account Settings → Auth Token"
prompt_secret SNYK_TOKEN "Snyk auth token"

echo "  Semgrep app token — https://semgrep.dev → Settings → Tokens"
prompt_secret SEMGREP_TOKEN "Semgrep app token"

step "Notifications"
prompt APPROVAL_EMAIL "Email address for pipeline approval notifications" ""

# ── 3. Secrets Manager ─────────────────────────────────────────────────────
step "Creating/updating AWS Secrets Manager secrets..."

upsert_secret() {
    local name="$1" value="$2" desc="$3"
    if aws secretsmanager describe-secret \
            --secret-id "$name" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --output text --query Name &>/dev/null; then
        aws secretsmanager update-secret \
            --secret-id "$name" \
            --secret-string "$value" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --output text --query Name > /dev/null
        success "Updated secret: $name"
    else
        aws secretsmanager create-secret \
            --name "$name" \
            --description "$desc" \
            --secret-string "$value" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --output text --query Name > /dev/null
        success "Created secret: $name"
    fi
}

upsert_secret \
    "planetary-api/docker-credentials" \
    "{\"DOCKER_HUB_USERNAME\":\"${DOCKER_USER}\",\"DOCKER_HUB_PASSWORD\":\"${DOCKER_PASS}\"}" \
    "Docker Hub credentials for Planetary API pipeline"

upsert_secret \
    "planetary-api/snyk-token" \
    "{\"SNYK_TOKEN\":\"${SNYK_TOKEN}\"}" \
    "Snyk auth token for Planetary API security scanning"

upsert_secret \
    "planetary-api/semgrep-token" \
    "{\"SEMGREP_APP_TOKEN\":\"${SEMGREP_TOKEN}\"}" \
    "Semgrep app token for Planetary API SAST scanning"

# ── 4. CodeStar connection (manual) ───────────────────────────────────────
step "CodeStar connection (manual step required)"
echo
echo "  Creating a GitHub connection requires an OAuth browser flow — it cannot"
echo "  be automated. Please complete the following steps now:"
echo
echo "  1. Open the AWS Console:"
echo "     https://${AWS_REGION}.console.aws.amazon.com/codesuite/settings/connections"
echo "  2. Click 'Create connection' → provider: GitHub"
echo "  3. Name it 'planetary-api' and complete the OAuth flow"
echo "  4. Copy the Connection ARN (starts with arn:aws:codeconnections:...)"
echo
while true; do
    read -rp "Paste the CodeStar Connection ARN: " CODESTAR_ARN
    if [[ "$CODESTAR_ARN" =~ ^arn:aws:code(connections|star-connections): ]]; then
        break
    fi
    warn "ARN should start with 'arn:aws:codeconnections:' or 'arn:aws:codestar-connections:'. Try again (or Ctrl-C to exit and edit infra/config.py manually)."
done
success "CodeStar ARN: $CODESTAR_ARN"

# ── 5. Generate infra/config.py ───────────────────────────────────────────
step "Generating infra/config.py..."

cat > infra/config.py << PYEOF
# Generated by setup.sh — re-run setup.sh to update.
# This file is gitignored — it contains your account-specific configuration.
# See infra/config.example.py for the expected shape.

ACCOUNT = "${ACCOUNT_ID}"
REGION = "${AWS_REGION}"

GITHUB_OWNER = "${GITHUB_OWNER}"
GITHUB_REPO = "${GITHUB_REPO}"
GITHUB_BRANCH = "${GITHUB_BRANCH}"

CODESTAR_CONNECTION_ARN = "${CODESTAR_ARN}"

# Secrets Manager secret holding Docker Hub credentials.
DOCKER_SECRET_NAME = "planetary-api/docker-credentials"
PYEOF

success "infra/config.py written."

# ── 6. Deploy instructions ─────────────────────────────────────────────────
step "Setup complete. Next steps:"
echo
echo "  a) Enable Security Hub (skip if already enabled):"
echo "     aws securityhub enable-security-hub --region ${AWS_REGION} --profile ${AWS_PROFILE}"
echo
echo "  b) Install CDK Python dependencies:"
echo "     cd infra"
echo "     python3 -m venv .venv && source .venv/bin/activate"
echo "     pip install -r requirements.txt"
echo
echo "  c) Bootstrap CDK (first time only, per account/region):"
echo "     cdk bootstrap aws://${ACCOUNT_ID}/${AWS_REGION} --profile ${AWS_PROFILE}"
echo
echo "  d) Deploy all stacks:"
echo "     cdk deploy --all --profile ${AWS_PROFILE}"
echo
echo "     RDS MySQL 8.0 is provisioned automatically by CDK (PlanetaryEcs stack)."
echo "     The DB credentials secret is generated and injected into ECS at runtime."
echo
echo "  e) After deploy, subscribe your email to the SNS approval topic:"
echo "     The ApprovalTopicArn is printed in the CDK outputs."
echo "     aws sns subscribe --topic-arn <ApprovalTopicArn> \\"
echo "         --protocol email --notification-endpoint ${APPROVAL_EMAIL} \\"
echo "         --profile ${AWS_PROFILE}"
echo
echo "  f) Push a commit to trigger the pipeline. The first run will block at"
echo "     SecurityGate — the app has intentional vulnerabilities. To allow it:"
echo "     aws ssm put-parameter --name /planetary-api/pipeline/security-override \\"
echo "         --value \"true\" --overwrite --type String --profile ${AWS_PROFILE}"
echo "     Reset after the pipeline completes:"
echo "     aws ssm put-parameter --name /planetary-api/pipeline/security-override \\"
echo "         --value \"false\" --overwrite --type String --profile ${AWS_PROFILE}"
echo
echo "     The DbMigrate stage runs flask db_create (idempotent) and flask db_seed"
echo "     (skips if already seeded) automatically on every deploy."
echo
success "All done!"
