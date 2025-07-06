# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the BargainB system.

## Quick Diagnosis

### System Health Check

Run this command to get an overview of system status:

```bash
# Check all services
npm run health-check

# Or manually check each component
curl http://localhost:3000/api/health        # Frontend
curl http://localhost:8000/health           # Backend
curl https://your-project.supabase.co/rest/v1/  # Database
```

### Common Symptoms

| Symptom | Likely Cause | Quick Fix |
|---------|-------------|-----------|
| 404 on admin panel | Frontend not running | `npm run dev` |
| API timeout errors | Backend not responding | Check backend logs |
| Database connection errors | Supabase credentials issue | Verify `.env.local` |
| Scraping jobs stuck | Agent communication issue | Restart agent service |
| Slow page loads | Database performance | Check query performance |

## Frontend Issues

### Next.js Build Errors

**Error**: `Module not found: Can't resolve '@/components/...'`

**Solution**:
```bash
# Check tsconfig.json paths
cat tsconfig.json | grep paths

# Verify file exists
ls -la components/

# Clear Next.js cache
rm -rf .next
npm run build
```

**Error**: `Hydration failed because the initial UI does not match`

**Solution**:
```typescript
// Use dynamic imports for client-only components
import dynamic from 'next/dynamic';

const ClientOnlyComponent = dynamic(
  () => import('./ClientOnlyComponent'),
  { ssr: false }
);
```

### Supabase Connection Issues

**Error**: `Invalid API key` or `Project not found`

**Solution**:
```bash
# Verify environment variables
echo $NEXT_PUBLIC_SUPABASE_URL
echo $NEXT_PUBLIC_SUPABASE_ANON_KEY

# Check Supabase dashboard for correct keys
# Ensure no trailing spaces in .env.local
```

**Error**: `Row Level Security policy violation`

**Solution**:
```sql
-- Check RLS policies
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual 
FROM pg_policies 
WHERE schemaname = 'public';

-- Temporarily disable RLS for testing
ALTER TABLE your_table DISABLE ROW LEVEL SECURITY;
```

### Authentication Problems

**Error**: User login redirects to error page

**Solution**:
```typescript
// Check Supabase auth configuration
const { data, error } = await supabase.auth.getUser();
console.log('Auth error:', error);

// Verify redirect URLs in Supabase dashboard
// Development: http://localhost:3000/auth/callback
// Production: https://your-domain.com/auth/callback
```

## Backend Issues

### Python Import Errors

**Error**: `ModuleNotFoundError: No module named 'langgraph'`

**Solution**:
```bash
# Check Python version
python --version  # Should be 3.11+

# Verify virtual environment
which python
which pip

# Reinstall requirements
pip install -r requirements.txt

# Check installed packages
pip list | grep langgraph
```

### FastAPI Server Won't Start

**Error**: `Address already in use`

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000

# Kill process (replace PID)
kill -9 <PID>

# Or use different port
uvicorn main:app --port 8001
```

**Error**: `ModuleNotFoundError: No module named 'main'`

**Solution**:
```bash
# Ensure you're in the backend directory
cd backend

# Check main.py exists
ls -la main.py

# Run with full path
python -m main
```

### Database Connection Errors

**Error**: `connection to server ... failed`

**Solution**:
```bash
# Test Supabase connection
psql "postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"

# Check environment variables
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY

# Verify IP allowlist in Supabase dashboard
```

### Agent Communication Issues

**Error**: Agents not responding or stuck in processing

**Solution**:
```bash
# Check agent status
curl http://localhost:8000/api/agents/status

# Restart orchestrator
cd backend
python agents/orchestrator.py

# Check Redis connection (if using Redis)
redis-cli ping

# Clear stuck jobs
redis-cli flushall  # ⚠️ This clears all Redis data
```

## Database Issues

### Supabase Performance Problems

**Slow Queries**:
```sql
-- Enable pg_stat_statements
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Find slow queries
SELECT 
  query,
  calls,
  total_time,
  mean_time,
  rows
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

