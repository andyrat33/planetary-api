# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Planetary API is an educational Flask application that provides a CRUD API for managing Star Trek planetary data. It intentionally includes security vulnerabilities (SQLi, command injection, SSRF, path traversal) alongside secure implementations for security training purposes.

## Development Commands

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running (Docker Compose — app + MySQL + Mailpit)
```bash
docker compose up
```
- App: http://localhost:5001
- MySQL: localhost:3306
- Mailpit UI: http://localhost:8025 (captures emails for testing)

### Running (Local — uses SQLite)
```bash
export DB_USER=root DB_PASSWORD=rootpassword DB_HOST=localhost DB_NAME=planetary
flask run
```

### Database Management (Flask CLI)
```bash
flask db_create   # Create tables
flask db_drop     # Drop all tables
flask db_seed     # Load seed data from star_trek_planets.json and users.json
```

### Linting
```bash
flake8 .                        # Linting (max-line-length: 120)
pre-commit run --all-files      # Black formatting + flake8 + file fixers
```

### Testing
No unit test suite. API testing is done via Postman collection (`planetary-api.postman_collection.json`) or the HTTP client file (`planetary-api.http`).

## Architecture

**Single-file Flask app (`app.py`)** containing all models, schemas, routes, and CLI commands.

### Models (SQLAlchemy)
- `User` — authentication accounts (table: `users`)
- `Planet` — planetary data (table: `planets`)

### Serialization (Marshmallow)
- `UserSchema` and `PlanetSchema` handle JSON serialization/deserialization

### Authentication
- JWT tokens via Flask-JWT-Extended
- `POST /login` returns a JWT access token
- Protected routes use `@jwt_required` decorator
- JWT secret is hardcoded as `"super-secret"` (intentional for educational use)

### Database
- **Docker Compose:** MySQL 5.7 (`mysql+pymysql://`)
- **Local dev:** SQLite (`planets.db`)
- **AWS (prod):** RDS MySQL 8.0 (`planetary-api-db.co5qauskgubh.us-east-1.rds.amazonaws.com`)
- Connection string is built from env vars: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`

### Route Categories
- **Public:** `/planets`, `/planet_details/<id>`, `/random_planet`, `/login`, `/register`
- **Protected (JWT):** `/get_planet/<name>`, `/add_planet`, `/update_planet`, `/remove_planet/<id>`
- **Intentionally vulnerable:** `/get_planet_sqlmap` (SQLi), `/dbsize/<dbfile>` (command injection), `/fetch` (SSRF), `/read_log` (path traversal)
- **Secure variants:** `/fetch/safe` (URL-validated), `/read_log/safe` (path-validated, commented in code)

### Frontend
Minimal HTML+JS UI served from `templates/index.html` at `GET /`. Provides login, planet search, add, and delete functionality.

## Environment Variables

```
DB_USER, DB_PASSWORD, DB_HOST, DB_NAME              # Database connection
MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS                # Mail server config (defaults to Mailtrap)
MAIL_USERNAME, MAIL_PASSWORD                        # Mail credentials
```

## CI/CD

### AWS CDK Pipeline (primary — `infra/`)

The production pipeline is built with AWS CDK (Python) and deployed to account `450372565572`, region `us-east-1`.

**Three CDK stacks:**
- `PlanetaryEcr` (`infra/stacks/ecr_stack.py`) — ECR repository `planetary-api`
- `PlanetaryEcs` (`infra/stacks/ecs_stack.py`) — VPC, ECS Fargate cluster + ALB, references RDS MySQL 8.0 credentials from Secrets Manager
- `PlanetaryPipeline` (`infra/stacks/pipeline_stack.py`) — full 10-stage CodePipeline

**Pipeline stages:**
1. **Source** — GitHub (`andyrat33/planetary-api`, branch `master`) via CodeStar connection
2. **Build** — Docker build + ECR push, produces `imagedefinitions.json`
3. **SecurityScan** — three parallel actions: Semgrep SAST, Snyk SCA, and Postman security tests; findings imported to Security Hub in ASFF format
4. **SecurityGate** — queries Security Hub for HIGH/CRITICAL findings; blocks pipeline unless SSM override is `true`
5. **ManualApproval** — SNS email notification with Security Hub console link; reviewer approves/rejects
6. **SmokeTest** — Docker-in-Docker: MySQL + app containers, Newman/Postman tests, results uploaded to S3
7. **Deploy** — ECS Fargate rolling update via `imagedefinitions.json`
8. **DbMigrate** — runs `flask db_create` as a one-off ECS Fargate task against prod RDS; idempotent (SQLAlchemy `create_all`), safe on every deploy; fails pipeline on non-zero exit
9. **Lockdown** — optionally restricts ALB SG to a single CIDR via the `AllowedIp` pipeline variable; defaults to `none` (unrestricted)
10. **Verify** — live health check against the ALB (skipped if `AllowedIp` is set, as CodeBuild can't reach a locked-down ALB); prints URL and commit SHA

**Buildspecs** (`infra/buildspecs/`):
- `build.yml` — Docker build + ECR push, Docker Hub login via Secrets Manager
- `semgrep.yml` — Semgrep SAST → SARIF → ASFF → Security Hub + S3
- `snyk_sca.yml` — Snyk SCA + CycloneDX SBOM → ASFF → Security Hub + S3
- `postman_security.yml` — Docker-in-Docker, runs Postman `Security` folder with `--suppress-exit-code`
- `security_gate.yml` — Security Hub query + SSM override check
- `smoke_test.yml` — Docker-in-Docker Newman tests (Postman `Basic` + `Negative` folders)
- `db_migrate.yml` — runs `flask db_create` as one-off ECS Fargate task; boto3 polls until STOPPED, fails on non-zero exit; `db_seed` intentionally excluded (would insert duplicates)
- `lockdown.yml` — updates ALB SG port-80 rule to `AllowedIp` CIDR, or restores `0.0.0.0/0` if `none`
- `verify.yml` — curl health check against live ALB; prints deployment URL and commit SHA

**Converter scripts** (`infra/scripts/`):
- `sarif_to_asff.py` — converts Semgrep SARIF output to ASFF (ERROR→HIGH, WARNING→MEDIUM, NOTE→LOW)
- `snyk_to_asff.py` — converts Snyk JSON output to ASFF with CVE/CWE/package metadata

**CDK deployment commands:**
```bash
cd infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# One-time bootstrap (already done for 450372565572/us-east-1)
AWS_PROFILE=andy_admin cdk bootstrap

