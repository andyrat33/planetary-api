# config.py shape — copy this to config.py and fill in your values,
# or run ./setup.sh from the repo root to generate it automatically.
# This file is committed to the repo as a template.
# infra/config.py (the real one) is gitignored.

ACCOUNT = "123456789012"  # 12-digit AWS account ID
REGION = "us-east-1"  # AWS region to deploy into

GITHUB_OWNER = "your-username"  # GitHub account or org that owns the fork
GITHUB_REPO = "planetary-api"  # GitHub repository name
GITHUB_BRANCH = "master"  # Branch the pipeline watches

# Create this in the AWS Console before running `cdk deploy`:
# Console → Developer Tools → Connections → Create connection → GitHub
# Complete the OAuth flow, then paste the resulting ARN here.
CODESTAR_CONNECTION_ARN = (
    "arn:aws:codeconnections:us-east-1:123456789012"
    ":connection/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
)

# Secrets Manager secret holding Docker Hub credentials.
# Created automatically by setup.sh.
# Shape: {"DOCKER_HUB_USERNAME": "...", "DOCKER_HUB_PASSWORD": "..."}
DOCKER_SECRET_NAME = "planetary-api/docker-credentials"
