# tinycua-backend

Backend API for session storage and management with multi-tenant authentication.

## Features

- **Session Management**: Create, read, update, and delete conversation sessions
- **Message Storage**: Store and retrieve messages within sessions
- **Authentication**: JWT + API key authentication with tenant isolation
- **Pure Storage Architecture**: Stores agent/tool configurations but does not execute them

## Setup

```bash
# Install dependencies
pip install -e .

# Or use make
make install
```

## Configuration

Create `.config.yaml`:

```yaml
runner:
  url: "http://localhost:8003"
  token: "your-runner-token"

database:
  url: "postgresql://user:pass@localhost:5432/tinycua"

auth:
  jwt_secret: "your-secret"
  jwt_algorithm: "HS256"
  jwt_expiration_hours: 24

server:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:3000"
```

## Running

```bash
python -m tinycua_backend.main
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/v1/auth/register` | Register new user |
| POST | `/v1/auth/login` | Login |
| POST | `/v1/sessions` | Create session |
| GET | `/v1/sessions` | List sessions |
| GET | `/v1/sessions/{id}` | Get session |
| PUT | `/v1/sessions/{id}` | Update session |
| DELETE | `/v1/sessions/{id}` | Delete session |
| GET | `/v1/sessions/{id}/messages` | List messages |
| POST | `/v1/sessions/{id}/messages` | Create message |

## Development

```bash
# Run tests
make test

# Run lint
make lint

# Run coverage
make coverage
```
