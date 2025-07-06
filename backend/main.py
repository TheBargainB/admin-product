"""
FastAPI Main Application
BargainB - Grocery Price Scraping Admin Panel Backend
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database initialization
from config.database import init_db, close_db

# WebSocket connection manager
from websocket.connection_manager import get_connection_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the FastAPI application."""
    # Startup
    logger.info("🚀 Starting BargainB Admin Panel API...")
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    
    # Start WebSocket connection manager
    try:
        connection_manager = await get_connection_manager()
        await connection_manager.start()
        logger.info("✅ WebSocket connection manager started")
    except Exception as e:
        logger.error(f"❌ WebSocket manager initialization failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down BargainB Admin Panel API...")
    try:
        # Stop WebSocket connection manager
        connection_manager = await get_connection_manager()
        await connection_manager.stop()
        logger.info("✅ WebSocket connection manager stopped")
    except Exception as e:
        logger.error(f"❌ WebSocket manager shutdown failed: {e}")
    
    try:
        await close_db()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Database shutdown failed: {e}")

# Create FastAPI app with lifespan
app = FastAPI(
    title="BargainB Admin Panel API",
    description="Backend API for Dutch grocery price scraping system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from routers import dashboard, agents, jobs, monitoring, scheduling

# Include API routers
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(scheduling.router, tags=["scheduling"])

# WebSocket endpoints
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for dashboard real-time updates"""
    connection_manager = await get_connection_manager()
    
    try:
        await connection_manager.connect(websocket, "dashboard")
        
        while True:
            # Keep connection alive and handle incoming messages
            try:
                data = await websocket.receive_text()
                # Handle any client messages if needed
                logger.debug(f"Received dashboard message: {data}")
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Dashboard WebSocket error: {e}")
    finally:
        await connection_manager.disconnect(websocket)

@app.websocket("/ws/jobs")
async def websocket_jobs(websocket: WebSocket):
    """WebSocket endpoint for jobs real-time updates"""
    connection_manager = await get_connection_manager()
    
    try:
        await connection_manager.connect(websocket, "jobs")
        
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received jobs message: {data}")
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Jobs WebSocket error: {e}")
    finally:
        await connection_manager.disconnect(websocket)

@app.websocket("/ws/agents")
async def websocket_agents(websocket: WebSocket):
    """WebSocket endpoint for agents real-time updates"""
    connection_manager = await get_connection_manager()
    
    try:
        await connection_manager.connect(websocket, "agents")
        
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received agents message: {data}")
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Agents WebSocket error: {e}")
    finally:
        await connection_manager.disconnect(websocket)

@app.websocket("/ws/system")
async def websocket_system(websocket: WebSocket):
    """WebSocket endpoint for system health real-time updates"""
    connection_manager = await get_connection_manager()
    
    try:
        await connection_manager.connect(websocket, "system")
        
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received system message: {data}")
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"System WebSocket error: {e}")
    finally:
        await connection_manager.disconnect(websocket)

# Root endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "BargainB Admin Panel API",
        "version": "1.0.0",
        "description": "Backend API for Dutch grocery price scraping system",
        "features": [
            "LangGraph-powered intelligent agents",
            "Real-time dashboard updates",
            "Background job processing with Redis",
            "WebSocket real-time monitoring",
            "Supabase database integration"
        ],
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "dashboard_api": "/api/dashboard",
            "agents_api": "/api/agents",
            "jobs_api": "/api/jobs",
            "monitoring_api": "/api/monitoring"
        },
        "websockets": {
            "dashboard": "/ws/dashboard",
            "jobs": "/ws/jobs",
            "agents": "/ws/agents",
            "system": "/ws/system"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        from database.client import get_database
        from websocket.connection_manager import get_connection_manager
        from job_queue.job_manager import get_job_queue
        
        # Check database
        db = await get_database()
        db_health = await db.health_check()
        
        # Check WebSocket connections
        connection_manager = await get_connection_manager()
        ws_connections = connection_manager.get_connection_count()
        
        # Check job queue
        queue = await get_job_queue()
        queue_stats = await queue.get_queue_stats()
        
        health_status = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",  # Will be replaced with actual timestamp
            "services": {
                "database": db_health,
                "websockets": {
                    "status": "healthy",
                    "connections": ws_connections,
                    "total_connections": sum(ws_connections.values())
                },
                "job_queue": {
                    "status": "healthy",
                    "stats": queue_stats
                }
            },
            "version": "1.0.0"
        }
        
        # Update timestamp
        from datetime import datetime
        health_status["timestamp"] = datetime.now().isoformat()
        
        # Check if any service is unhealthy
        if db_health.get("status") != "healthy":
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-01-01T00:00:00Z"  # Will be replaced
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 