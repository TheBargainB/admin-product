# Deployment Guide

This guide covers deploying BargainB to various environments, from local development to production.

## Overview

BargainB consists of three main components:
- **Frontend**: Next.js application (React-based admin panel)
- **Backend**: Python/FastAPI with LangGraph agents
- **Database**: Supabase (managed PostgreSQL)

## Development Environment

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- Python 3.11+ with pip
- Git
- Supabase account

### Local Setup

1. **Clone and Setup**
```bash
git clone https://github.com/your-username/bargainb-admin.git
cd bargainb-admin

# Copy environment template
cp .env.example .env.local
```

2. **Configure Environment Variables**

Edit `.env.local`:
```env
# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Backend Configuration
BACKEND_URL=http://localhost:8000
PYTHON_ENV=development

# Agent Configuration
OPENAI_API_KEY=your-openai-key
LANGGRAPH_API_KEY=your-langgraph-key

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/bargainb
REDIS_URL=redis://localhost:6379
```

3. **Install Dependencies**
```bash
# Frontend
npm install

# Backend
cd backend
pip install -r requirements.txt
cd ..
```

4. **Setup Database**
```bash
# Initialize Supabase schema
npm run db:setup

# Run migrations
npm run db:migrate

# Seed initial data
npm run db:seed
```

5. **Start Development Servers**
```bash
# Terminal 1: Frontend
npm run dev

# Terminal 2: Backend
cd backend
python main.py

# Terminal 3: Agent system (optional)
cd backend
python agents/orchestrator.py
```

### Development Scripts

```bash
# Database operations
npm run db:reset          # Reset database schema
npm run db:types          # Generate TypeScript types
npm run db:migrate        # Run migrations
npm run db:seed           # Seed test data

# Code quality
npm run lint              # Lint frontend code
npm run test              # Run tests
npm run type-check        # TypeScript type checking

# Backend operations
cd backend
python -m pytest         # Run Python tests
black .                   # Format Python code
flake8 .                  # Lint Python code
```

## Production Deployment

### Architecture Overview

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Vercel    │    │   Railway    │    │  Supabase   │
│  (Frontend) │────│  (Backend)   │────│ (Database)  │
│             │    │              │    │             │
└─────────────┘    └──────────────┘    └─────────────┘
```

### Frontend Deployment (Vercel)

1. **Connect Repository**
```bash
# Install Vercel CLI
npm install -g vercel

# Login and deploy
vercel login
vercel --prod
```

2. **Environment Variables**

In Vercel dashboard, set:
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
BACKEND_URL=https://your-backend.railway.app
```

3. **Build Configuration**

`vercel.json`:
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "installCommand": "npm install",
  "functions": {
    "app/api/**/*.ts": {
      "maxDuration": 30
    }
  },
  "rewrites": [
    {
      "source": "/api/backend/:path*",
      "destination": "https://your-backend.railway.app/api/:path*"
    }
  ]
}
```

### Backend Deployment (Railway)

1. **Create Railway Project**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and create project
railway login
railway init
```

2. **Docker Configuration**

`Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. **Environment Variables**

In Railway dashboard:
```env
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-key
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis
REDIS_URL=redis://user:pass@host:port

# API Keys
OPENAI_API_KEY=your-openai-key
LANGGRAPH_API_KEY=your-langgraph-key

# Environment
PYTHON_ENV=production
PORT=8000
```

4. **Deploy**
```bash
# Deploy to Railway
railway up

# Check deployment status
railway status

# View logs
railway logs
```

### Database Setup (Supabase)

1. **Create Production Project**
- Go to [Supabase Dashboard](https://app.supabase.com)
- Create new project
- Wait for initialization (2-3 minutes)

2. **Run Migrations**
```bash
# Install Supabase CLI
npm install -g supabase

# Login
supabase login

# Link project
supabase link --project-ref your-project-ref

# Push schema
supabase db push

