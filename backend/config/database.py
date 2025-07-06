"""
Database configuration and connection management
"""

from typing import AsyncGenerator, Optional
import logging
from database.client import get_database, initialize_database, SupabaseClient
from .settings import settings

logger = logging.getLogger(__name__)

# Global database client
_db_client: Optional[SupabaseClient] = None

async def init_db():
    """Initialize database connections."""
    global _db_client
    
    try:
        logger.info("🔄 Initializing database connections...")
        
        # Initialize the database client
        success = await initialize_database()
        
        if success:
            _db_client = await get_database()
            logger.info("✅ Database initialization completed successfully")
        else:
            logger.error("❌ Database initialization failed")
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

async def get_db() -> SupabaseClient:
    """Get database client instance."""
    global _db_client
    
    if _db_client is None:
        await init_db()
    
    return _db_client

async def close_db():
    """Close database connections."""
    global _db_client
    
    if _db_client:
        logger.info("🔄 Closing database connections...")
        _db_client = None
        logger.info("✅ Database connections closed")

# Database dependency for FastAPI
async def get_db_dependency() -> AsyncGenerator[SupabaseClient, None]:
    """Database dependency for FastAPI endpoints."""
    db = await get_db()
    try:
        yield db
    finally:
        # Connection is managed by the client, no need to close
        pass

# Health check function
async def check_db_health():
    """Check database health."""
    try:
        db = await get_db()
        health_result = await db.health_check()
        return health_result
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": None
        }

# Database manager for backward compatibility
class DatabaseManager:
    """Database manager class for common operations."""
    
    def __init__(self):
        self._client = None
    
    async def get_client(self) -> SupabaseClient:
        """Get database client."""
        if self._client is None:
            self._client = await get_db()
        return self._client
    
    async def get_stores(self) -> list:
        """Get all active stores."""
        client = await self.get_client()
        return await client.get_stores()
    
    async def get_store_by_slug(self, slug: str) -> dict:
        """Get store by slug."""
        client = await self.get_client()
        return await client.get_store_by_slug(slug)
    
    async def get_categories(self) -> list:
        """Get all categories."""
        client = await self.get_client()
        return await client.get_categories()
    
    async def get_products_count(self) -> int:
        """Get total products count."""
        client = await self.get_client()
        return await client.get_products_count()
    
    async def get_recent_scraping_jobs(self, limit: int = 10) -> list:
        """Get recent scraping jobs."""
        client = await self.get_client()
        return await client.get_recent_jobs(limit)
    
    async def create_scraping_job(self, store_id: str, job_type: str) -> dict:
        """Create a new scraping job."""
        client = await self.get_client()
        return await client.create_scraping_job(store_id, job_type)
    
    async def update_scraping_job(self, job_id: str, **kwargs) -> dict:
        """Update scraping job status and details."""
        client = await self.get_client()
        return await client.update_job_status(job_id, **kwargs)
    
    async def log_system_event(self, level: str, message: str, component: str = None, 
                             store_id: str = None, job_id: str = None, metadata: dict = None):
        """Log system event."""
        client = await self.get_client()
        return await client.log_system_event(level, message, component, store_id, job_id, metadata)

# Global database manager instance
db_manager = DatabaseManager() 