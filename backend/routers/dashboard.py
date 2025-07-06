from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import psutil
import asyncio
from config.database import get_db_dependency
from utils.logging import get_logger
from database.client import SupabaseClient

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = get_logger(__name__)

# Pydantic models for API responses
class SystemMetric(BaseModel):
    name: str
    value: float
    unit: str
    status: str
    timestamp: datetime

class SystemHealth(BaseModel):
    metrics: List[SystemMetric]
    overall_status: str
    last_updated: datetime

class JobStatus(BaseModel):
    id: str
    store: str
    job_type: str
    status: str
    progress: float
    start_time: datetime
    estimated_end: Optional[datetime]
    products_processed: int
    products_total: int
    error_count: int

class ChartData(BaseModel):
    label: str
    value: int
    change: Optional[float] = None

class DashboardMetrics(BaseModel):
    total_products: int
    active_stores: int
    today_updates: int
    system_health: float
    last_scrape: str
    running_jobs: int
    error_rate: float
    avg_response_time: float

@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(db: SupabaseClient = Depends(get_db_dependency)):
    """Get main dashboard metrics"""
    try:
        # Get real data from database
        stores = await db.get_stores()
        total_products = await db.get_products_count()
        today_updates = await db.get_today_price_updates()
        active_jobs = await db.get_active_jobs()
        
        # Calculate system health based on real metrics
        health_check = await db.health_check()
        system_health = 100.0 if health_check["status"] == "healthy" else 50.0
        
        # Get recent jobs for error rate calculation
        recent_jobs = await db.get_recent_jobs(limit=50)
        error_jobs = [job for job in recent_jobs if job.get("status") == "failed"]
        error_rate = (len(error_jobs) / len(recent_jobs)) * 100 if recent_jobs else 0
        
        # Get response time from health check
        avg_response_time = health_check.get("response_time_ms", 0) / 1000  # Convert to seconds
        
        # Get last scrape time
        last_scrape = "Never"
        if recent_jobs:
            last_job = recent_jobs[0]
            if last_job.get("completed_at"):
                last_scrape_time = datetime.fromisoformat(last_job["completed_at"].replace("Z", "+00:00"))
                time_diff = datetime.now() - last_scrape_time.replace(tzinfo=None)
                if time_diff.days > 0:
                    last_scrape = f"{time_diff.days} days ago"
                elif time_diff.seconds > 3600:
                    last_scrape = f"{time_diff.seconds // 3600} hours ago"
                else:
                    last_scrape = f"{time_diff.seconds // 60} minutes ago"
        
        metrics = DashboardMetrics(
            total_products=total_products,
            active_stores=len(stores),
            today_updates=today_updates,
            system_health=system_health,
            last_scrape=last_scrape,
            running_jobs=len(active_jobs),
            error_rate=error_rate,
            avg_response_time=avg_response_time
        )
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {e}")
        # Return fallback metrics on error
        return DashboardMetrics(
            total_products=0,
            active_stores=0,
            today_updates=0,
            system_health=0.0,
            last_scrape="Error",
            running_jobs=0,
            error_rate=100.0,
            avg_response_time=0.0
        )

