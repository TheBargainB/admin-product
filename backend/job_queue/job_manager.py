"""
Job Queue Manager
Redis-based background job processing system for scraping tasks
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import logging

import redis
from pydantic import BaseModel
from config.settings import settings
from database.client import get_database

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"  
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class JobConfig:
    """Configuration for scraping jobs"""
    store: str
    job_type: str = "price_update"  # full_scrape, price_update, category_update
    max_pages: int = 100
    rate_limit_delay: float = 1.0
    batch_size: int = 100
    categories: Optional[List[str]] = None
    priority: JobPriority = JobPriority.NORMAL
    retry_count: int = 3
    timeout: int = 3600  # 1 hour
    scheduled_time: Optional[datetime] = None

@dataclass
class JobInfo:
    """Job information"""
    id: str
    store: str
    job_type: str
    status: JobStatus
    config: Dict[str, Any]
    priority: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Dict[str, Any] = None
    result: Dict[str, Any] = None
    error_message: Optional[str] = None

class RedisJobQueue:
    """Redis-based job queue manager"""
    
    def __init__(self):
        self.redis_client = None
        self.initialized = False
        self._initialize_redis()
        
        # Queue names by priority
        self.queues = {
            JobPriority.LOW: "scraping_jobs:low",
            JobPriority.NORMAL: "scraping_jobs:normal", 
            JobPriority.HIGH: "scraping_jobs:high",
            JobPriority.URGENT: "scraping_jobs:urgent"
        }
        
        # Job tracking keys
        self.JOB_KEY_PREFIX = "job:"
        self.ACTIVE_JOBS_KEY = "jobs:active"
        self.COMPLETED_JOBS_KEY = "jobs:completed"
        self.FAILED_JOBS_KEY = "jobs:failed"
        
    def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            # Parse Redis URL
            redis_url = settings.REDIS_URL
            if redis_url.startswith('redis://'):
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
            else:
                # Fallback to default localhost connection
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True
                )
            
            # Test connection
            self.redis_client.ping()
            self.initialized = True
            logger.info("✅ Redis connection established")
            
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")
            logger.info("📝 Using fallback in-memory queue")
            self._setup_fallback()
    
    def _setup_fallback(self):
        """Setup fallback in-memory queue when Redis is not available"""
        self.fallback_queue = {}
        self.fallback_jobs = {}
        self.initialized = False
        
    async def create_job(self, config: JobConfig) -> str:
        """Create a new scraping job"""
        job_id = str(uuid.uuid4())
        
        # Get database connection
        db = await get_database()
        
        # Get store from database
        store = await db.get_store_by_slug(config.store)
        if not store:
            raise ValueError(f"Store '{config.store}' not found")
        
        # Convert config to dict and ensure enums are serializable
        config_dict = asdict(config)
        config_dict["priority"] = config.priority.value  # Convert enum to value
        
        # Create job in database
        db_job = await db.create_scraping_job(
            store["id"], 
            config.job_type,
            metadata={
                "priority": config.priority.value,
                "config": config_dict,
                "max_pages": config.max_pages,
                "batch_size": config.batch_size,
                "categories": config.categories
            }
        )
        
        if not db_job:
            raise RuntimeError("Failed to create job in database")
        
        job_info = JobInfo(
            id=db_job["id"],
            store=config.store,
            job_type=config.job_type,
            status=JobStatus.PENDING,
            config=config_dict,
            priority=config.priority.value,
            created_at=datetime.now(),
            progress={},
            result={}
        )
        
        # Store job info in Redis/fallback
        await self._store_job(job_info)
        
        logger.info(f"✅ Created {config.store} job: {db_job['id']}")
        return db_job["id"]
    
    async def queue_job(self, job_id: str) -> bool:
        """Queue a job for execution"""
        try:
            job_info = await self._get_job(job_id)
            if not job_info:
                logger.error(f"Job {job_id} not found")
                return False
            
            # Update database status
            db = await get_database()
            await db.update_job_status(job_id, "pending")
            
            # Add to appropriate priority queue
            priority = JobPriority(job_info.priority)
            queue_name = self.queues[priority]
            
            if self.initialized:
                # Use Redis
                self.redis_client.lpush(queue_name, job_id)
                self.redis_client.sadd(self.ACTIVE_JOBS_KEY, job_id)
            else:
                # Use fallback
                if queue_name not in self.fallback_queue:
                    self.fallback_queue[queue_name] = []
                self.fallback_queue[queue_name].append(job_id)
            
            # Update job status
            job_info.status = JobStatus.QUEUED
            await self._store_job(job_info)
            
            logger.info(f"🔄 Queued job {job_id} for {job_info.store}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to queue job {job_id}: {e}")
            return False
    
    async def get_next_job(self) -> Optional[str]:
        """Get the next job from the queue (highest priority first)"""
        try:
            # Check queues in priority order
            for priority in [JobPriority.URGENT, JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]:
                queue_name = self.queues[priority]
                
                if self.initialized:
                    # Use Redis
                    job_id = self.redis_client.brpop(queue_name, timeout=1)
                    if job_id:
                        return job_id[1]  # brpop returns (queue_name, job_id)
                else:
                    # Use fallback
                    if queue_name in self.fallback_queue and self.fallback_queue[queue_name]:
                        return self.fallback_queue[queue_name].pop(0)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next job: {e}")
            return None
    
    async def start_job(self, job_id: str) -> bool:
        """Mark job as started"""
        try:
            # Update database
            db = await get_database()
            await db.update_job_status(job_id, "running")
            
            # Update job info
            job_info = await self._get_job(job_id)
            if job_info:
                job_info.status = JobStatus.RUNNING
                job_info.started_at = datetime.now()
                await self._store_job(job_info)
            
            logger.info(f"🚀 Started job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting job {job_id}: {e}")
            return False
    
    async def complete_job(self, job_id: str, result: Dict[str, Any] = None) -> bool:
        """Mark job as completed"""
        try:
            # Update database
            db = await get_database()
            products_processed = result.get("products_processed", 0) if result else 0
            products_updated = result.get("products_updated", 0) if result else 0
            
            await db.update_job_status(
                job_id, 
                "completed",
                products_processed=products_processed,
                products_updated=products_updated
            )
            
            # Update job info and move to completed
            job_info = await self._get_job(job_id)
            if job_info:
                job_info.status = JobStatus.COMPLETED
                job_info.completed_at = datetime.now()
                job_info.result = result or {}
                await self._store_job(job_info)
                
                # Move from active to completed
                if self.initialized:
                    self.redis_client.srem(self.ACTIVE_JOBS_KEY, job_id)
                    self.redis_client.sadd(self.COMPLETED_JOBS_KEY, job_id)
            
            logger.info(f"✅ Completed job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error completing job {job_id}: {e}")
            return False
    
    async def fail_job(self, job_id: str, error_message: str = None) -> bool:
        """Mark job as failed"""
        try:
            # Update database
            db = await get_database()
            await db.update_job_status(
                job_id, 
                "failed",
                errors_count=1,
                error_details={"error": error_message} if error_message else None
            )
            
            # Update job info and move to failed
            job_info = await self._get_job(job_id)
            if job_info:
                job_info.status = JobStatus.FAILED
                job_info.completed_at = datetime.now()
                job_info.error_message = error_message
                await self._store_job(job_info)
                
                # Move from active to failed
                if self.initialized:
                    self.redis_client.srem(self.ACTIVE_JOBS_KEY, job_id)
                    self.redis_client.sadd(self.FAILED_JOBS_KEY, job_id)
            
            logger.error(f"❌ Failed job {job_id}: {error_message}")
            return True
            
        except Exception as e:
            logger.error(f"Error failing job {job_id}: {e}")
            return False
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        try:
            # Update database
            db = await get_database()
            await db.update_job_status(job_id, "cancelled")
            
            # Update job info
            job_info = await self._get_job(job_id)
            if job_info:
                job_info.status = JobStatus.CANCELLED
                job_info.completed_at = datetime.now()
                await self._store_job(job_info)
            
            # Remove from active jobs
            if self.initialized:
                self.redis_client.srem(self.ACTIVE_JOBS_KEY, job_id)
            
            logger.info(f"🚫 Cancelled job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return False
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status information"""
        try:
            job_info = await self._get_job(job_id)
            if not job_info:
                return None
                
            return {
                "id": job_info.id,
                "store": job_info.store,
                "job_type": job_info.job_type,
                "status": job_info.status.value,
                "priority": job_info.priority,
                "created_at": job_info.created_at.isoformat(),
                "started_at": job_info.started_at.isoformat() if job_info.started_at else None,
                "completed_at": job_info.completed_at.isoformat() if job_info.completed_at else None,
                "progress": job_info.progress,
                "result": job_info.result,
                "error_message": job_info.error_message
            }
            
        except Exception as e:
            logger.error(f"Error getting job status {job_id}: {e}")
            return None
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        try:
            stats = {}
            
            if self.initialized:
                for priority, queue_name in self.queues.items():
                    stats[priority.name.lower()] = self.redis_client.llen(queue_name)
                    
                stats["active_jobs"] = self.redis_client.scard(self.ACTIVE_JOBS_KEY)
                stats["completed_jobs"] = self.redis_client.scard(self.COMPLETED_JOBS_KEY)
                stats["failed_jobs"] = self.redis_client.scard(self.FAILED_JOBS_KEY)
            else:
                # Fallback stats
                for priority, queue_name in self.queues.items():
                    stats[priority.name.lower()] = len(self.fallback_queue.get(queue_name, []))
                stats["active_jobs"] = 0
                stats["completed_jobs"] = 0
                stats["failed_jobs"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    async def _store_job(self, job_info: JobInfo):
        """Store job information"""
        job_key = f"{self.JOB_KEY_PREFIX}{job_info.id}"
        job_data = {
            "id": job_info.id,
            "store": job_info.store,
            "job_type": job_info.job_type,
            "status": job_info.status.value,
            "config": json.dumps(job_info.config),
            "priority": job_info.priority,
            "created_at": job_info.created_at.isoformat(),
            "started_at": job_info.started_at.isoformat() if job_info.started_at else "",
            "completed_at": job_info.completed_at.isoformat() if job_info.completed_at else "",
            "progress": json.dumps(job_info.progress or {}),
            "result": json.dumps(job_info.result or {}),
            "error_message": job_info.error_message or ""
        }
        
        if self.initialized:
            self.redis_client.hset(job_key, mapping=job_data)
        else:
            self.fallback_jobs[job_info.id] = job_data
    
    async def _get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job information"""
        try:
            job_key = f"{self.JOB_KEY_PREFIX}{job_id}"
            
            if self.initialized:
                job_data = self.redis_client.hgetall(job_key)
            else:
                job_data = self.fallback_jobs.get(job_id, {})
            
            if not job_data:
                return None
            
            return JobInfo(
                id=job_data["id"],
                store=job_data["store"],
                job_type=job_data["job_type"],
                status=JobStatus(job_data["status"]),
                config=json.loads(job_data["config"]),
                priority=int(job_data["priority"]),
                created_at=datetime.fromisoformat(job_data["created_at"]),
                started_at=datetime.fromisoformat(job_data["started_at"]) if job_data["started_at"] else None,
                completed_at=datetime.fromisoformat(job_data["completed_at"]) if job_data["completed_at"] else None,
                progress=json.loads(job_data["progress"]),
                result=json.loads(job_data["result"]),
                error_message=job_data["error_message"] if job_data["error_message"] else None
            )
            
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None

# Global job queue instance
_job_queue: Optional[RedisJobQueue] = None

async def get_job_queue() -> RedisJobQueue:
    """Get the global job queue instance"""
    global _job_queue
    
    if _job_queue is None:
        _job_queue = RedisJobQueue()
    
    return _job_queue

# Convenience functions
async def create_scraping_job(store: str, job_type: str = "price_update", **kwargs) -> str:
    """Create a new scraping job"""
    # Convert string priority to enum
    priority = kwargs.get("priority", "normal")
    if isinstance(priority, str):
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT
        }
        kwargs["priority"] = priority_map.get(priority.lower(), JobPriority.NORMAL)
    
    config = JobConfig(
        store=store,
        job_type=job_type,
        **kwargs
    )
    
    queue = await get_job_queue()
    job_id = await queue.create_job(config)
    await queue.queue_job(job_id)
    
    return job_id

async def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status"""
    queue = await get_job_queue()
    return await queue.get_job_status(job_id)

async def cancel_job(job_id: str) -> bool:
    """Cancel a job"""
    queue = await get_job_queue()
    return await queue.cancel_job(job_id) 