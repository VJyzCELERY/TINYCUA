# 🚀 Deployment Guide - Notion Clone

## Current State
The application is designed for local development with SQLite. Here are deployment options:

---

## Option 1: Self-Hosted (Single Server)

### Prerequisites
- Linux/Windows server or VPS
- Python 3.8+ installed
- Optional: Nginx as reverse proxy, SSL certificates

### Step-by-Step Deployment

#### 1. Prepare the Application Directory
```bash
cd /workspace/experiment-4/notion-app
# Install dependencies in production mode (no debug)
pip install -r requirements.txt --upgrade --no-cache-dir
```

#### 2. Create Production WSGI Config (`gunicorn_config.py`):
```python
def workers():
    return 1  # Single worker for single-user app; scale up if needed

def worker_class():
    return 'sync'  # Or use geventgevent for async I/O
```

#### 3. Start with Gunicorn:
```bash
gunicorn -w 1 -b 0.0.0.0:5000 backend.app:app --timeout=60 --keep-alive=5
```

#### 4. Set Up Nginx as Reverse Proxy (Optional but Recommended):
Edit `/etc/nginx/sites-available/notion-clone`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;  # Or use localhost for development
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

#### 5. Enable HTTPS with Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
# Follow prompts to complete SSL setup
```

---

## Option 2: Cloud Platforms (Easiest)

### Railway.app (Recommended for Flask apps)
1. Push code to GitHub or upload project files directly
2. Create new app in Railway, select Python environment
3. Add `requirements.txt` from your repo
4. Set entrypoint to `python backend/app.py`
5. Deploy! Railway will auto-provision database (or use their SQLite support)
6. Enable HTTPS automatically
7. Get free subdomain or connect custom domain

### Render.com Alternative:
1. Push to GitHub repo or upload project via CLI
2. Create "Web Service" with Python environment
3. Set root directory and start command (`python backend/app.py`)
4. Connect SQLite database (Render supports it natively for small apps, but consider PostgreSQL migration later)
5. Deploy automatically on push
6. Configure custom domain in settings
7. HTTPS enabled by default

### Heroku (Requires app to be a proper Flask project):
1. Create `Procfile`:
   ```
   web: gunicorn backend.app:app -b 0.0.0.0:$PORT --timeout=60
   ```
2. Update requirements.txt with production dependencies
3. Push to Heroku:
   ```bash
   heroku create your-app-name
   git push heroku main
   heroku pscale:scale-to-1  # If using multiple workers
   ```
4. Set environment variables via `heroku config:set`
5. Add database addon if migrating from SQLite to PostgreSQL:
   ```bash
   heroku addons:create heroku-postgresql:hobby-dev
   heroku run python -c 'from flask import current_app; print(current_app.config["DATABASE_URI"])'
   ```

---

## Option 3: Docker Containerization

### Create `Dockerfile`:
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/public/ ./frontend/public/

EXPOSE 5000
CMD ["python", "backend/app.py"]
```

### Build and Run:
```bash
docker build -t notion-clone .
docker run -p 5000:5000 --name notion-app notion-clone
# Or with persistent storage for database:
docker run -d \
  -v $(pwd)/database.db:/app/database.db \
  -p 5000:5000 \
  --name notion-app \
  notion-clone
```

### Deploy to Docker Hub + Cloud Provider:
1. Push image: `docker push yourusername/notion-clone`  
2. Deploy to AWS ECS, Google Cloud Run, Azure Container Apps, or any container host
3. Use environment variables for configuration (database path, secret key)
4. Enable auto-scaling if needed (requires stateless design; consider externalizing database)

---

## Database Migration Options

### Current: SQLite (Local Development / Small Scale)
- **Pros**: Simple setup, single-file storage, no server required  
- **Cons**: Not ideal for multi-user production, limited scaling, BLOB image storage inefficient  

### Recommended Production Upgrade: PostgreSQL
1. Add `psycopg2-binary` to requirements.txt:
   ```
pip install psycopg2-binary
```

2. Modify connection string in app.py or use environment variable:
   ```python
   import os
   DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
   conn = sqlite3.connect(DATABASE_URL.replace('postgresql://', ''))  # Or use SQLAlchemy for abstraction
   ```

3. Deploy with managed PostgreSQL (Railway, Render, Heroku all support it automatically)
4. Migrate existing SQLite data to PostgreSQL using:
   - `pgloader` tool: https://github.com/dimitri/pgloader
   - Custom Python script with both drivers loaded
   - Export/import via CSV as intermediate step

---

## Environment Variables for Production

Create `.env.production` file (do NOT commit to git):
```bash
FLASK_SECRET_KEY=your-secret-key-here-at-least-32-characters-long
DEBUG=false  # Never use debug in production!
PORT=5000
DATABASE_PATH=/app/database.db  # Or external PostgreSQL URL
ALLOWED_HOSTS=yourdomain.com,localhost
```

Load them in app.py:
```python
from dotenv import load_dotenv
load_dotenv()
os.environ['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
os.environ['DEBUG'] = str(os.getenv('DEBUG', 'false')).lower()
os.environ['PORT'] = str(os.getenv('PORT', 5000))
```

---

## Security Checklist for Production