# Deploy all stacks
AWS_PROFILE=andy_admin cdk deploy --all

# Deploy a single stack
AWS_PROFILE=andy_admin cdk deploy PlanetaryPipeline
```

**IP lockdown** (to restrict ALB access to a specific IP after deploy):
```bash
# Trigger via boto3 — AWS CLI version installed doesn't support --variables
cd infra && pyenv activate aws_cdk_python_3.14.3
AWS_PROFILE=andy_admin python3 -c "
import boto3
boto3.client('codepipeline', region_name='us-east-1').start_pipeline_execution(
    name='planetary-api-pipeline',
    variables=[{'name': 'AllowedIp', 'value': '1.2.3.4/32'}]
)"
# To restore unrestricted access, trigger without AllowedIp (uses default 'none')
```

**Security override** (to deploy despite Security Hub findings):
```bash
# Allow pipeline to proceed
aws ssm put-parameter --name /planetary-api/pipeline/security-override \
  --value "true" --overwrite --type String --profile andy_admin

# Reset after deploy
aws ssm put-parameter --name /planetary-api/pipeline/security-override \
  --value "false" --overwrite --type String --profile andy_admin
```

**Typical workflow:**

| Scenario | Override | AllowedIp |
|---|---|---|
| Normal push — verify gate blocks | `false` | `none` |
| Deploy for testing, open access | `true` | `none` |
| Deploy for testing, restrict to your IP | `true` | `1.2.3.4/32` |
| Re-open after a locked deploy | `true` | `none` |

ManualApproval always fires regardless of the override — a human must approve before anything deploys.

**AWS resource references:**
- ALB: `Planet-Plane-SNDR7vxPgVHV-1816646008.us-east-1.elb.amazonaws.com`
- ECR: `450372565572.dkr.ecr.us-east-1.amazonaws.com/planetary-api`
- ECS cluster: `planetary-api-cluster`
- RDS: `planetary-api-db.co5qauskgubh.us-east-1.rds.amazonaws.com`
- Pipeline: `planetary-api-pipeline`
- Artifacts bucket: `planetarypipeline-artifactsbucket2aac5544-ia3wnxtts7eq`
- SNS approval topic: `arn:aws:sns:us-east-1:450372565572:PlanetaryPipeline-ApprovalTopic1D517B4C-NqFIB9PFwYya`

**AWS Secrets Manager secrets:**
- `prod/docker-login-iJ6OPC` — Docker Hub credentials (`DOCKER_HUB_USERNAME`, `DOCKER_HUB_PASSWORD`)
- `planetary-api/snyk-token` — Snyk auth token (`SNYK_TOKEN`)
- `planetary-api/semgrep-token` — Semgrep app token (`SEMGREP_APP_TOKEN`)
- `planetary-api/db-credentials` — RDS credentials (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`)

**Known CDK quirks:**
- Do NOT call `ecr_repo.grant_pull(task_definition.execution_role)` — `execution_role` is null at synth time; CDK handles ECR permissions automatically via `ContainerImage.from_ecr_repository()`
- Do NOT use `codebuild.Cache.no_cache()` — no cache is the default in CDK v2, that method does not exist
- `EcsDeployAction` takes either `input` or `image_file`, not both
- `securityhub.CfnHub` was removed because Security Hub was enabled manually; re-adding it will cause a 409 conflict
- `codepipeline.Variable` default value must be 1–1000 chars — use `"none"` as the sentinel for "not set", not `""`
- `aws codepipeline start-pipeline-execution --variables` is not supported by the installed AWS CLI version; use boto3 instead (see IP lockdown command above)
- ASFF `WorkflowState` field is deprecated and rejected by `batch-import-findings` — use nothing (RecordState only)
- ASFF `Vulnerabilities[].Cwes` expects strings (`"CWE-79"`), not integers
- SecurityGate: `get-findings --query 'length(Findings)'` emits one count per page when paginating — capture via `awk '{sum+=$1} END{print sum+0}'` to get a single integer, otherwise the `[ -gt ]` comparison fails silently and the gate passes

### GitHub Actions
Semgrep SAST scanning on PRs and pushes to `main`/`master` (`.github/workflows/`).
