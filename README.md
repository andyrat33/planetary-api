# Planetary API

A Flask-based CRUD API for managing Star Trek planetary data, designed as a security training tool. The application intentionally includes common web vulnerabilities (SQL injection, command injection, SSRF, path traversal) alongside their secure counterparts to demonstrate secure vs. insecure coding practices.

## Features

- CRUD operations for Star Trek planets
- JWT-based authentication
- Intentionally vulnerable endpoints paired with secure variants
- Minimal HTML/JS frontend
- Docker Compose setup with MySQL and Mailpit (email testing)
- SQLite support for local development
- CI/CD pipelines for Jenkins, AWS CodeBuild, and GitHub Actions (Semgrep SAST)

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
- **Database**: MySQL 5.7 (Docker) or SQLite (local)
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

## CI/CD

- **Jenkinsfile** — Build, seed, smoke test, Postman tests, Semgrep, OWASP Dependency Check
- **buildspec.yml** — AWS CodeBuild pipeline pushing to ECR
- **GitHub Actions** — Semgrep SAST scanning on PRs and pushes to main/master

## Disclaimer

This application contains **intentional security vulnerabilities** for educational purposes. Do not deploy it in a production environment.
