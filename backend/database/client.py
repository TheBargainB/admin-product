"""
Supabase Database Client
Handles connection management and provides database operations
"""

from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from config.settings import settings
import logging
import asyncio
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Supabase client wrapper with enhanced functionality."""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the Supabase client."""
        try:
            if self._initialized:
                return True
                
            # Create Supabase client
            self._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY
            )
            
            # Test connection
            await self.health_check()
            self._initialized = True
            logger.info("Supabase client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database connection health."""
        try:
            if not self._client:
                return {"status": "error", "message": "Client not initialized"}
            
            # Simple health check - try to query a system table
            start_time = datetime.now()
            result = self._client.table("stores").select("id").limit(1).execute()
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "timestamp": datetime.now().isoformat(),
                "supabase_url": settings.SUPABASE_URL
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "error", 
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_stores(self) -> List[Dict[str, Any]]:
        """Get all active stores."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("stores")\
                .select("*")\
                .eq("is_active", True)\
                .order("name")\
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get stores: {e}")
            return []
    
    async def get_store_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get store by slug."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("stores")\
                .select("*")\
                .eq("slug", slug)\
                .eq("is_active", True)\
                .single()\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get store by slug {slug}: {e}")
            return None
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("categories")\
                .select("*")\
                .order("name")\
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return []
    
    async def get_products_count(self) -> int:
        """Get total products count."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("products")\
                .select("id", count="exact")\
                .execute()
            
            return result.count or 0
            
        except Exception as e:
            logger.error(f"Failed to get products count: {e}")
            return 0
    
    async def get_current_prices_count(self) -> int:
        """Get current prices count."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("current_prices")\
                .select("id", count="exact")\
                .execute()
            
            return result.count or 0
            
        except Exception as e:
            logger.error(f"Failed to get current prices count: {e}")
            return 0
    
    async def get_today_price_updates(self) -> int:
        """Get today's price updates count."""
        try:
            if not self._client:
                await self.initialize()
            
            today = datetime.now().date()
            result = self._client.table("current_prices")\
                .select("id", count="exact")\
                .gte("last_updated", today.isoformat())\
                .execute()
            
            return result.count or 0
            
        except Exception as e:
            logger.error(f"Failed to get today's price updates: {e}")
            return 0
    
    async def create_scraping_job(self, store_id: str, job_type: str, metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Create a new scraping job."""
        try:
            if not self._client:
                await self.initialize()
            
            job_data = {
                "store_id": store_id,
                "job_type": job_type,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            
            # Store metadata in error_details field as JSONB (reusing existing column)
            if metadata:
                job_data["error_details"] = metadata
            
            result = self._client.table("scraping_jobs")\
                .insert(job_data)\
                .execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to create scraping job: {e}")
            return None
    
    async def update_job_status(self, job_id: str, status: str, 
                              products_processed: int = None,
                              products_updated: int = None,
                              errors_count: int = None,
                              error_details: Dict[str, Any] = None) -> bool:
        """Update job status and metadata."""
        try:
            if not self._client:
                await self.initialize()
            
            update_data = {
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            
            if products_processed is not None:
                update_data["products_processed"] = products_processed
            if products_updated is not None:
                update_data["products_updated"] = products_updated
            if errors_count is not None:
                update_data["errors_count"] = errors_count
            if error_details:
                update_data["error_details"] = error_details
            
            if status == "completed":
                update_data["completed_at"] = datetime.now().isoformat()
            elif status == "running":
                update_data["started_at"] = datetime.now().isoformat()
            
            result = self._client.table("scraping_jobs")\
                .update(update_data)\
                .eq("id", job_id)\
                .execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False
    
    async def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get all active scraping jobs."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("scraping_jobs")\
                .select("*, stores(name, slug)")\
                .in_("status", ["pending", "running"])\
                .order("created_at", desc=True)\
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get active jobs: {e}")
            return []
    
    async def get_recent_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scraping jobs."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("scraping_jobs")\
                .select("*, stores(name, slug)")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get recent jobs: {e}")
            return []
    
    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        try:
            if not self._client:
                await self.initialize()
            
            result = self._client.table("scraping_jobs")\
                .select("*, stores(name, slug)")\
                .eq("id", job_id)\
                .single()\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get job by ID {job_id}: {e}")
            return None
    
    async def save_product(self, name: str, brand: str = None, category: str = None, 
                          unit_size: float = None, unit_type: str = None, description: str = None, 
                          image_url: str = None, external_id: str = None) -> Optional[str]:
        """Save a single product and return its ID."""
        try:
            if not self._client:
                await self.initialize()
            
            # First check if product exists by name and brand (upsert behavior)
            query = self._client.table("products")\
                .select("id")\
                .eq("normalized_name", name.lower())
            
            if brand:
                query = query.eq("brand", brand)
            else:
                query = query.is_("brand", "null")
            
            existing = query.execute()
            
            if existing.data:
                # Product exists, return its ID
                return existing.data[0]["id"]
            
            # Create new product
            product_data = {
                "name": name,
                "normalized_name": name.lower(),
                "brand": brand,
                "unit_size": unit_size,
                "unit_type": unit_type,
                "description": description,
                "image_url": image_url,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self._client.table("products")\
                .insert(product_data)\
                .execute()
            
            return result.data[0]["id"] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to save product {name}: {e}")
            return None
    
    async def save_store_product(self, store_id: str, product_id: str, 
                               store_product_id: str = None, store_url: str = None) -> bool:
        """Link a product to a store."""
        try:
            if not self._client:
                await self.initialize()
            
            # Check if link already exists
            existing = self._client.table("store_products")\
                .select("id")\
                .eq("store_id", store_id)\
                .eq("product_id", product_id)\
                .execute()
            
            if existing.data:
                # Already linked
                return True
            
            # Create new link
            link_data = {
                "store_id": store_id,
                "product_id": product_id,
                "store_product_id": store_product_id,
                "store_url": store_url,
                "is_available": True,
                "last_seen": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            }
            
            result = self._client.table("store_products")\
                .insert(link_data)\
                .execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Failed to save store product link: {e}")
            return False
    
    async def save_current_price(self, store_id: str, product_id: str, price: float,
                               original_price: float = None, discount_percentage: float = None,
                               is_promotion: bool = False, promotion_text: str = None) -> bool:
        """Save current price for a product."""
        try:
            if not self._client:
                await self.initialize()
            
            # First get store_product_id
            store_product = self._client.table("store_products")\
                .select("id")\
                .eq("store_id", store_id)\
                .eq("product_id", product_id)\
                .execute()
            
            if not store_product.data:
                logger.error(f"Store product link not found for store {store_id} and product {product_id}")
                return False
            
            store_product_id = store_product.data[0]["id"]
            
            # Prepare price data
            price_data = {
                "store_product_id": store_product_id,
                "price": price,
                "original_price": original_price,
                "discount_percentage": discount_percentage,
                "is_promotion": is_promotion,
                "promotion_text": promotion_text,
                "last_updated": datetime.now().isoformat()
            }
            
            # Upsert price (insert or update)
            result = self._client.table("current_prices")\
                .upsert(price_data)\
                .execute()
            
            # Also save to price history
            history_data = {
                "store_product_id": store_product_id,
                "price": price,
                "original_price": original_price,
                "discount_percentage": discount_percentage,
                "is_promotion": is_promotion,
                "promotion_text": promotion_text,
                "scraped_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            }
            
            self._client.table("price_history")\
                .insert(history_data)\
                .execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Failed to save current price: {e}")
            return False

    async def save_products(self, products: List[Dict[str, Any]], store_id: str) -> int:
        """Save products to database."""
        try:
            if not self._client or not products:
                return 0
            
            # Process products in batches to avoid overwhelming the database
            batch_size = 100
            total_saved = 0
            
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]
                
                # Prepare product data
                processed_batch = []
                for product in batch:
                    product_data = {
                        "name": product.get("name", ""),
                        "normalized_name": product.get("name", "").lower(),
                        "brand": product.get("brand"),
                        "category_id": product.get("category_id"),
                        "barcode": product.get("barcode"),
                        "unit_type": product.get("unit_type"),
                        "unit_size": product.get("unit_size"),
                        "description": product.get("description"),
                        "image_url": product.get("image_url"),
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                    processed_batch.append(product_data)
                
                # Insert batch
                result = self._client.table("products")\
                    .insert(processed_batch)\
                    .execute()
                
                total_saved += len(result.data) if result.data else 0
            
            logger.info(f"Saved {total_saved} products for store {store_id}")
            return total_saved
            
        except Exception as e:
            logger.error(f"Failed to save products: {e}")
            return 0
    
    async def save_current_prices(self, prices: List[Dict[str, Any]]) -> int:
        """Save current prices to database."""
        try:
            if not self._client or not prices:
                return 0
            
            # Process prices in batches
            batch_size = 100
            total_saved = 0
            
            for i in range(0, len(prices), batch_size):
                batch = prices[i:i + batch_size]
                
                # Prepare price data
                processed_batch = []
                for price in batch:
                    price_data = {
                        "store_product_id": price.get("store_product_id"),
                        "price": price.get("price"),
                        "original_price": price.get("original_price"),
                        "discount_percentage": price.get("discount_percentage"),
                        "is_promotion": price.get("is_promotion", False),
                        "promotion_text": price.get("promotion_text"),
                        "last_updated": datetime.now().isoformat()
                    }
                    processed_batch.append(price_data)
                
                # Upsert batch (insert or update)
                result = self._client.table("current_prices")\
                    .upsert(processed_batch)\
                    .execute()
                
                total_saved += len(result.data) if result.data else 0
            
            logger.info(f"Saved {total_saved} price updates")
            return total_saved
            
        except Exception as e:
            logger.error(f"Failed to save current prices: {e}")
            return 0
    
    async def log_system_event(self, level: str, message: str, component: str = "system", 
                             store_id: str = None, job_id: str = None, metadata: Dict[str, Any] = None) -> bool:
        """Log system event."""
        try:
            if not self._client:
                await self.initialize()
            
            log_data = {
                "level": level,
                "message": message,
                "component": component,
                "store_id": store_id,
                "job_id": job_id,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }
            
            result = self._client.table("system_logs")\
                .insert(log_data)\
                .execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
            return False
    
    async def get_system_logs(self, limit: int = 100, level: str = None) -> List[Dict[str, Any]]:
        """Get system logs."""
        try:
            if not self._client:
                await self.initialize()
            
            query = self._client.table("system_logs")\
                .select("*")\
                .order("created_at", desc=True)\
                .limit(limit)
            
            if level:
                query = query.eq("level", level)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get system logs: {e}")
            return []
    
    async def get_store_performance_metrics(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get store performance metrics."""
        try:
            if not self._client:
                await self.initialize()
            
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get job statistics by store
            result = self._client.table("scraping_jobs")\
                .select("store_id, stores(name, slug), status, products_processed, errors_count, created_at")\
                .gte("created_at", start_date)\
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get store performance metrics: {e}")
            return []


# Global database client instance
_db_client: Optional[SupabaseClient] = None

async def get_database() -> SupabaseClient:
    """Get the global database client instance."""
    global _db_client
    
    if _db_client is None:
        _db_client = SupabaseClient()
        await _db_client.initialize()
    
    return _db_client

async def initialize_database():
    """Initialize the database connection."""
    global _db_client
    
    if _db_client is None:
        _db_client = SupabaseClient()
        success = await _db_client.initialize()
        if not success:
            logger.error("Failed to initialize database connection")
            return False
    
    return True 