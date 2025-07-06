"""
WebSocket Connection Manager
Handles real-time updates for dashboard metrics and job progress
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from database.client import get_database
from job_queue.job_manager import get_job_queue

logger = logging.getLogger(__name__)

class WebSocketMessage(BaseModel):
    """WebSocket message model"""
    type: str
    data: Dict[str, Any]
    timestamp: str = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        super().__init__(**data)

class ConnectionManager:
    """Manages WebSocket connections and real-time updates"""
    
    def __init__(self):
        # Active connections grouped by subscription type
        self.active_connections: Dict[str, Set[WebSocket]] = {
            'dashboard': set(),
            'jobs': set(),
            'agents': set(),
            'system': set()
        }
        
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
        # Update intervals (in seconds)
        self.update_intervals = {
            'dashboard_metrics': 5,
            'job_progress': 2,
            'system_health': 10
        }
        
        # Background tasks
        self.background_tasks: Dict[str, asyncio.Task] = {}
        
        # Last update timestamps
        self.last_updates: Dict[str, datetime] = {}
        
        self.running = False
        
    async def start(self):
        """Start background update tasks"""
        if self.running:
            return
            
        self.running = True
        logger.info("🚀 Starting WebSocket connection manager...")
        
        # Start background update tasks
        self.background_tasks['dashboard'] = asyncio.create_task(self._dashboard_update_loop())
        self.background_tasks['jobs'] = asyncio.create_task(self._jobs_update_loop())
        self.background_tasks['system'] = asyncio.create_task(self._system_update_loop())
        
        logger.info("✅ WebSocket connection manager started")
    
    async def stop(self):
        """Stop background update tasks"""
        if not self.running:
            return
            
        self.running = False
        logger.info("🛑 Stopping WebSocket connection manager...")
        
        # Cancel background tasks
        for task_name, task in self.background_tasks.items():
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close all connections
        for connection_type, connections in self.active_connections.items():
            for websocket in connections.copy():
                try:
                    await websocket.close()
                except:
                    pass
        
        self.active_connections.clear()
        self.connection_metadata.clear()
        
        logger.info("✅ WebSocket connection manager stopped")
    
    async def connect(self, websocket: WebSocket, connection_type: str = 'dashboard', metadata: Dict[str, Any] = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        if connection_type not in self.active_connections:
            self.active_connections[connection_type] = set()
        
        self.active_connections[connection_type].add(websocket)
        self.connection_metadata[websocket] = {
            'type': connection_type,
            'connected_at': datetime.now(),
            'metadata': metadata or {}
        }
        
        logger.info(f"📡 New {connection_type} WebSocket connection established")
        
        # Send initial data
        await self._send_initial_data(websocket, connection_type)
        
        # Start background tasks if not already running
        if not self.running:
            await self.start()
    
    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        connection_info = self.connection_metadata.get(websocket, {})
        connection_type = connection_info.get('type', 'unknown')
        
        # Remove from active connections
        for conn_type, connections in self.active_connections.items():
            if websocket in connections:
                connections.remove(websocket)
                break
        
        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        logger.info(f"📡 {connection_type} WebSocket connection disconnected")
    
    async def send_personal_message(self, message: WebSocketMessage, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message.json())
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            await self.disconnect(websocket)
    
    async def broadcast_to_type(self, message: WebSocketMessage, connection_type: str):
        """Broadcast message to all connections of a specific type"""
        if connection_type not in self.active_connections:
            return
        
        connections = self.active_connections[connection_type].copy()
        
        for websocket in connections:
            try:
                await websocket.send_text(message.json())
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_type}: {e}")
                await self.disconnect(websocket)
    
    async def broadcast_to_all(self, message: WebSocketMessage):
        """Broadcast message to all active connections"""
        for connection_type in self.active_connections:
            await self.broadcast_to_type(message, connection_type)
    
    async def _send_initial_data(self, websocket: WebSocket, connection_type: str):
        """Send initial data when connection is established"""
        try:
            if connection_type == 'dashboard':
                await self._send_dashboard_data(websocket)
            elif connection_type == 'jobs':
                await self._send_jobs_data(websocket)
            elif connection_type == 'agents':
                await self._send_agents_data(websocket)
            elif connection_type == 'system':
                await self._send_system_data(websocket)
        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
    
    async def _send_dashboard_data(self, websocket: WebSocket):
        """Send dashboard metrics data"""
        try:
            db = await get_database()
            
            # Get system metrics
            system_metrics = await self._get_system_metrics()
            
            # Get recent jobs summary
            recent_jobs = await db.get_recent_jobs(limit=10)
            
            # Get active jobs count
            active_jobs = await db.get_active_jobs()
            
            message = WebSocketMessage(
                type="dashboard_update",
                data={
                    "system_metrics": system_metrics,
                    "recent_jobs": recent_jobs,
                    "active_jobs_count": len(active_jobs),
                    "last_updated": datetime.now().isoformat()
                }
            )
            
            await self.send_personal_message(message, websocket)
            
        except Exception as e:
            logger.error(f"Error sending dashboard data: {e}")
    
    async def _send_jobs_data(self, websocket: WebSocket):
        """Send jobs data"""
        try:
            db = await get_database()
            queue = await get_job_queue()
            
            # Get recent jobs
            recent_jobs = await db.get_recent_jobs(limit=20)
            
            # Get queue statistics
            queue_stats = await queue.get_queue_stats()
            
            message = WebSocketMessage(
                type="jobs_update",
                data={
                    "recent_jobs": recent_jobs,
                    "queue_stats": queue_stats,
                    "last_updated": datetime.now().isoformat()
                }
            )
            
            await self.send_personal_message(message, websocket)
            
        except Exception as e:
            logger.error(f"Error sending jobs data: {e}")
    
    async def _send_agents_data(self, websocket: WebSocket):
        """Send agents status data"""
        try:
            db = await get_database()
            
            # Get stores and their recent activity
            stores = await db.get_stores()
            agents_data = []
            
            for store in stores:
                recent_jobs = await db.get_recent_jobs(limit=5)
                store_jobs = [job for job in recent_jobs if job.get("store_id") == store["id"]]
                
                # Calculate status
                status = "idle"
                if store_jobs:
                    latest_job = store_jobs[0]
                    if latest_job.get("status") == "running":
                        status = "running"
                    elif latest_job.get("status") == "pending":
                        status = "queued"
                
                agents_data.append({
                    "store_id": store["id"],
                    "store_name": store["name"],
                    "store_slug": store["slug"],
                    "status": status,
                    "recent_jobs": len(store_jobs),
                    "is_active": store.get("is_active", True)
                })
            
            message = WebSocketMessage(
                type="agents_update",
                data={
                    "agents": agents_data,
                    "last_updated": datetime.now().isoformat()
                }
            )
            
            await self.send_personal_message(message, websocket)
            
        except Exception as e:
            logger.error(f"Error sending agents data: {e}")
    
    async def _send_system_data(self, websocket: WebSocket):
        """Send system health data"""
        try:
            system_health = await self._get_system_health()
            
            message = WebSocketMessage(
                type="system_update",
                data={
                    "system_health": system_health,
                    "last_updated": datetime.now().isoformat()
                }
            )
            
            await self.send_personal_message(message, websocket)
            
        except Exception as e:
            logger.error(f"Error sending system data: {e}")
    
    async def _dashboard_update_loop(self):
        """Background task to update dashboard data"""
        while self.running:
            try:
                if self.active_connections['dashboard']:
                    # Get updated dashboard data
                    db = await get_database()
                    
                    # Get system metrics
                    system_metrics = await self._get_system_metrics()
                    
                    # Get recent jobs
                    recent_jobs = await db.get_recent_jobs(limit=10)
                    
                    # Get active jobs
                    active_jobs = await db.get_active_jobs()
                    
                    message = WebSocketMessage(
                        type="dashboard_update",
                        data={
                            "system_metrics": system_metrics,
                            "recent_jobs": recent_jobs,
                            "active_jobs_count": len(active_jobs),
                            "last_updated": datetime.now().isoformat()
                        }
                    )
                    
                    await self.broadcast_to_type(message, 'dashboard')
                
                await asyncio.sleep(self.update_intervals['dashboard_metrics'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in dashboard update loop: {e}")
                await asyncio.sleep(5)
    
    async def _jobs_update_loop(self):
        """Background task to update jobs data"""
        while self.running:
            try:
                if self.active_connections['jobs']:
                    db = await get_database()
                    queue = await get_job_queue()
                    
                    # Get recent jobs
                    recent_jobs = await db.get_recent_jobs(limit=20)
                    
                    # Get queue statistics
                    queue_stats = await queue.get_queue_stats()
                    
                    message = WebSocketMessage(
                        type="jobs_update",
                        data={
                            "recent_jobs": recent_jobs,
                            "queue_stats": queue_stats,
                            "last_updated": datetime.now().isoformat()
                        }
                    )
                    
                    await self.broadcast_to_type(message, 'jobs')
                
                await asyncio.sleep(self.update_intervals['job_progress'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in jobs update loop: {e}")
                await asyncio.sleep(5)
    
    async def _system_update_loop(self):
        """Background task to update system health data"""
        while self.running:
            try:
                if self.active_connections['system']:
                    system_health = await self._get_system_health()
                    
                    message = WebSocketMessage(
                        type="system_update",
                        data={
                            "system_health": system_health,
                            "last_updated": datetime.now().isoformat()
                        }
                    )
                    
                    await self.broadcast_to_type(message, 'system')
                
                await asyncio.sleep(self.update_intervals['system_health'])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in system update loop: {e}")
                await asyncio.sleep(10)
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory_percent,
                "disk_usage": round(disk_percent, 2),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            health_data = {
                "services": {},
                "overall_status": "healthy",
                "checks": []
            }
            
            # Check database connectivity
            try:
                db = await get_database()
                db_health = await db.health_check()
                health_data["services"]["database"] = db_health
                health_data["checks"].append({
                    "name": "Database",
                    "status": db_health["status"],
                    "message": db_health.get("message", "OK")
                })
            except Exception as e:
                health_data["services"]["database"] = {"status": "unhealthy", "error": str(e)}
                health_data["checks"].append({
                    "name": "Database",
                    "status": "unhealthy",
                    "message": str(e)
                })
                health_data["overall_status"] = "unhealthy"
            
            # Check job queue
            try:
                queue = await get_job_queue()
                queue_stats = await queue.get_queue_stats()
                health_data["services"]["job_queue"] = {
                    "status": "healthy",
                    "stats": queue_stats
                }
                health_data["checks"].append({
                    "name": "Job Queue",
                    "status": "healthy",
                    "message": f"Queue operational"
                })
            except Exception as e:
                health_data["services"]["job_queue"] = {"status": "unhealthy", "error": str(e)}
                health_data["checks"].append({
                    "name": "Job Queue",
                    "status": "unhealthy",
                    "message": str(e)
                })
                health_data["overall_status"] = "degraded"
            
            # Add system metrics
            health_data["metrics"] = await self._get_system_metrics()
            
            return health_data
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "services": {},
                "overall_status": "unhealthy",
                "checks": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def notify_job_update(self, job_id: str, job_data: Dict[str, Any]):
        """Notify about job status update"""
        message = WebSocketMessage(
            type="job_progress",
            data={
                "job_id": job_id,
                "job_data": job_data,
                "event": "job_update"
            }
        )
        
        await self.broadcast_to_type(message, 'jobs')
        await self.broadcast_to_type(message, 'dashboard')
    
    async def notify_agent_update(self, store_slug: str, agent_data: Dict[str, Any]):
        """Notify about agent status update"""
        message = WebSocketMessage(
            type="agent_status",
            data={
                "store_slug": store_slug,
                "agent_data": agent_data,
                "event": "agent_update"
            }
        )
        
        await self.broadcast_to_type(message, 'agents')
        await self.broadcast_to_type(message, 'dashboard')
    
    async def notify_system_alert(self, alert_type: str, message_text: str, severity: str = "info"):
        """Notify about system alerts"""
        message = WebSocketMessage(
            type="system_alert",
            data={
                "alert_type": alert_type,
                "message": message_text,
                "severity": severity,
                "event": "system_alert"
            }
        )
        
        await self.broadcast_to_all(message)
    
    def get_connection_count(self) -> Dict[str, int]:
        """Get count of active connections by type"""
        return {
            conn_type: len(connections)
            for conn_type, connections in self.active_connections.items()
        }
    
    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())

# Global connection manager instance
connection_manager = ConnectionManager()

# Convenience functions
async def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance"""
    return connection_manager

async def notify_job_update(job_id: str, job_data: Dict[str, Any]):
    """Convenience function to notify about job updates"""
    await connection_manager.notify_job_update(job_id, job_data)

async def notify_agent_update(store_slug: str, agent_data: Dict[str, Any]):
    """Convenience function to notify about agent updates"""
    await connection_manager.notify_agent_update(store_slug, agent_data)

async def notify_system_alert(alert_type: str, message: str, severity: str = "info"):
    """Convenience function to notify about system alerts"""
    await connection_manager.notify_system_alert(alert_type, message, severity) 