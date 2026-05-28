# tinycua-backend

Backend API for agent deployment, tool management, and session tracking.

## Features

- **Agent Management**: Create, update, deploy agents
- **Tool Registry**: Store and manage custom tools with dependency resolution
- **Session Tracking**: Track conversation sessions
- **Authentication**: JWT + API key authentication with tenant isolation
- **Runner Integration**: Triggers agent execution on runner service

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
```

## Running

```bash
python -m tinycua_backend.main
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/register` | Register new user |
| POST | `/v1/auth/login` | Login |
| GET | `/v1/agents` | List agents |
| POST | `/v1/agents` | Create agent |
| POST | `/v1/agents/{id}/run` | Run agent |
| GET | `/v1/tools` | List tools |
| POST | `/v1/tools` | Create tool |
| GET | `/v1/sessions` | List sessions |

## Development

```bash
# Run tests
make test

# Run lint
make lint

# Run coverage
make coverage
```
