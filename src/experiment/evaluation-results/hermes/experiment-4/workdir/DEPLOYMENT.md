# Deployment Guide

## Quick Start (Local Development)

```bash
cd /workspace/experiment-4

# Install dependencies
pip install -r requirements.txt

# Initialize database  
python app/init_db.py

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Production Deployment Options

### Option 1: Docker (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  notion-clone:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=sqlite:///./data/notion_clone.db
```

Start with: `docker-compose up -d`

### Option 2: Gunicorn + Nginx (Production Server)

Install production dependencies:
```bash
pip install gunicorn uvicorn[standard]
```

Run with Gunicorn:
```bash
gunicorn app.main:app \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --keep-alive 5
```

### Option 3: PythonAnywhere / Heroku / DigitalOcean

For cloud platforms, create a `Procfile`:
```
web: gunicorn app.main:app --bind 0.0.0.0:$PORT
```

## Environment Variables (.env)

Create `.env` file in project root:

```bash
DATABASE_URL=sqlite:///./notion_clone.db
SECRET_KEY=your-secret-key-here-generate-one-using-python-jose
HOST=0.0.0.0
PORT=8000
DEBUG=true  # Set to false for production
```

## Database Backup Strategy (SQLite)

For SQLite, regularly backup the database file:

```bash
# Manual backup
cp notion_clone.db backup_$(date +%Y%m%d).db

# Or use sqlite3 command line
sqlite3 notion_clone.db ".dump" > backup.sql
```

## Scaling Considerations

As your application grows:

1. **Migrate to PostgreSQL**: Replace SQLite with PostgreSQL for better concurrency
2. **Add Redis cache** for frequently accessed pages/databases  
3. **Use CDN** for cover images and static assets
4. **Implement rate limiting** on API endpoints
5. **Set up monitoring** (Prometheus/Grafana)

## Security Checklist

- [ ] Use strong SECRET_KEY in production
- [ ] Implement proper password hashing with bcrypt
- [ ] Add CSRF protection for web forms
- [ ] Enable HTTPS/TLS certificates
- [ ] Set CORS headers appropriately
- [ ] Sanitize all user inputs to prevent XSS
- [ ] Rate limit API endpoints

## Monitoring & Logging

Add logging configuration to `main.py`:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

---

For any issues or questions, check the README.md file!
