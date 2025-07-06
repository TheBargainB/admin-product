from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum
import psutil
import asyncio
from config.database import get_db
from utils.logging import get_logger

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])
logger = get_logger(__name__)

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class LogEntry(BaseModel):
    id: str
    timestamp: datetime
    level: LogLevel
    message: str
    component: str
    store_id: Optional[str] = None
    job_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class Alert(BaseModel):
    id: str
    title: str
    message: str
    severity: AlertSeverity
    component: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    is_resolved: bool = False
    metadata: Optional[Dict[str, Any]] = None

class PerformanceMetric(BaseModel):
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Optional[Dict[str, str]] = None

class SystemStatus(BaseModel):
    status: str
    uptime: float
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_status: str
    database_status: str
    active_connections: int
    last_updated: datetime

@router.get("/logs", response_model=List[LogEntry])
async def get_logs(
    level: Optional[LogLevel] = None,
    component: Optional[str] = None,
    store_id: Optional[str] = None,
    job_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db=Depends(get_db)
):
    """Get system logs with filtering options"""
    try:
        # Mock log data
        mock_logs = [
            LogEntry(
                id="log_001",
                timestamp=datetime.now() - timedelta(minutes=2),
                level=LogLevel.INFO,
                message="Albert Heijn price update completed successfully",
                component="scraper",
                store_id="store_001",
                job_id="job_001",
                metadata={"products_updated": 29450, "duration": 1800}
            ),
            LogEntry(
                id="log_002",
                timestamp=datetime.now() - timedelta(minutes=5),
                level=LogLevel.INFO,
                message="Started Dirk product catalog sync",
                component="scraper",
                store_id="store_002",
                job_id="job_002",
                metadata={"products_total": 32145}
            ),
            LogEntry(
                id="log_003",
                timestamp=datetime.now() - timedelta(minutes=8),
                level=LogLevel.WARNING,
                message="Hoogvliet scraper encountered rate limit",
                component="scraper",
                store_id="store_003",
                job_id="job_003",
                metadata={"retry_after": 300, "attempts": 3}
            ),
            LogEntry(
                id="log_004",
                timestamp=datetime.now() - timedelta(minutes=10),
                level=LogLevel.ERROR,
                message="Database connection timeout",
                component="database",
                metadata={"connection_pool": "main", "timeout": 30}
            ),
            LogEntry(
                id="log_005",
                timestamp=datetime.now() - timedelta(minutes=12),
                level=LogLevel.INFO,
                message="Jumbo new products detected",
                component="processor",
                store_id="store_004",
                metadata={"new_products": 23, "categories": ["fresh", "dairy"]}
            ),
            LogEntry(
                id="log_006",
                timestamp=datetime.now() - timedelta(minutes=15),
                level=LogLevel.INFO,
                message="System health check completed",
                component="monitor",
                metadata={"cpu": 45.2, "memory": 68.1, "disk": 23.4}
            ),
            LogEntry(
                id="log_007",
                timestamp=datetime.now() - timedelta(minutes=18),
                level=LogLevel.CRITICAL,
                message="Failed to connect to Albert Heijn API",
                component="scraper",
                store_id="store_001",
                metadata={"error_code": "CONNECTION_REFUSED", "retry_count": 5}
            )
        ]
        
        # Apply filters
        filtered_logs = mock_logs
        
        if level:
            filtered_logs = [log for log in filtered_logs if log.level == level]
        if component:
            filtered_logs = [log for log in filtered_logs if log.component == component]
        if store_id:
            filtered_logs = [log for log in filtered_logs if log.store_id == store_id]
        if job_id:
            filtered_logs = [log for log in filtered_logs if log.job_id == job_id]
        if start_time:
            filtered_logs = [log for log in filtered_logs if log.timestamp >= start_time]
        if end_time:
            filtered_logs = [log for log in filtered_logs if log.timestamp <= end_time]
        
        # Apply pagination
        return filtered_logs[offset:offset + limit]
        
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch logs")

