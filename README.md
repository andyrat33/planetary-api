# Planetary API

A Flask-based CRUD API for managing Star Trek planetary data, designed as a security training tool. The application intentionally includes common web vulnerabilities (SQL injection, command injection, SSRF, path traversal) alongside their secure counterparts to demonstrate secure vs. insecure coding practices.

## Features

- CRUD operations for Star Trek planets
- JWT-based authentication
- Intentionally vulnerable endpoints paired with secure variants
- Minimal HTML/JS frontend
- Docker Compose setup with MySQL and Mailpit (email testing)
- SQLite support for local development
- AWS CDK security pipeline with Semgrep SAST, Snyk SCA, Security Hub integration, and Newman smoke tests

## Quick Setup (AWS deployment)

To deploy the full AWS CDK security pipeline, run the interactive setup script:

```bash
./setup.sh
```

It will collect your AWS profile, GitHub details, Docker Hub credentials, and security scanning tokens; create the required Secrets Manager secrets; and generate `infra/config.py`. Then follow the printed deploy instructions (`cdk deploy --all`).

See [infra/config.example.py](infra/config.example.py) for the shape of the generated config file.

---

## Quick Start

### Docker Compose (recommended)

```bash
docker compose up
```

| Service | URL |
|---------|-----|
| API     | http://localhost:5001 |
| MySQL   | localhost:3306 |
| Mailpit | http://localhost:8025 |

### Local Development (SQLite)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export DB_USER=root DB_PASSWORD=rootpassword DB_HOST=localhost DB_NAME=planetary
flask run
```

### Database Setup

```bash
flask db_create   # Create tables
flask db_drop     # Drop all tables
flask db_seed     # Load seed data from star_trek_planets.json and users.json
```

## API Endpoints

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/` | Frontend UI |
| GET    | `/planets` | List all planets |
| GET    | `/planet_details/<id>` | Get planet by ID |
| GET    | `/random_planet` | Get a random planet name |
| POST   | `/login` | Login, returns JWT token |
| POST   | `/register` | Register a new user |
| GET    | `/retrieve_password/<email>` | Email password recovery |

### Protected (JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/get_planet/<name>` | Fetch planet by name |
| POST   | `/add_planet` | Create a planet |
| PUT    | `/update_planet` | Update a planet |
| DELETE | `/remove_planet/<id>` | Delete a planet |

### Vulnerable (for security training)

| Endpoint | Vulnerability |
|----------|---------------|
| `/get_planet_sqlmap` | SQL Injection |
| `/dbsize/<dbfile>` | Command Injection |
| `/fetch` | SSRF |
| `/read_log` | Path Traversal |

Secure variants (`/fetch/safe`, `/read_log/safe`) demonstrate proper input validation.

## Authentication

The API uses JWT tokens via Flask-JWT-Extended.

```bash
# Login to get a token
curl -X POST http://localhost:5001/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "P@ssw0rd"}'

# Use the token on protected routes
curl http://localhost:5001/get_planet/Vulcan \
  -H "Authorization: Bearer <token>"
```

## Architecture

Single-file Flask application (`app.py`) containing all models, schemas, routes, and CLI commands.

- **ORM**: SQLAlchemy (`User` and `Planet` models)
- **Serialization**: Marshmallow (`UserSchema`, `PlanetSchema`)
- **Auth**: Flask-JWT-Extended with `@jwt_required` decorator
- **Database**: MySQL 5.7 (Docker) or SQLite (local) or RDS MySQL 8.0 (AWS)
- **Email**: Flask-Mail configured for Mailpit in Docker

## Testing

API tests are provided as:

- **Postman collection**: `planetary-api.postman_collection.json`
- **HTTP client file**: `planetary-api.http` (IntelliJ / VS Code REST Client)

## Linting

```bash
flake8 .                        # Lint check (max-line-length: 120)
pre-commit run --all-files      # Black + flake8 + file fixers
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DB_USER` | Database username |
| `DB_PASSWORD` | Database password |
| `DB_HOST` | Database host |
| `DB_NAME` | Database name |
| `MAIL_SERVER` | SMTP server |
| `MAIL_PORT` | SMTP port |
| `MAIL_USE_TLS` | Enable TLS |
| `MAIL_USERNAME` | SMTP username |
| `MAIL_PASSWORD` | SMTP password |

## CI/CD — AWS Security Pipeline

The production pipeline is built with AWS CDK (Python) in the `infra/` directory and deployed to AWS (`us-east-1`).

### Pipeline Stages

```
GitHub (master)
    │
    ▼
[1] Source         — CodeStar connection to your GitHub repo
[2] Build          — Docker build + push to ECR
[3] SecurityScan   — three parallel actions:
                     • Semgrep SAST → ASFF → Security Hub
                     • Snyk SCA → ASFF → Security Hub + CycloneDX SBOM → S3
                     • Postman security tests (SQLi, cmdi, XSS) with --suppress-exit-code
[4] SecurityGate   — blocks on HIGH/CRITICAL Security Hub findings
                     (SSM parameter /planetary-api/pipeline/security-override
                      can be set to "true" to bypass for intentional vulns)
[5] ManualApproval — SNS email with Security Hub console link
[6] SmokeTest      — Newman/Postman functional tests (Basic + Negative folders)
                     in Docker-in-Docker; results uploaded to S3
[7] Deploy         — ECS Fargate rolling update
[8] DbMigrate      — runs `flask db_create` as one-off ECS task against prod RDS
                     (idempotent — safe on every deploy; creates missing tables only)
[9] Lockdown       — restricts ALB SG to AllowedIp CIDR (optional pipeline
                     variable, default 'none' = unrestricted 0.0.0.0/0)
[10] Verify        — live health check + URL output (skipped if ALB is locked)
```

### Infrastructure (CDK Stacks)

| Stack | Resources |
|-------|-----------|
| `PlanetaryEcr` | ECR repository |
| `PlanetaryEcs` | VPC, ECS Fargate cluster, ALB, task definition |
| `PlanetaryPipeline` | CodePipeline, CodeBuild projects, S3, SNS, SSM, IAM |

RDS MySQL 8.0 (`db.t3.micro`) is provisioned separately in the same VPC.

### Security Hub Integration

All findings from Semgrep and Snyk are converted to ASFF format and imported to AWS Security Hub as a single pane of glass. The `infra/scripts/` directory contains the converters:

- `sarif_to_asff.py` — Semgrep SARIF → ASFF
- `snyk_to_asff.py` — Snyk JSON → ASFF with CVE/CWE metadata

### CDK Deployment

Run `./setup.sh` first to generate `infra/config.py`, then:

```bash
cd infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk deploy --all --profile <your-aws-profile>
```

CDK outputs include the ALB DNS name, SNS approval topic ARN, and S3 artifacts bucket name.

### Security Override

To deploy despite Security Hub findings (e.g. when testing the intentional vulnerabilities):

```bash
aws ssm put-parameter --name /planetary-api/pipeline/security-override \
  --value "true" --overwrite --type String --profile <your-aws-profile>
# Re-run the pipeline, then reset:
aws ssm put-parameter --name /planetary-api/pipeline/security-override \
  --value "false" --overwrite --type String --profile <your-aws-profile>
```

### GitHub Actions

Semgrep SAST scanning runs on all PRs and pushes to `main`/`master`.

## Disclaimer

This application contains **intentional security vulnerabilities** for educational purposes. Do not deploy it in a production environment without the appropriate controls.
