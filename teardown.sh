#!/usr/bin/env bash
# teardown.sh — remove all AWS resources created by setup.sh + cdk deploy.
# Re-running is safe: steps that find nothing skip gracefully.
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

# ── Read config ────────────────────────────────────────────────────────────
if [[ ! -f infra/config.py ]]; then
    err "infra/config.py not found. Run ./setup.sh first to generate it."
    exit 1
fi

REGION=$(python3 -c "import sys; sys.path.insert(0,'infra'); from config import REGION; print(REGION)" 2>/dev/null || true)
ACCOUNT=$(python3 -c "import sys; sys.path.insert(0,'infra'); from config import ACCOUNT; print(ACCOUNT)" 2>/dev/null || true)
CODESTAR_ARN=$(python3 -c "import sys; sys.path.insert(0,'infra'); from config import CODESTAR_CONNECTION_ARN; print(CODESTAR_CONNECTION_ARN)" 2>/dev/null || true)

if [[ -z "$REGION" || -z "$ACCOUNT" ]]; then
    err "Could not read REGION or ACCOUNT from infra/config.py."
    exit 1
fi

# ── Banner ─────────────────────────────────────────────────────────────────
echo -e "${CYAN}"
echo "================================================="
echo "  Planetary API — AWS Teardown"
echo "================================================="
echo -e "${NC}"
echo "Account: $ACCOUNT   Region: $REGION"
echo
echo "This script will:"
echo "  1. Stop the ECS service (immediate Fargate billing stop)"
echo "  2. Empty the S3 artifacts bucket (versioned — uses boto3)"
echo "  3. Empty the ECR repository"
echo "  4. Run cdk destroy --all (VPC, NAT Gateway, ALB, ECS, Pipeline, etc.)"
echo "  5. Delete RETAIN resources (S3 bucket + ECR repo)"
echo "  6. Delete Secrets Manager secrets"
echo "  7. Prompt to delete the RDS instance"
echo "  8. Print remaining optional manual cleanup steps"
echo
echo "Note: ensure your CDK Python environment is active before continuing."
echo "  If using pyenv: pyenv activate <your-cdk-env>"
echo

# ── Prerequisites ──────────────────────────────────────────────────────────
if ! command -v aws &>/dev/null; then
    err "aws CLI not found. Please install it and re-run."
    exit 1
fi
if ! command -v cdk &>/dev/null; then
    err "cdk not found in PATH. Install with: npm install -g aws-cdk"
    exit 1
fi

# ── AWS profile ────────────────────────────────────────────────────────────
read -rp "AWS CLI profile [default]: " PROFILE
PROFILE="${PROFILE:-default}"

echo "Verifying AWS credentials..."
if ! aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" \
        --output text --query Account &>/dev/null; then
    err "Could not authenticate with profile '$PROFILE'. Check your AWS credentials."
    exit 1
fi
success "Authenticated — profile '$PROFILE', account $ACCOUNT, region $REGION"

# ── Confirmation ───────────────────────────────────────────────────────────
echo
echo -e "${YELLOW}Resources that will be permanently deleted:${NC}"
echo
printf "  %-52s %s\n" "Resource" "Cost stopped"
printf "  %-52s %s\n" "----------------------------------------------------" "---------------"
printf "  %-52s %s\n" "NAT Gateway" "~\$32/month"
printf "  %-52s %s\n" "ALB (Application Load Balancer)" "~\$18/month"
printf "  %-52s %s\n" "ECS Fargate service + cluster" "per-task billing"
printf "  %-52s %s\n" "CodePipeline + 9 CodeBuild projects" "per-build billing"
printf "  %-52s %s\n" "S3 artifacts bucket (versioned)" "storage costs"
printf "  %-52s %s\n" "ECR repository  planetary-api" "storage costs"
printf "  %-52s %s\n" "4x Secrets Manager secrets" "~\$0.40/secret/month"
printf "  %-52s %s\n" "VPC, SNS, SSM, IAM, CloudWatch logs" "negligible"
echo
echo "  RDS instance: prompted separately — will not delete without confirmation."
echo
echo -e "${RED}This is irreversible. All pipeline history, container images,"
echo -e "and scan artifacts will be permanently deleted.${NC}"
echo