**Solution**:
```sql
-- Add missing indexes
CREATE INDEX CONCURRENTLY idx_products_name ON products(name);
CREATE INDEX CONCURRENTLY idx_prices_date ON price_history(scraped_at);

-- Analyze table statistics
ANALYZE products;
ANALYZE price_history;
```

### Connection Pool Exhaustion

**Error**: `remaining connection slots are reserved`

**Solution**:
```python
# Implement connection pooling
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)
```

### Migration Issues

**Error**: `relation "table_name" already exists`

**Solution**:
```bash
# Check migration status
supabase migration list

# Reset to specific migration
supabase db reset --linked

# Apply migrations manually
psql $DATABASE_URL -f migrations/001_initial.sql
```

## Scraping Issues

### Store Scraper Failures

**Error**: `HTTP 403 Forbidden` or `Access Denied`

**Solution**:
```python
# Rotate user agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
]

# Add delays between requests
await asyncio.sleep(random.uniform(1, 3))

# Use proxy rotation
PROXIES = ['proxy1:port', 'proxy2:port']
```

**Error**: `HTML structure changed` or parsing errors

**Solution**:
```python
# Add robust error handling
try:
    price_element = soup.find('span', class_='price')
    if not price_element:
        # Try alternative selectors
        price_element = soup.find('div', {'data-testid': 'price'})
    
    price = float(price_element.text.replace('€', '').replace(',', '.'))
except (AttributeError, ValueError) as e:
    logger.warning(f"Could not parse price: {e}")
    price = None
```

### Rate Limiting Issues

**Error**: `429 Too Many Requests`

**Solution**:
```python
# Implement exponential backoff
import time
import random

async def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError:
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(wait_time)
    
    raise Exception("Max retries exceeded")
```

### Data Quality Issues

**Error**: Duplicate products or incorrect categorization

**Solution**:
```python
# Implement data validation
def validate_product_data(product):
    errors = []
    
    if not product.get('name') or len(product['name']) < 3:
        errors.append("Product name too short")
    
    if product.get('price', 0) <= 0:
        errors.append("Invalid price")
    
    if not product.get('category'):
        errors.append("Missing category")
    
    return errors

# Clean and normalize data
def normalize_product_name(name):
    # Remove extra whitespace, convert to lowercase
    normalized = ' '.join(name.split()).lower()
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'^(ah|jumbo|dirk)\s+', '', normalized)
    
    return normalized
```

## Performance Issues

### High Memory Usage

**Symptoms**: System becomes slow or crashes

**Diagnosis**:
```bash
# Check memory usage
free -h
htop

# Python memory profiling
pip install memory-profiler
python -m memory_profiler your_script.py
```

**Solution**:
```python
# Process data in chunks
def process_products_in_batches(products, batch_size=100):
    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        yield batch

# Clear unused variables
import gc

def cleanup_memory():
    gc.collect()
    
# Use generators instead of lists
def get_products():
    for product in query_products():
        yield process_product(product)
```

### High CPU Usage

**Symptoms**: Slow response times, high load average

**Diagnosis**:
```bash
# Check CPU usage
top -p $(pgrep python)

# Profile Python code
pip install py-spy
py-spy record -o profile.svg -d 60 -p <PID>
```

**Solution**:
```python
# Use asyncio for I/O bound tasks
import asyncio
import aiohttp

async def scrape_multiple_stores(stores):
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_store(session, store) for store in stores]
        results = await asyncio.gather(*tasks)
    return results

# Optimize database queries
# Use bulk operations instead of individual inserts
products = [Product(name=name, price=price) for name, price in data]
session.bulk_insert_mappings(Product, products)
```

## Monitoring and Alerting

### Setting Up Monitoring