@router.get("/alerts", response_model=List[Alert])
async def get_alerts(
    severity: Optional[AlertSeverity] = None,
    component: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db=Depends(get_db)
):
    """Get system alerts with filtering options"""
    try:
        # Mock alert data
        mock_alerts = [
            Alert(
                id="alert_001",
                title="High Error Rate Detected",
                message="Hoogvliet scraper error rate exceeded 10% threshold",
                severity=AlertSeverity.HIGH,
                component="scraper",
                created_at=datetime.now() - timedelta(minutes=30),
                is_resolved=False,
                metadata={"store": "Hoogvliet", "error_rate": 15.2, "threshold": 10}
            ),
            Alert(
                id="alert_002",
                title="Database Connection Pool Exhausted",
                message="All database connections are in use",
                severity=AlertSeverity.CRITICAL,
                component="database",
                created_at=datetime.now() - timedelta(hours=1),
                resolved_at=datetime.now() - timedelta(minutes=45),
                is_resolved=True,
                metadata={"pool_size": 20, "active_connections": 20}
            ),
            Alert(
                id="alert_003",
                title="Memory Usage High",
                message="System memory usage exceeded 80%",
                severity=AlertSeverity.MEDIUM,
                component="system",
                created_at=datetime.now() - timedelta(minutes=15),
                is_resolved=False,
                metadata={"memory_usage": 85.3, "threshold": 80}
            ),
            Alert(
                id="alert_004",
                title="Job Queue Backlog",
                message="Job queue has more than 50 pending jobs",
                severity=AlertSeverity.MEDIUM,
                component="queue",
                created_at=datetime.now() - timedelta(minutes=20),
                is_resolved=False,
                metadata={"pending_jobs": 67, "threshold": 50}
            ),
            Alert(
                id="alert_005",
                title="Disk Space Low",
                message="Available disk space is below 20%",
                severity=AlertSeverity.LOW,
                component="system",
                created_at=datetime.now() - timedelta(hours=2),
                resolved_at=datetime.now() - timedelta(hours=1),
                is_resolved=True,
                metadata={"disk_usage": 85, "available": 15}
            )
        ]
        
        # Apply filters
        filtered_alerts = mock_alerts
        
        if severity:
            filtered_alerts = [alert for alert in filtered_alerts if alert.severity == severity]
        if component:
            filtered_alerts = [alert for alert in filtered_alerts if alert.component == component]
        if is_resolved is not None:
            filtered_alerts = [alert for alert in filtered_alerts if alert.is_resolved == is_resolved]
        
        # Apply pagination
        return filtered_alerts[offset:offset + limit]
        
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alerts")

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, db=Depends(get_db)):
    """Mark an alert as resolved"""
    try:
        # Mock alert resolution
        logger.info(f"Resolving alert {alert_id}")
        
        return {
            "message": "Alert resolved successfully",
            "alert_id": alert_id,
            "resolved_at": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")

@router.get("/metrics", response_model=List[PerformanceMetric])
async def get_performance_metrics(
    metric_name: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    db=Depends(get_db)
):
    """Get performance metrics"""
    try:
        # Generate mock metrics data
        now = datetime.now()
        metrics = []
        
        metric_names = ["cpu_usage", "memory_usage", "disk_usage", "network_throughput", "db_response_time"]
        
        if metric_name:
            metric_names = [metric_name] if metric_name in metric_names else []
        
        for i in range(min(limit, 50)):
            timestamp = now - timedelta(minutes=i * 5)
            
            for name in metric_names:
                if name == "cpu_usage":
                    value = 30 + (i % 20) + (i * 0.5)
                elif name == "memory_usage":
                    value = 50 + (i % 15) + (i * 0.3)
                elif name == "disk_usage":
                    value = 20 + (i % 10) + (i * 0.1)
                elif name == "network_throughput":
                    value = 100 + (i % 50) + (i * 2)
                elif name == "db_response_time":
                    value = 10 + (i % 30) + (i * 0.2)
                else:
                    value = i * 1.5
                
                metrics.append(PerformanceMetric(
                    name=name,
                    value=value,
                    unit="%" if name.endswith("_usage") else "ms" if name.endswith("_time") else "MB/s",
                    timestamp=timestamp,
                    tags={"component": "system"}
                ))
        
        # Apply time filters
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        return sorted(metrics, key=lambda x: x.timestamp, reverse=True)
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch metrics")

@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get overall system status"""
    try:
        # Get actual system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Mock some values
        uptime = psutil.boot_time()
        uptime_seconds = datetime.now().timestamp() - uptime
        
        return SystemStatus(
            status="healthy",
            uptime=uptime_seconds,
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            network_status="connected",
            database_status="connected",
            active_connections=15,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error fetching system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch system status")

@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    try:
        # Perform basic health checks
        cpu_ok = psutil.cpu_percent(interval=0.1) < 90
        memory_ok = psutil.virtual_memory().percent < 90
        disk_ok = psutil.disk_usage('/').percent < 90
        
        all_healthy = cpu_ok and memory_ok and disk_ok
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.now(),
            "checks": {
                "cpu": "ok" if cpu_ok else "warning",
                "memory": "ok" if memory_ok else "warning",
                "disk": "ok" if disk_ok else "warning",
                "database": "ok"  # Mock for now
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(),
            "error": str(e)
        }

@router.get("/components")
async def get_component_status(db=Depends(get_db)):
    """Get status of all system components"""
    try:
        components = [
            {
                "name": "scraper",
                "status": "healthy",
                "last_check": datetime.now() - timedelta(minutes=1),
                "uptime": 99.8,
                "active_jobs": 2,
                "error_rate": 0.2
            },
            {
                "name": "database",
                "status": "healthy",
                "last_check": datetime.now() - timedelta(seconds=30),
                "uptime": 99.9,
                "active_connections": 15,
                "response_time": 12.5
            },
            {
                "name": "queue",
                "status": "healthy",
                "last_check": datetime.now() - timedelta(minutes=2),
                "uptime": 99.7,
                "pending_jobs": 5,
                "processing_rate": 45
            },
            {
                "name": "api",
                "status": "healthy",
                "last_check": datetime.now() - timedelta(seconds=15),
                "uptime": 99.9,
                "requests_per_minute": 120,
                "avg_response_time": 150
            }
        ]
        
        return components
        
    except Exception as e:
        logger.error(f"Error fetching component status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch component status") 