read -rp "Type 'yes' to proceed with teardown: " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

# ── Step 1 — Stop ECS service ──────────────────────────────────────────────
step "1/8 — Stopping ECS service (immediate Fargate billing stop)..."
SERVICE_ARN=$(aws ecs list-services --cluster planetary-api-cluster \
    --profile "$PROFILE" --region "$REGION" \
    --query 'serviceArns[0]' --output text 2>/dev/null || echo "None")

if [[ "$SERVICE_ARN" != "None" && -n "$SERVICE_ARN" ]]; then
    SERVICE_NAME=$(basename "$SERVICE_ARN")
    aws ecs update-service --cluster planetary-api-cluster \
        --service "$SERVICE_NAME" --desired-count 0 \
        --profile "$PROFILE" --region "$REGION" \
        --output text --query 'service.desiredCount' > /dev/null
    success "ECS service '$SERVICE_NAME' scaled to 0."
else
    warn "ECS cluster planetary-api-cluster not found — skipping."
fi

# ── Step 2 — Look up S3 artifacts bucket ──────────────────────────────────
step "2/8 — Looking up S3 artifacts bucket from CloudFormation..."
BUCKET=$(aws cloudformation describe-stacks \
    --stack-name PlanetaryPipeline \
    --profile "$PROFILE" --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ArtifactsBucketName`].OutputValue' \
    --output text 2>/dev/null || true)

if [[ -n "$BUCKET" && "$BUCKET" != "None" ]]; then
    success "Artifacts bucket: $BUCKET"
else
    warn "Could not find ArtifactsBucketName from PlanetaryPipeline stack — skipping S3 steps."
    BUCKET=""
fi

# ── Step 3 — Empty versioned S3 bucket ────────────────────────────────────
step "3/8 — Emptying versioned S3 bucket..."

# Deletes one object type ("Versions" or "DeleteMarkers") in 1000-item batches
# using only AWS CLI + stdlib python3 — no boto3 required.
_delete_s3_object_type() {
    local object_type="$1"
    local tmpfile
    tmpfile=$(mktemp /tmp/s3-delete-XXXXXX.json)
    while true; do
        aws s3api list-object-versions \
            --bucket "$BUCKET" --profile "$PROFILE" --region "$REGION" \
            --query "${object_type}[].{Key:Key,VersionId:VersionId}" \
            --max-items 1000 --output json 2>/dev/null \
        | python3 -c "
import sys, json
items = json.load(sys.stdin)
if not items:
    sys.exit(0)
print(json.dumps({'Objects': items, 'Quiet': True}))
" > "$tmpfile" 2>/dev/null || break
        [[ ! -s "$tmpfile" ]] && break
        aws s3api delete-objects \
            --bucket "$BUCKET" --profile "$PROFILE" --region "$REGION" \
            --delete "file://$tmpfile" > /dev/null
    done
    rm -f "$tmpfile"
}

if [[ -n "$BUCKET" ]]; then
    _delete_s3_object_type "Versions"
    _delete_s3_object_type "DeleteMarkers"
    success "S3 bucket $BUCKET emptied."
else
    warn "No bucket to empty — skipping."
fi

# ── Step 4 — Empty ECR repository ─────────────────────────────────────────
step "4/8 — Emptying ECR repository planetary-api..."
IMAGES=$(aws ecr list-images --repository-name planetary-api \
    --profile "$PROFILE" --region "$REGION" \
    --query 'imageIds' --output json 2>/dev/null || echo "null")

if [[ "$IMAGES" != "null" && "$IMAGES" != "[]" && -n "$IMAGES" ]]; then
    TMPFILE=$(mktemp /tmp/ecr-images-XXXXXX.json)
    echo "$IMAGES" > "$TMPFILE"
    aws ecr batch-delete-image --repository-name planetary-api \
        --image-ids "file://$TMPFILE" \
        --profile "$PROFILE" --region "$REGION" > /dev/null
    rm -f "$TMPFILE"
    success "ECR images deleted."
else
    warn "ECR repository is empty or not found — skipping."
fi

# ── Step 5 — cdk destroy --all ────────────────────────────────────────────
step "5/8 — Running cdk destroy --all --force..."
echo "  This may take 10-20 minutes while CloudFormation deletes the stacks."
(cd infra && cdk destroy --all --force --profile "$PROFILE")
success "CDK stacks destroyed."

# ── Step 6 — Delete RETAIN resources ──────────────────────────────────────
step "6/8 — Deleting RETAIN resources (S3 bucket + ECR repo)..."
if [[ -n "$BUCKET" ]]; then
    aws s3 rb "s3://$BUCKET" --profile "$PROFILE" --region "$REGION" 2>/dev/null \
        && success "S3 bucket $BUCKET deleted." \
        || warn "S3 bucket $BUCKET not found or already deleted."
fi

aws ecr delete-repository --repository-name planetary-api --force \
    --profile "$PROFILE" --region "$REGION" > /dev/null 2>/dev/null \
    && success "ECR repository planetary-api deleted." \
    || warn "ECR repository planetary-api not found or already deleted."

# ── Step 7 — Delete Secrets Manager secrets ───────────────────────────────
step "7/8 — Deleting Secrets Manager secrets..."
for SECRET in planetary-api/docker-credentials planetary-api/snyk-token \
              planetary-api/semgrep-token planetary-api/db-credentials; do
    aws secretsmanager delete-secret --secret-id "$SECRET" \
        --force-delete-without-recovery \
        --profile "$PROFILE" --region "$REGION" > /dev/null 2>/dev/null \
        && success "Deleted secret: $SECRET" \
        || warn "Secret $SECRET not found or already deleted."
done

# ── Step 8 — RDS instance ─────────────────────────────────────────────────
step "8/8 — RDS instance..."
echo "RDS instances in $REGION:"
aws rds describe-db-instances \
    --profile "$PROFILE" --region "$REGION" \
    --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceClass,DBInstanceStatus]' \
    --output table 2>/dev/null || echo "  (none found or no access)"
echo

read -rp "RDS instance identifier to delete (Enter to skip): " RDS_ID
if [[ -n "$RDS_ID" ]]; then
    aws rds delete-db-instance \
        --db-instance-identifier "$RDS_ID" \
        --skip-final-snapshot \
        --delete-automated-backups \
        --profile "$PROFILE" --region "$REGION" > /dev/null
    success "RDS instance '$RDS_ID' deletion initiated (takes a few minutes)."
else
    warn "Skipping RDS deletion. Delete manually when ready to avoid ongoing charges."
fi

# ── Remaining manual steps ─────────────────────────────────────────────────
echo
echo -e "${CYAN}================================================="
echo "  Remaining optional cleanup"
echo -e "=================================================${NC}"
echo
echo "  1. Disable Security Hub (if not used by other workloads):"
echo "       aws securityhub disable-security-hub \\"
echo "           --region $REGION --profile $PROFILE"
echo
if [[ -n "$CODESTAR_ARN" ]]; then
    echo "  2. Delete CodeStar connection (no ongoing cost — optional):"
    echo "       aws codeconnections delete-connection \\"
    echo "           --connection-arn $CODESTAR_ARN \\"
    echo "           --profile $PROFILE --region $REGION"
    echo
fi
echo "  3. CDK bootstrap stack (only if no other CDK apps in this account/region):"
echo "       aws cloudformation delete-stack --stack-name CDKToolkit \\"
echo "           --profile $PROFILE --region $REGION"
echo "     Then empty and delete the CDK assets bucket:"
echo "       s3://cdk-hnb659fds-assets-${ACCOUNT}-${REGION}"
echo
echo "  4. Remove local config:"
echo "       rm infra/config.py"
echo

echo -e "${CYAN}================================================="
echo "  Teardown complete."
echo -e "=================================================${NC}"
echo
echo "Verify nothing remains:"
echo "  aws cloudformation list-stacks --region $REGION --profile $PROFILE \\"
echo "    --query 'StackSummaries[?contains(StackName,\`Planetary\`)].{Name:StackName,Status:StackStatus}'"
echo "  aws ecr describe-repositories --region $REGION --profile $PROFILE"
echo "  aws s3 ls --profile $PROFILE"
echo "  aws secretsmanager list-secrets --region $REGION --profile $PROFILE \\"
echo "    --query 'SecretList[?starts_with(Name,\`planetary-api\`)].Name'"