**Application Monitoring**:
```python
# Add health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Test database connection
        db_status = await test_db_connection()
        
        # Test Redis connection
        redis_status = await test_redis_connection()
        
        return {
            "status": "healthy" if db_status and redis_status else "unhealthy",
            "database": "ok" if db_status else "error",
            "redis": "ok" if redis_status else "error",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

**Log Monitoring**:
```python
import structlog

logger = structlog.get_logger()

# Structured logging
logger.info(
    "Scraping completed",
    store="albert_heijn",
    products_processed=1500,
    duration=120.5,
    success_rate=0.98
)
```

### Custom Alerts

**Email Alerts**:
```python
import smtplib
from email.mime.text import MIMEText

async def send_alert(subject, message):
    msg = MIMEText(message)
    msg['Subject'] = f"BargainB Alert: {subject}"
    msg['From'] = "alerts@bargainb.nl"
    msg['To'] = "admin@bargainb.nl"
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
```

**Slack Notifications**:
```python
import aiohttp

async def send_slack_alert(message):
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    
    payload = {
        "text": message,
        "channel": "#bargainb-alerts",
        "username": "BargainB Bot"
    }
    
    async with aiohttp.ClientSession() as session:
        await session.post(webhook_url, json=payload)
```

## Production Issues

### High Load Scenarios

**Symptoms**: Timeouts, 5xx errors, slow responses

**Immediate Actions**:
```bash
# Scale up backend (Railway)
railway scale --replicas 3

# Check resource usage
railway logs --tail

# Enable caching
redis-cli config set maxmemory 256mb
redis-cli config set maxmemory-policy allkeys-lru
```

**Long-term Solutions**:
- Implement API rate limiting
- Add database read replicas
- Use CDN for static assets
- Optimize database queries
- Implement background job processing

### Data Inconsistency

**Symptoms**: Price discrepancies, missing products

**Investigation**:
```sql
-- Check for data inconsistencies
SELECT 
    p.name,
    COUNT(DISTINCT cp.price) as price_variations,
    MAX(cp.last_updated) as last_update
FROM products p
JOIN store_products sp ON p.id = sp.product_id
JOIN current_prices cp ON sp.id = cp.store_product_id
GROUP BY p.id, p.name
HAVING COUNT(DISTINCT cp.price) > 3;
```

**Resolution**:
```python
# Data validation and correction
async def validate_and_correct_prices():
    inconsistent_products = await find_inconsistent_products()
    
    for product in inconsistent_products:
        # Re-scrape from all stores
        fresh_data = await scrape_product_from_all_stores(product.id)
        
        # Update database with fresh data
        await update_product_prices(product.id, fresh_data)
        
        # Log correction
        logger.info("Corrected price data", product_id=product.id)
```

## Getting Help

### Debug Information to Collect

When reporting issues, include:

1. **System Information**:
```bash
# Environment details
node --version
python --version
npm list --depth=0

# System resources
free -h
df -h
```

2. **Application Logs**:
```bash
# Frontend logs
npm run dev 2>&1 | tee frontend.log

# Backend logs
cd backend
python main.py 2>&1 | tee backend.log
```

3. **Database State**:
```sql
-- Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Support Channels

- **Documentation**: Check relevant docs in `/docs` folder
- **GitHub Issues**: [Create an issue](https://github.com/your-username/bargainb-admin/issues)
- **Discord**: [BargainB Community](https://discord.gg/bargainb)
- **Email**: support@bargainb.nl

### Emergency Procedures

**System Down**:
1. Check all services are running
2. Verify database connectivity
3. Check for recent deployments
4. Rollback if necessary
5. Notify stakeholders

**Data Loss**:
1. Stop all write operations
2. Assess scope of data loss
3. Restore from latest backup
4. Verify data integrity
5. Resume operations

**Security Incident**:
1. Isolate affected systems
2. Change all API keys and passwords
3. Review access logs
4. Apply security patches
5. Conduct post-incident review 