# Seed production data
supabase db reset --linked
```

3. **Configure Security**

Enable Row Level Security:
```sql
-- Enable RLS on all tables
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE current_prices ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Public read access" ON stores FOR SELECT USING (true);
CREATE POLICY "Admin full access" ON stores FOR ALL USING (auth.jwt() ->> 'role' = 'admin');
```

4. **Setup Backups**
- Enable automatic backups in Supabase dashboard
- Configure backup retention (7 days recommended)
- Set up backup monitoring

### Monitoring and Logging

1. **Application Monitoring**

`backend/monitoring.py`:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# Initialize Sentry
sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FastApiIntegration()],
    traces_sample_rate=1.0,
    environment="production"
)
```

2. **Health Checks**

`backend/health.py`:
```python
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }
```

3. **Logging Configuration**

`backend/logging_config.py`:
```python
import logging
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### SSL and Security

1. **HTTPS Configuration**
- Vercel provides automatic HTTPS
- Railway provides automatic HTTPS
- Custom domains require SSL certificates

2. **CORS Configuration**

`backend/main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

3. **API Security**
```python
from fastapi.security import HTTPBearer
from fastapi import Depends, HTTPException

security = HTTPBearer()

async def verify_token(token: str = Depends(security)):
    # Verify JWT token with Supabase
    # Raise HTTPException if invalid
    pass
```

### Performance Optimization

1. **Caching Strategy**
```python
import redis
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

# Initialize Redis caching
redis_client = redis.from_url("redis://localhost:6379")
FastAPICache.init(RedisBackend(redis_client), prefix="bargainb")
```

2. **Database Optimization**
```sql
-- Add indexes for performance
CREATE INDEX CONCURRENTLY idx_products_search ON products USING gin(to_tsvector('english', name));
CREATE INDEX CONCURRENTLY idx_prices_date ON price_history(scraped_at);
CREATE INDEX CONCURRENTLY idx_store_products_lookup ON store_products(store_id, product_id);
```

3. **Frontend Optimization**
```typescript
// Next.js configuration
const nextConfig = {
  experimental: {
    appDir: true,
  },
  images: {
    domains: ['your-cdn-domain.com'],
  },
  compression: true,
  poweredByHeader: false,
}
```

## CI/CD Pipeline

### GitHub Actions

`.github/workflows/deploy.yml`:
```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run test
      - run: npm run lint

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.ORG_ID }}
          vercel-project-id: ${{ secrets.PROJECT_ID }}
          vercel-args: '--prod'

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: railway-app/railway-deploy@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN }}
          service: 'backend'
```

## Scaling Considerations

### Horizontal Scaling

1. **Backend Scaling**
- Railway auto-scaling based on CPU/memory
- Multiple worker processes with gunicorn
- Load balancing with Railway's built-in LB

2. **Database Scaling**
- Supabase auto-scaling
- Read replicas for heavy read workloads
- Connection pooling with PgBouncer

3. **Caching Strategy**
- Redis for session caching
- CDN for static assets
- Application-level caching for API responses

### Performance Monitoring

1. **Metrics to Track**
- Response times
- Error rates
- Database query performance
- Scraping job success rates
- System resource usage

2. **Alerting Setup**
- Sentry for error monitoring
- Uptime monitoring with Railway
- Custom alerts for business metrics

## Disaster Recovery

### Backup Strategy

1. **Database Backups**
- Automated daily backups via Supabase
- Point-in-time recovery capability
- Cross-region backup replication

2. **Application Backups**
- Git repository as source of truth
- Docker images stored in registry
- Configuration backed up in secure storage

### Recovery Procedures

1. **Database Recovery**
```bash
# Restore from backup
supabase db reset --restore-from backup-20240115

# Verify data integrity
npm run db:validate
```

2. **Application Recovery**
```bash
# Redeploy from last known good commit
git checkout last-known-good
railway up
vercel --prod
```

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
```bash
# Check Supabase status
curl https://your-project.supabase.co/rest/v1/

# Verify connection string
psql $DATABASE_URL -c "SELECT 1"
```

2. **Agent Communication Issues**
```bash
# Check Redis connectivity
redis-cli ping

# Verify agent health
curl http://localhost:8000/agents/health
```

3. **Frontend Build Issues**
```bash
# Clear Next.js cache
rm -rf .next

# Rebuild
npm run build
```

### Performance Issues

1. **Slow API Responses**
```sql
-- Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

2. **High Memory Usage**
```bash
# Monitor Python processes
ps aux | grep python

# Check memory usage
free -h
```

For more detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md). 