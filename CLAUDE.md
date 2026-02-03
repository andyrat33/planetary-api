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

- **buildspec.yml:** AWS CodeBuild pipeline pushing to ECR
- **GitHub Actions:** Semgrep SAST scanning on PRs and pushes to main/master
