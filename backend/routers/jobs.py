"""
Jobs API Router
Manages scraping jobs and queue operations
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
from pydantic import BaseModel

# Database integration
from config.database import get_db_dependency
from database.client import SupabaseClient

# Job queue integration
from job_queue.job_manager import (
    get_job_queue, 
    create_scraping_job, 
    get_job_status, 
    cancel_job,
    JobConfig,
    JobPriority
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for API requests
class CreateJobRequest(BaseModel):
    store: str
    job_type: str = "price_update"
    priority: str = "normal"
    max_pages: int = 100
    categories: Optional[List[str]] = None

class BulkJobRequest(BaseModel):
    stores: List[str]
    job_type: str = "price_update"
    priority: str = "normal"

# API Endpoints

@router.get("/")
async def get_all_jobs(
    limit: int = 50,
    status_filter: str = None,
    store_filter: str = None,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Get all jobs with optional filtering"""
    try:
        # Get jobs from database
        recent_jobs = await db.get_recent_jobs(limit=limit * 2)  # Get more to allow for filtering
        
        # Apply filters
        filtered_jobs = recent_jobs
        
        if status_filter:
            filtered_jobs = [job for job in filtered_jobs if job.get("status") == status_filter]
        
        if store_filter:
            # Get store ID for filtering
            store = await db.get_store_by_slug(store_filter)
            if store:
                filtered_jobs = [job for job in filtered_jobs if job.get("store_id") == store["id"]]
        
        # Limit results
        filtered_jobs = filtered_jobs[:limit]
        
        # Enhance with queue information
        enhanced_jobs = []
        for job in filtered_jobs:
            job_status = await get_job_status(job["id"])
            enhanced_job = {**job}
            
            if job_status:
                enhanced_job.update({
                    "queue_info": job_status,
                    "job_queue_managed": True
                })
            
            enhanced_jobs.append(enhanced_job)
        
        return {
            "jobs": enhanced_jobs,
            "total": len(enhanced_jobs),
            "filters": {
                "status": status_filter,
                "store": store_filter,
                "limit": limit
            },
            "job_queue_enabled": True
        }
        
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get jobs: {str(e)}")

