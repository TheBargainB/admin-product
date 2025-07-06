"""
Background Job Worker
Processes scraping jobs from Redis queue
"""

import asyncio
import signal
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from job_queue.job_manager import get_job_queue, JobStatus
from database.client import get_database
from config.settings import settings

# Import agents
try:
    from agents.albert_heijn_agent import AlbertHeijnAgent
    from agents.dirk_agent import DirkAgent
    from agents.hoogvliet_agent import HoogvlietAgent
    from agents.jumbo_agent import JumboAgent
    AGENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Agent imports failed: {e}")
    AGENTS_AVAILABLE = False

logger = logging.getLogger(__name__)

class JobWorker:
    """Background worker that processes scraping jobs"""
    
    def __init__(self):
        self.running = False
        self.agents = {}
        self.current_job_id = None
        
        # Initialize agents if available
        if AGENTS_AVAILABLE:
            try:
                self.agents = {
                    "albert_heijn": AlbertHeijnAgent(),
                    "dirk": DirkAgent(),
                    "hoogvliet": HoogvlietAgent(),
                    "jumbo": JumboAgent()
                }
                logger.info(f"✅ Initialized {len(self.agents)} agents")
            except Exception as e:
                logger.error(f"❌ Failed to initialize agents: {e}")
                self.agents = {}
        else:
            logger.warning("⚠️ LangGraph agents not available")
    
    async def start(self):
        """Start the worker process"""
        self.running = True
        logger.info("🚀 Starting job worker...")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Main worker loop
        while self.running:
            try:
                await self._process_jobs()
                await asyncio.sleep(1)  # Short sleep to prevent busy waiting
                
            except Exception as e:
                logger.error(f"❌ Worker error: {e}")
                await asyncio.sleep(5)  # Longer sleep on error
    
    async def stop(self):
        """Stop the worker gracefully"""
        logger.info("🛑 Stopping job worker...")
        self.running = False
        
        # Cancel current job if running
        if self.current_job_id:
            queue = await get_job_queue()
            await queue.cancel_job(self.current_job_id)
            logger.info(f"🚫 Cancelled current job: {self.current_job_id}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum}, shutting down gracefully...")
        asyncio.create_task(self.stop())
    
    async def _process_jobs(self):
        """Process jobs from the queue"""
        queue = await get_job_queue()
        
        # Get next job from queue
        job_id = await queue.get_next_job()
        if not job_id:
            return  # No jobs available
        
        self.current_job_id = job_id
        
        try:
            # Start the job
            await queue.start_job(job_id)
            
            # Get job details
            job_status = await queue.get_job_status(job_id)
            if not job_status:
                logger.error(f"❌ Job {job_id} not found")
                return
            
            logger.info(f"🔄 Processing job {job_id} for {job_status['store']}")
            
            # Execute the job
            result = await self._execute_job(job_status)
            
            # Complete the job
            if result.get("success", False):
                await queue.complete_job(job_id, result)
                logger.info(f"✅ Job {job_id} completed successfully")
            else:
                await queue.fail_job(job_id, result.get("error", "Unknown error"))
                logger.error(f"❌ Job {job_id} failed")
                
        except Exception as e:
            # Job failed
            await queue.fail_job(job_id, str(e))
            logger.error(f"❌ Job {job_id} failed with exception: {e}")
            
        finally:
            self.current_job_id = None
    
    async def _execute_job(self, job_status: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a scraping job"""
        store_slug = job_status["store"]
        job_type = job_status["job_type"]
        job_id = job_status["id"]
        
        try:
            # Check if we have an agent for this store
            if not AGENTS_AVAILABLE or store_slug not in self.agents:
                return {
                    "success": False,
                    "error": f"Agent for {store_slug} not available",
                    "products_processed": 0,
                    "products_updated": 0
                }
            
            agent = self.agents[store_slug]
            db = await get_database()
            
            # Log job start
            await db.log_system_event(
                "info",
                f"Started scraping job for {store_slug}",
                "worker",
                job_id=job_id
            )
            
            # Execute the scraping based on job type
            if job_type == "price_update":
                result = await self._run_price_update(agent, job_id)
            elif job_type == "full_scrape":
                result = await self._run_full_scrape(agent, job_id)
            elif job_type == "category_update":
                result = await self._run_category_update(agent, job_id)
            else:
                result = await self._run_default_scrape(agent, job_id)
            
            # Log completion
            await db.log_system_event(
                "info" if result.get("success") else "error",
                f"Completed scraping job for {store_slug} - {result.get('products_processed', 0)} products processed",
                "worker",
                job_id=job_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error executing job {job_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "products_processed": 0,
                "products_updated": 0
            }
    
    async def _run_price_update(self, agent, job_id: str) -> Dict[str, Any]:
        """Run a price update job"""
        try:
            logger.info(f"📊 Running price update with {agent.name}")
            
            # Mock implementation - in real implementation this would call agent methods
            await asyncio.sleep(2)  # Simulate work
            
            # Simulate processing results
            products_processed = 150
            products_updated = 120
            
            return {
                "success": True,
                "job_type": "price_update",
                "products_processed": products_processed,
                "products_updated": products_updated,
                "duration": 2.0,
                "agent": agent.name
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "job_type": "price_update",
                "products_processed": 0,
                "products_updated": 0
            }
    
    async def _run_full_scrape(self, agent, job_id: str) -> Dict[str, Any]:
        """Run a full scraping job"""
        try:
            logger.info(f"🔍 Running full scrape with {agent.name}")
            
            # Mock implementation - in real implementation this would call agent methods
            await asyncio.sleep(5)  # Simulate longer work
            
            # Simulate processing results
            products_processed = 450
            products_updated = 380
            new_products = 70
            
            return {
                "success": True,
                "job_type": "full_scrape",
                "products_processed": products_processed,
                "products_updated": products_updated,
                "new_products": new_products,
                "duration": 5.0,
                "agent": agent.name
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "job_type": "full_scrape",
                "products_processed": 0,
                "products_updated": 0
            }
    
    async def _run_category_update(self, agent, job_id: str) -> Dict[str, Any]:
        """Run a category update job"""
        try:
            logger.info(f"📂 Running category update with {agent.name}")
            
            # Mock implementation
            await asyncio.sleep(3)  # Simulate work
            
            categories_processed = 15
            products_processed = 200
            
            return {
                "success": True,
                "job_type": "category_update",
                "categories_processed": categories_processed,
                "products_processed": products_processed,
                "products_updated": products_processed - 20,
                "duration": 3.0,
                "agent": agent.name
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "job_type": "category_update",
                "products_processed": 0,
                "products_updated": 0
            }
    
    async def _run_default_scrape(self, agent, job_id: str) -> Dict[str, Any]:
        """Run a default scraping job"""
        try:
            logger.info(f"⚙️ Running default scrape with {agent.name}")
            
            # Fallback to price update
            return await self._run_price_update(agent, job_id)
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "job_type": "default",
                "products_processed": 0,
                "products_updated": 0
            }

async def main():
    """Main entry point for the worker"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🎯 BargainB Job Worker Starting...")
    
    # Initialize database
    try:
        from database.client import initialize_database
        await initialize_database()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return
    
    # Create and start worker
    worker = JobWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("📡 Received interrupt signal")
    finally:
        await worker.stop()
        logger.info("✅ Worker stopped")

if __name__ == "__main__":
    asyncio.run(main()) 