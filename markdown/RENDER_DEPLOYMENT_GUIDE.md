# Deploy School ERP Backend to Render

## 📋 Prerequisites

- [ ] Render account (free at https://render.com)
- [ ] GitHub repository with your code
- [ ] PostgreSQL database (can use Render's)
- [ ] Redis instance (can use Render's)

---

## 🚀 Step-by-Step Deployment

### Step 1: Prepare Your Repository

Push your code to GitHub with the latest optimizations:

```bash
git add .
git commit -m "Performance optimizations: connection pooling, Redis caching, indexes"
git push origin main
```

**Required files in repo:**
```
backend/
├── requirements.txt          (includes redis, aioredis)
├── server.py
├── database.py
├── auth.py
├── config.py
├── middleware.py
├── create_indexes.py
├── Procfile                  (NEW - for Render)
├── render.yaml              (NEW - for Render)
└── routers/
    ├── ...
    └── all your routers
```

### Step 2: Create Procfile

Create `Procfile` in your repo root:

```
web: cd backend && gunicorn server:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120 --workers 4
```

Or for better async support:

```
web: cd backend && uvicorn server:app --host 0.0.0.0 --port $PORT --workers 4
```

### Step 3: Update requirements.txt

Add Render-specific dependencies:

```bash
# In backend/requirements.txt, add these at the end:
gunicorn==21.2.0
uvicorn[standard]==0.27.0
```

### Step 4: Create render.yaml

Create `render.yaml` in your repo root:

```yaml
services:
  - type: web
    name: school-erp-backend
    env: python
    plan: standard
    buildCommand: cd backend && pip install -r requirements.txt && python create_indexes.py
    startCommand: cd backend && gunicorn server:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120
    envVars:
      - key: PYTHON_VERSION
        value: 3.11
      - key: DATABASE_URL
        fromDatabase:
          name: school-erp-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: school-erp-redis
          type: redis
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: ALLOWED_HOSTS
        value: "localhost,127.0.0.1,*.onrender.com"
    
  - type: pserv
    name: school-erp-redis
    plan: free
    ipAllowList: []
    
  - type: pserv
    name: school-erp-db
    plan: starter
    dbName: school_erp
    user: postgres
    ipAllowList: []
```

### Step 5: Update Config for Render

Update `backend/config.py` to support Render's environment:

```python
"""Application configuration loaded from environment variables"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os


class Settings(BaseSettings):
    """Application configuration"""
    
    # Database - PostgreSQL (Render provides via DATABASE_URL)
    database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/school_erp")
    ALLOWED_HOSTS: list[str] = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    
    # Redis URL (Render provides via REDIS_URL)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # JWT
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    
    # Resend Email
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from_email: str = os.getenv("RESEND_FROM_EMAIL", "noreply@schoolerp.com")
    resend_from_name: str = os.getenv("RESEND_FROM_NAME", "School ERP")
    
    # ... rest of settings
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### Step 6: Update Auth for Render Redis

Update `backend/auth.py` to use REDIS_URL from config:

```python
import os

async def get_redis() -> redis.Redis:
    """Get or create Redis client"""
    global _redis_client
    if _redis_client is None:
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            
            # Try to connect to Redis
            _redis_client = await redis.from_url(
                redis_url,
                encoding="utf8",
                decode_responses=True,
                socket_connect_timeout=5
            )
            await _redis_client.ping()
            logger.info("✓ Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"⚠ Redis cache unavailable ({e}), falling back to database queries")
            _redis_client = None
    return _redis_client
```

### Step 7: Update Database for Render

Update `backend/database.py` to use DATABASE_URL from Render:

```python
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Fix DATABASE_URL for asyncpg if necessary
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

logger.info(f"Connecting to database...")

async_engine = create_async_engine(
    database_url,
    echo=False,
    poolclass=QueuePool,
    pool_size=5,               # Lower for free tier (Render limits connections)
    max_overflow=3,            # Lower overflow
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "timeout": 30,
        "command_timeout": 60,
        "server_settings": {
            "application_name": "school_erp_app",
            "jit": "off",
        }
    } 
)
```

---

## 🔗 Deploy via Render Dashboard

### Method 1: One-Click Deploy with render.yaml

1. Go to https://dashboard.render.com/new
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Paste your repo URL
5. Click "Create" (Render will use render.yaml)
6. Wait for deployment (5-10 minutes)

### Method 2: Manual Web Service Setup

1. Go to https://dashboard.render.com/new
2. Click "Web Service"
3. Connect your GitHub repository
4. Configure:

```
Service Name:           school-erp-backend
Environment:            Python 3.11
Build Command:          cd backend && pip install -r requirements.txt
Start Command:          cd backend && gunicorn server:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
Plan:                   Starter ($7/month)
```

5. Add Environment Variables:

```
DATABASE_URL        = (from PostgreSQL service)
REDIS_URL          = (from Redis service)
SECRET_KEY         = (generate random 32-char string)
ALLOWED_HOSTS      = localhost,127.0.0.1,school-erp-backend.onrender.com
RESEND_API_KEY     = (your Resend API key)
RESEND_FROM_EMAIL  = (your email)
```

6. Click "Create Web Service"

### Method 3: PostgreSQL Service

1. Go to https://dashboard.render.com/new
2. Click "PostgreSQL"
3. Configure:

```
Name:               school-erp-db
Database:           school_erp
User:               postgres
Plan:               Starter ($15/month)
```

4. Save the connection string for Environment Variables

### Method 4: Redis Service

1. Go to https://dashboard.render.com/new
2. Click "Redis"
3. Configure:

```
Name:               school-erp-redis
Plan:               Free ($0/month)
Max memory policy:  allkeys-lru
```

4. Save the connection string for Environment Variables

---

## 🔧 Post-Deployment Setup

### 1. Run Database Migrations (if needed)

In Render dashboard for your web service:

1. Go to "Shell" tab
2. Run:

```bash
cd backend
python migrate.py
python create_indexes.py
```

### 2. Test the Deployment

```bash
# Test health endpoint
curl https://school-erp-backend.onrender.com/api/health

# Test with authentication
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://school-erp-backend.onrender.com/api/dashboard/overview
```

### 3. Monitor Logs

In Render dashboard:

1. Click your service name
2. Go to "Logs" tab
3. Watch for errors during startup

Expected logs:
```
🚀 Starting School ERP System...
✓ Redis cache initialized successfully
✓ All routers loaded successfully
✅ Application started successfully
```

---

## 🛠️ Environment Variables Reference

| Variable | Value | Required |
|----------|-------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `SECRET_KEY` | Random 32+ character string | Yes |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,*.onrender.com` | Yes |
| `RESEND_API_KEY` | Your Resend API key | Yes |
| `RESEND_FROM_EMAIL` | Your email address | Yes |
| `USMS_TOKEN` | USMS token (optional) | No |
| `TWILIO_ACCOUNT_SID` | Twilio SID (optional) | No |
| `TWILIO_AUTH_TOKEN` | Twilio token (optional) | No |

---

## 📊 Render Configuration Summary

### For Development:
```
Web Service Plan: Free ($0, sleeps after 15 min idle)
PostgreSQL Plan: Starter ($15/month)
Redis Plan: Free ($0)
Total: $15/month
```

### For Production:
```
Web Service Plan: Standard ($7/month, always running)
PostgreSQL Plan: Standard ($20/month, 100 connections)
Redis Plan: Free or Starter ($7-15/month, 25GB)
Total: $27-45/month
```

---

## ⚠️ Common Issues & Solutions

### Issue: "DatabaseConnectivity Error"

**Cause:** DATABASE_URL not set or invalid

**Solution:**
1. Get URL from PostgreSQL service in Render dashboard
2. Set as environment variable
3. Test with: `psql "your-database-url"`

### Issue: "Redis connection refused"

**Cause:** REDIS_URL not set or Redis service not created

**Solution:**
1. Create Redis service in Render
2. Copy connection string
3. Set as REDIS_URL environment variable
4. App will fallback to database if Redis unavailable

### Issue: "PermissionError: Can't create file indexes.db"

**Cause:** Trying to create SQLite in Render (read-only filesystem)

**Solution:** Make sure you're using PostgreSQL, not SQLite

### Issue: "413 Payload Too Large"

**Cause:** Request body too large

**Solution:** Increase in Render settings (usually not needed)

### Issue: Slow initial response (timeout)

**Cause:** First request triggers cold start

**Solution:** Use "Keep-Alive" or upgrade to Standard plan

---

## 🚀 Optimization for Render

### Connection Pool Tuning for Render Free Tier:

```python
# database.py - For free tier (limited connections)
pool_size=5,               # Very limited on free tier
max_overflow=2,
pool_recycle=1800,         # Recycle every 30 min
```

### For Production Render Plan:

```python
# database.py - For standard tier
pool_size=10,              # More connections available
max_overflow=5,
pool_recycle=3600,
```

---

## 📝 Complete Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] `Procfile` created in repo root
- [ ] `render.yaml` created (optional but recommended)
- [ ] `requirements.txt` updated with redis, aioredis, gunicorn
- [ ] `config.py` reads REDIS_URL, DATABASE_URL from env
- [ ] `auth.py` updated to use REDIS_URL
- [ ] `database.py` updated to use DATABASE_URL
- [ ] PostgreSQL service created in Render
- [ ] Redis service created in Render
- [ ] Web service created with correct Start Command
- [ ] Environment variables set in Render dashboard
- [ ] Deployment successful (check logs)
- [ ] Health endpoint responds: `curl https://your-service.onrender.com/api/health`
- [ ] Database indexes created: `python create_indexes.py` (run in Shell)
- [ ] Test authentication endpoint

---

## 🔒 Production Security Checklist

- [ ] `SECRET_KEY` is 32+ random characters (NOT "dev-secret")
- [ ] `ALLOWED_HOSTS` set to actual domain
- [ ] CORS configured for your frontend domain
- [ ] Database credentials not in code (using env vars)
- [ ] Redis URL not in code (using env vars)
- [ ] API keys not in code (using env vars)
- [ ] HTTPS enforced (Render provides free SSL)
- [ ] Database backups enabled
- [ ] Monitoring/alerting configured

---

## 💰 Cost Estimate (Render)

| Service | Plan | Cost |
|---------|------|------|
| Web Backend | Starter | $7/mo |
| PostgreSQL | Starter | $15/mo |
| Redis | Free | $0/mo |
| **Total** | | **$22/mo** |

*All services have free trial available*

---

## 📚 Useful Render Resources

- Render Docs: https://render.com/docs
- Python Support: https://render.com/docs/deploy-python
- PostgreSQL: https://render.com/docs/databases
- Redis: https://render.com/docs/redis
- Environment Variables: https://render.com/docs/environment-variables
- Troubleshooting: https://render.com/docs/troubleshooting

---

## 🎯 After Deployment

### 1. Set Up Custom Domain
- Go to Service Settings → Custom Domain
- Add your domain (e.g., `api.schoolerp.com`)
- Update DNS records per Render instructions

### 2. Enable Auto-Deploy
- Go to Settings → GitHub
- Enable "Auto-deploy" for automatic updates on push

### 3. Monitor Performance
- Check Render dashboard for CPU/memory usage
- Monitor response times in logs
- Set up error alerting

### 4. Scale if Needed
- Upgrade to Standard plan if high traffic
- Add more PostgreSQL connections
- Upgrade Redis memory

---

**Your backend is now deployed on Render! 🎉**

**Dashboard:** https://dashboard.render.com  
**Your API:** https://school-erp-backend.onrender.com/api  
**Docs:** https://school-erp-backend.onrender.com/api/docs