@router.post("/create")
async def create_job(
    request: CreateJobRequest,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Create a new scraping job"""
    try:
        # Validate store exists
        store = await db.get_store_by_slug(request.store)
        if not store:
            raise HTTPException(status_code=404, detail=f"Store '{request.store}' not found")
        
        # Create job
        job_id = await create_scraping_job(
            store=request.store,
            job_type=request.job_type,
            priority=request.priority,
            max_pages=request.max_pages,
            categories=request.categories
        )
        
        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to create job")
        
        # Log creation
        await db.log_system_event(
            "info",
            f"Created new {request.job_type} job for {request.store}",
            "jobs_api",
            job_id=job_id
        )
        
        return {
            "success": True,
            "job_id": job_id,
            "message": f"Created {request.job_type} job for {request.store}",
            "created_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

@router.post("/bulk-create")
async def create_bulk_jobs(
    request: BulkJobRequest,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Create multiple jobs for different stores"""
    try:
        created_jobs = []
        failed_stores = []
        
        for store_slug in request.stores:
            try:
                # Validate store exists
                store = await db.get_store_by_slug(store_slug)
                if not store:
                    failed_stores.append({"store": store_slug, "error": "Store not found"})
                    continue
                
                # Create job
                job_id = await create_scraping_job(
                    store=store_slug,
                    job_type=request.job_type,
                    priority=request.priority
                )
                
                if job_id:
                    created_jobs.append({
                        "store": store_slug,
                        "job_id": job_id,
                        "job_type": request.job_type
                    })
                else:
                    failed_stores.append({"store": store_slug, "error": "Failed to create job"})
                    
            except Exception as e:
                failed_stores.append({"store": store_slug, "error": str(e)})
        
        # Log bulk creation
        await db.log_system_event(
            "info",
            f"Bulk job creation: {len(created_jobs)} successful, {len(failed_stores)} failed",
            "jobs_api"
        )
        
        return {
            "success": len(created_jobs) > 0,
            "created_jobs": created_jobs,
            "failed_stores": failed_stores,
            "total_created": len(created_jobs),
            "total_failed": len(failed_stores),
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating bulk jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create bulk jobs: {str(e)}")

@router.get("/{job_id}")
async def get_job_details(
    job_id: str,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Get detailed information about a specific job"""
    try:
        # Get job from database
        job = await db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        # Get queue status
        queue_status = await get_job_status(job_id)
        
        return {
            "job": job,
            "queue_status": queue_status,
            "job_queue_managed": queue_status is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job details {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job details: {str(e)}")

@router.post("/{job_id}/cancel")
async def cancel_job_endpoint(
    job_id: str,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Cancel a specific job"""
    try:
        # Get job details first
        job = await db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        # Cancel the job
        success = await cancel_job(job_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to cancel job")
        
        # Log cancellation
        await db.log_system_event(
            "info",
            f"Cancelled job {job_id}",
            "jobs_api",
            job_id=job_id
        )
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "Job cancelled successfully",
            "cancelled_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")

@router.get("/queue/stats")
async def get_queue_statistics(db: SupabaseClient = Depends(get_db_dependency)) -> Dict[str, Any]:
    """Get queue statistics and system status"""
    try:
        # Get queue stats
        queue = await get_job_queue()
        queue_stats = await queue.get_queue_stats()
        
        # Get recent job statistics from database
        recent_jobs = await db.get_recent_jobs(limit=100)
        
        # Calculate statistics
        total_jobs = len(recent_jobs)
        completed_jobs = len([job for job in recent_jobs if job.get("status") == "completed"])
        failed_jobs = len([job for job in recent_jobs if job.get("status") == "failed"])
        running_jobs = len([job for job in recent_jobs if job.get("status") == "running"])
        pending_jobs = len([job for job in recent_jobs if job.get("status") == "pending"])
        
        # Calculate success rate
        finished_jobs = completed_jobs + failed_jobs
        success_rate = (completed_jobs / finished_jobs * 100) if finished_jobs > 0 else 100.0
        
        # Jobs by store
        store_stats = {}
        for job in recent_jobs:
            store_info = job.get("stores", {})
            store_name = store_info.get("name", "Unknown") if store_info else "Unknown"
            
            if store_name not in store_stats:
                store_stats[store_name] = {"total": 0, "completed": 0, "failed": 0}
            
            store_stats[store_name]["total"] += 1
            if job.get("status") == "completed":
                store_stats[store_name]["completed"] += 1
            elif job.get("status") == "failed":
                store_stats[store_name]["failed"] += 1
        
        # Jobs today
        today = datetime.now().date()
        jobs_today = len([
            job for job in recent_jobs 
            if job.get("created_at") and 
            datetime.fromisoformat(job["created_at"].replace("Z", "+00:00")).date() == today
        ])
        
        return {
            "queue_stats": queue_stats,
            "job_statistics": {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "running_jobs": running_jobs,
                "pending_jobs": pending_jobs,
                "success_rate": round(success_rate, 2),
                "jobs_today": jobs_today
            },
            "store_statistics": store_stats,
            "last_updated": datetime.now().isoformat(),
            "job_queue_enabled": True
        }
        
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue statistics: {str(e)}")

@router.get("/active/summary")
async def get_active_jobs_summary(db: SupabaseClient = Depends(get_db_dependency)) -> Dict[str, Any]:
    """Get summary of currently active jobs"""
    try:
        # Get active jobs from database
        active_jobs = await db.get_active_jobs()
        
        # Enhance with queue information
        enhanced_jobs = []
        for job in active_jobs:
            job_status = await get_job_status(job["id"])
            enhanced_job = {**job}
            
            if job_status:
                enhanced_job.update(job_status)
            
            enhanced_jobs.append(enhanced_job)
        
        # Group by store
        jobs_by_store = {}
        for job in enhanced_jobs:
            store_info = job.get("stores", {})
            store_name = store_info.get("name", "Unknown") if store_info else "Unknown"
            
            if store_name not in jobs_by_store:
                jobs_by_store[store_name] = []
            
            jobs_by_store[store_name].append({
                "id": job["id"],
                "job_type": job.get("job_type", "unknown"),
                "status": job.get("status", "unknown"),
                "created_at": job.get("created_at"),
                "started_at": job.get("started_at"),
                "progress": job.get("progress", {})
            })
        
        return {
            "active_jobs": enhanced_jobs,
            "jobs_by_store": jobs_by_store,
            "total_active": len(enhanced_jobs),
            "stores_with_active_jobs": len(jobs_by_store),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting active jobs summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active jobs: {str(e)}")

@router.post("/schedule/daily")
async def schedule_daily_jobs(
    job_type: str = "price_update",
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Schedule daily jobs for all active stores"""
    try:
        # Get all active stores
        stores = await db.get_stores()
        
        created_jobs = []
        failed_stores = []
        
        for store in stores:
            try:
                job_id = await create_scraping_job(
                    store=store["slug"],
                    job_type=job_type,
                    priority="normal"
                )
                
                if job_id:
                    created_jobs.append({
                        "store": store["slug"],
                        "store_name": store["name"],
                        "job_id": job_id
                    })
                else:
                    failed_stores.append({"store": store["slug"], "error": "Failed to create job"})
                    
            except Exception as e:
                failed_stores.append({"store": store["slug"], "error": str(e)})
        
        # Log scheduled jobs
        await db.log_system_event(
            "info",
            f"Scheduled daily {job_type} jobs: {len(created_jobs)} successful, {len(failed_stores)} failed",
            "jobs_api"
        )
        
        return {
            "success": True,
            "message": f"Scheduled daily {job_type} jobs",
            "created_jobs": created_jobs,
            "failed_stores": failed_stores,
            "total_scheduled": len(created_jobs),
            "scheduled_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error scheduling daily jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule daily jobs: {str(e)}")

@router.delete("/cleanup")
async def cleanup_old_jobs(
    days: int = 7,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Clean up old completed jobs (placeholder - implement based on your retention policy)"""
    try:
        # This is a placeholder for job cleanup functionality
        # In a real implementation, you would:
        # 1. Query for jobs older than specified days
        # 2. Archive or delete completed jobs
        # 3. Clean up Redis queue data
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Log cleanup attempt
        await db.log_system_event(
            "info",
            f"Job cleanup requested for jobs older than {days} days",
            "jobs_api"
        )
        
        return {
            "success": True,
            "message": f"Cleanup initiated for jobs older than {days} days",
            "cutoff_date": cutoff_date.isoformat(),
            "cleaned_at": datetime.now().isoformat(),
            "note": "This is a placeholder implementation"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup jobs: {str(e)}") 