@router.get("/system-health", response_model=SystemHealth)
async def get_system_health(db: SupabaseClient = Depends(get_db_dependency)):
    """Get real-time system health metrics"""
    try:
        # Get actual system metrics using psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get database health
        db_health = await db.health_check()
        db_response_time = db_health.get("response_time_ms", 0)
        
        metrics = [
            SystemMetric(
                name="CPU Usage",
                value=cpu_percent,
                unit="%",
                status="healthy" if cpu_percent < 70 else "warning" if cpu_percent < 90 else "critical",
                timestamp=datetime.now()
            ),
            SystemMetric(
                name="Memory Usage",
                value=memory.percent,
                unit="%",
                status="healthy" if memory.percent < 70 else "warning" if memory.percent < 90 else "critical",
                timestamp=datetime.now()
            ),
            SystemMetric(
                name="Disk Usage",
                value=disk.percent,
                unit="%",
                status="healthy" if disk.percent < 70 else "warning" if disk.percent < 90 else "critical",
                timestamp=datetime.now()
            ),
            SystemMetric(
                name="Database Response",
                value=db_response_time,
                unit="ms",
                status="healthy" if db_response_time < 100 else "warning" if db_response_time < 500 else "critical",
                timestamp=datetime.now()
            )
        ]
        
        # Determine overall status
        critical_count = sum(1 for m in metrics if m.status == "critical")
        warning_count = sum(1 for m in metrics if m.status == "warning")
        
        if critical_count > 0:
            overall_status = "critical"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return SystemHealth(
            metrics=metrics,
            overall_status=overall_status,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error fetching system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch system health")

@router.get("/jobs", response_model=List[JobStatus])
async def get_active_jobs(db: SupabaseClient = Depends(get_db_dependency)):
    """Get current scraping jobs status"""
    try:
        # Get real active jobs from database
        active_jobs = await db.get_active_jobs()
        
        job_statuses = []
        for job in active_jobs:
            # Extract store info
            store_info = job.get("stores", {})
            store_name = store_info.get("name", "Unknown Store") if store_info else "Unknown Store"
            
            # Calculate progress
            processed = job.get("products_processed", 0)
            total = job.get("products_total", 0) or 1  # Avoid division by zero
            progress = (processed / total) * 100
            
            # Parse timestamps
            start_time = datetime.now()
            if job.get("started_at"):
                start_time = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            
            # Estimate end time for running jobs
            estimated_end = None
            if job.get("status") == "running" and progress > 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > 0:
                    estimated_total = elapsed / (progress / 100)
                    estimated_end = start_time + timedelta(seconds=estimated_total)
            
            job_status = JobStatus(
                id=job["id"],
                store=store_name,
                job_type=job.get("job_type", "unknown"),
                status=job.get("status", "unknown"),
                progress=progress,
                start_time=start_time,
                estimated_end=estimated_end,
                products_processed=processed,
                products_total=total,
                error_count=job.get("errors_count", 0)
            )
            job_statuses.append(job_status)
        
        return job_statuses
        
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")

@router.get("/store-performance", response_model=List[ChartData])
async def get_store_performance(time_range: str = "24h", db: SupabaseClient = Depends(get_db_dependency)):
    """Get store performance metrics"""
    try:
        # Parse time range
        if time_range == "24h":
            days = 1
        elif time_range == "7d":
            days = 7
        elif time_range == "30d":
            days = 30
        else:
            days = 7
        
        # Get performance metrics from database
        metrics = await db.get_store_performance_metrics(days)
        
        # Group by store and calculate metrics
        store_metrics = {}
        for metric in metrics:
            store_info = metric.get("stores", {})
            store_name = store_info.get("name", "Unknown") if store_info else "Unknown"
            
            if store_name not in store_metrics:
                store_metrics[store_name] = {
                    "total_processed": 0,
                    "total_errors": 0,
                    "job_count": 0
                }
            
            store_metrics[store_name]["total_processed"] += metric.get("products_processed", 0)
            store_metrics[store_name]["total_errors"] += metric.get("errors_count", 0)
            store_metrics[store_name]["job_count"] += 1
        
        # Convert to ChartData format
        chart_data = []
        for store_name, metrics in store_metrics.items():
            # Calculate performance score based on processed vs errors
            processed = metrics["total_processed"]
            errors = metrics["total_errors"]
            
            if processed > 0:
                success_rate = ((processed - errors) / processed) * 100
                change = success_rate - 90  # Compare to 90% baseline
            else:
                success_rate = 0
                change = -90
            
            chart_data.append(ChartData(
                label=store_name,
                value=int(success_rate),
                change=round(change, 1)
            ))
        
        return chart_data
        
    except Exception as e:
        logger.error(f"Error fetching store performance: {e}")
        return []

@router.get("/price-trends", response_model=List[Dict[str, Any]])
async def get_price_trends(time_range: str = "24h", db: SupabaseClient = Depends(get_db_dependency)):
    """Get price trend data"""
    try:
        # For now, return placeholder data since we need more complex queries
        # This would require analyzing price_history table
        return [
            {"date": "2024-01-01", "average_price": 2.50, "store": "Albert Heijn"},
            {"date": "2024-01-02", "average_price": 2.45, "store": "Albert Heijn"},
            {"date": "2024-01-03", "average_price": 2.48, "store": "Albert Heijn"},
        ]
        
    except Exception as e:
        logger.error(f"Error fetching price trends: {e}")
        return []

@router.get("/recent-activity")
async def get_recent_activity(limit: int = 10, db: SupabaseClient = Depends(get_db_dependency)):
    """Get recent system activity"""
    try:
        # Get recent system logs
        logs = await db.get_system_logs(limit=limit)
        
        activities = []
        for log in logs:
            activities.append({
                "id": log["id"],
                "type": log["level"],
                "message": log["message"],
                "component": log.get("component", "system"),
                "timestamp": log["created_at"]
            })
        
        return {"activities": activities}
        
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        return {"activities": []}

@router.get("/stores")
async def get_stores_status(db: SupabaseClient = Depends(get_db_dependency)):
    """Get stores status information"""
    try:
        stores = await db.get_stores()
        
        store_statuses = []
        for store in stores:
            # Get recent jobs for this store
            recent_jobs = await db.get_recent_jobs(limit=5)
            store_jobs = [job for job in recent_jobs if job.get("store_id") == store["id"]]
            
            # Determine status
            status = "idle"
            last_scrape = "Never"
            
            if store_jobs:
                latest_job = store_jobs[0]
                if latest_job.get("status") == "running":
                    status = "active"
                elif latest_job.get("status") == "failed":
                    status = "error"
                
                if latest_job.get("completed_at"):
                    last_scrape_time = datetime.fromisoformat(latest_job["completed_at"].replace("Z", "+00:00"))
                    time_diff = datetime.now() - last_scrape_time.replace(tzinfo=None)
                    if time_diff.days > 0:
                        last_scrape = f"{time_diff.days} days ago"
                    elif time_diff.seconds > 3600:
                        last_scrape = f"{time_diff.seconds // 3600} hours ago"
                    else:
                        last_scrape = f"{time_diff.seconds // 60} minutes ago"
            
            store_statuses.append({
                "id": store["id"],
                "name": store["name"],
                "slug": store["slug"],
                "status": status,
                "last_scrape": last_scrape,
                "is_active": store.get("is_active", True)
            })
        
        return {"stores": store_statuses}
        
    except Exception as e:
        logger.error(f"Error fetching stores status: {e}")
        return {"stores": []} 