- [ ] Set `debug=False` in app.py or via environment variable
- [ ] Use HTTPS (Let's Encrypt SSL certificates)
- [ ] Change default secret key to a strong random value
- [ ] Restrict CORS origins: 
  ```python
  from flask_cors import CORS
  CORS(app, resources={"r/*": {"origins":"https://yourdomain.com"}})
  ```
- [ ] Add rate limiting (Flask-Limiter or similar):
  ```bash
  pip install Flask-Limiter
  # Then in app.py:
  from flask_limiter import Limiter
  limiter = Limiter(app, key_func=lambda: request.remote_addr)
  app.before_request(limiter.limit("10 per hour", "/api/*"))
  ```
- [ ] Add input sanitization for user content (XSS prevention)
- [ ] Implement password hashing if adding passwords
- [ ] Regular database backups and monitoring
- [ ] Set up error tracking (Sentry, Bugsnag, etc.)
- [ ] Review session timeout settings in production

---

## Monitoring & Logging Setup

### Add Logging Configuration:
```python
import logging
from flask import Flask

def setup_logging(app):
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    file_handler = logging.FileHandler(f'{log_dir}/notion-clone.log')
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

setup_logging(app)
```

---

## Backup Strategy for Production

### Automated Database Backups:
```bash
# Add to crontab (edit with: crontab -e)
0 2 * * * /usr/bin/mysqldump database.db | gzip > backups/db_backup_$(date +\%Y\%m\%d).sql.gz  # For MySQL/PostgreSQL
# Or for SQLite:
0 3 * * * cp /path/to/database.db /backups/db_backup_$(date +\%Y\%m\%d_%H%M%S).db
```

### Cloud Provider Backups:
- Railway: Automatic database backups enabled by default
- Render: Daily snapshots available in settings  
- Heroku: Add-on like "Heroku Postgres" includes automatic backups

---

## Scaling Considerations

If you expect high traffic or multiple users:
1. **Horizontal scaling**: Use application server (Gunicorn/uWSGI) with multiple workers behind Nginx
2. **Database read replicas**: If using PostgreSQL, set up read replicas for query offloading
3. **Cache layer**: Add Redis for session storage instead of Flask sessions in memory
4. **CDN**: Serve static assets via Cloudflare or similar CDN
5. **Externalize media**: Store cover images on S3/Cloudinary instead of SQLite BLOBs
6. **Database sharding/migration**: Consider PostgreSQL with partitioning if data grows large
7. **API rate limiting**: Prevent abuse from unauthenticated requests
8. **Monitoring tools**: Prometheus + Grafana for metrics, or New Relic/AWS X-Ray
9. **Health checks**: Add `/health` endpoint for load balancer monitoring:
   ```python
   @app.route('/health')
def health_check():
       return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
   ```
10. **Graceful shutdown handlers**:
    ```python
    import signal, os
    def handle_sigterm(signum, frame):
        print('Shutting down gracefully...')
        # Close database connections here if needed
        
    app.server.add_signal_handler(signal.SIGTERM, lambda: None)  # Or use gunicorn's built-in handling
    ```

---

## Migration Path to Production-Ready Architecture

### Phase 1 (Current State): Local Development ✅
- SQLite database
- Flask development server
- Email-only authentication
- Base64 image encoding in BLOBs

### Phase 2 (Small Scale / Hobby Project):
- PostgreSQL migration for better scalability
- External file storage for images (S3, Cloudinary)
- JWT token-based auth instead of sessions
- Rate limiting and CORS restrictions
- Error tracking with Sentry

### Phase 3 (Production Multi-User Application):
- User authentication system (password hashing + email verification)
- Role-based access control (RBAC) for permissions
- Database connection pooling
- Horizontal scaling with multiple app instances behind load balancer
- Comprehensive logging and monitoring stack
- Automated backup strategy and disaster recovery plan
- Security audits and penetration testing

---

## Useful Commands Reference

### Development:
```bash
# Start development server (current state)
python backend/app.py

# View database schema
sqlite3 database.db ".schema"

# Backup current database
cp database.db backup_$(date +%Y%m%d_%H%M%S).db
```

### Production Deployment:
```bash
# With Gunicorn (production WSGI server)
gunicorn -w 1 -b 0.0.0.0:5000 backend.app:app --timeout=60 --keep-alive=5

# Or with uWSGI
uwsgi --http :8000 --module backend.app:app --processes 4 --threads 2
```

### Docker:
```bash
docker build -t notion-clone .
docker run -d -p 5000:5000 --name notion-app notion-clone
# View logs
docker logs notion-app
# Restart container
docker restart notion-app
```

---

## Troubleshooting Deployment Issues

### "Database locked" error in production:
Ensure no other processes are accessing the SQLite file. For PostgreSQL migration, see Database Migration section above.

### Session timeout causing login issues:
Increase `SESSION_TIMEOUT` or implement JWT tokens with refresh mechanism.

### CORS errors from browser console:
Update Flask-CORS configuration to allow specific origins instead of all:
```python
CORS(app, resources={"r/*": {"origins":"https://yourdomain.com"}})
```

---

## Resources for Further Reading

- [Flask Deployment Guide](https://flask.palletsprojects.com/deploying/)
- [Railway Flask App Tutorial](https://railway.app/docs/flask)
- [Gunicorn Configuration Best Practices](http://docs.guniconfig.org/)
- [Nginx Reverse Proxy Setup](https://www.digitalocean.com/community/tutorials/how-to-set-up-a-reverse-proxy-with-nginx-on-ubuntu-20-04)

---

**Deployment complete!** 🚀 Your Notion Clone is now live and accessible!
