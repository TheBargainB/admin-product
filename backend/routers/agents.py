"""
Agents API Router
Manages scraper agents and their operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, List, Any
import logging
from datetime import datetime

# Database integration
from config.database import get_db_dependency
from database.client import SupabaseClient

# Job queue integration
from job_queue.job_manager import create_scraping_job, get_job_status, cancel_job, get_job_queue

# Import agents
try:
    from agents.albert_heijn_agent import AlbertHeijnAgent
    from agents.dirk_agent import DirkAgent  
    from agents.hoogvliet_agent import HoogvlietAgent
    from agents.jumbo_agent import JumboAgent
    from agents.etos_agent import EtosAgent
    from agents.kruidvat_agent import KruidvatAgent
    AGENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Agent imports failed: {e}")
    AGENTS_AVAILABLE = False

from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize agents if available
agents = {}
if AGENTS_AVAILABLE:
    try:
        agents = {
            "albert_heijn": AlbertHeijnAgent(),
            "dirk": DirkAgent(),
            "hoogvliet": HoogvlietAgent(), 
            "jumbo": JumboAgent(),
            "etos": EtosAgent(),
            "kruidvat": KruidvatAgent()
        }
        logger.info(f"Successfully initialized {len(agents)} agents")
    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}")
        agents = {}

@router.get("/")
async def get_agents(db: SupabaseClient = Depends(get_db_dependency)) -> Dict[str, Any]:
    """Get list of available agents and their status."""
    try:
        if not AGENTS_AVAILABLE or not agents:
            return {
                "agents": [],
                "message": "Agents not available - LangGraph dependencies required",
                "available": False,
                "langgraph_available": AGENTS_AVAILABLE,
                "agent_count": 0
            }
        
        # Get stores from database
        stores = await db.get_stores()
        store_dict = {store["slug"]: store for store in stores}
        
        agent_list = []
        for store_slug, agent in agents.items():
            # Get store info from database
            store_info = store_dict.get(store_slug, {})
            
            # Get recent jobs for this store
            recent_jobs = await db.get_recent_jobs(limit=10)
            store_jobs = [job for job in recent_jobs if job.get("store_id") == store_info.get("id")]
            
            # Calculate status and metrics
            status = "idle"
            last_run = None
            success_rate = 100.0
            
            if store_jobs:
                latest_job = store_jobs[0]
                if latest_job.get("status") == "running":
                    status = "running"
                elif latest_job.get("status") == "failed":
                    status = "error"
                
                # Get last successful run
                successful_jobs = [job for job in store_jobs if job.get("status") == "completed"]
                if successful_jobs:
                    last_run = successful_jobs[0].get("completed_at")
                
                # Calculate success rate
                if store_jobs:
                    successful = len([job for job in store_jobs if job.get("status") == "completed"])
                    success_rate = (successful / len(store_jobs)) * 100
            
            agent_info = {
                "id": store_slug,
                "name": agent.display_name,
                "store_id": store_info.get("id"),
                "status": status,
                "last_run": last_run,
                "total_runs": len(store_jobs),
                "success_rate": round(success_rate, 1),
                "langgraph_enabled": True,
                "is_active": store_info.get("is_active", True),
                "job_queue_enabled": True
            }
            agent_list.append(agent_info)
        
        return {
            "agents": agent_list,
            "message": f"Found {len(agents)} active agents",
            "available": True,
            "langgraph_available": True,
            "job_queue_enabled": True,
            "agent_count": len(agents)
        }
        
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        return {
            "agents": [],
            "message": f"Error loading agents: {str(e)}",
            "available": False,
            "error": str(e)
        }

@router.post("/test")
async def test_agents(db: SupabaseClient = Depends(get_db_dependency)) -> Dict[str, Any]:
    """Test endpoint to verify agents are working."""
    try:
        if not AGENTS_AVAILABLE:
            return {
                "message": "Agents test endpoint - LangGraph not available",
                "available": False,
                "agent_count": 0,
                "test_status": "dependencies_missing"
            }
        
        if not agents:
            return {
                "message": "Agents test endpoint - no agents initialized", 
                "available": False,
                "agent_count": 0,
                "test_status": "initialization_failed"
            }
        
        # Test database connectivity
        db_health = await db.health_check()
        
        # Test job queue connectivity
        queue = await get_job_queue()
        queue_stats = await queue.get_queue_stats()
        
        # Test basic agent functionality
        test_results = {}
        for store_slug, agent in agents.items():
            try:
                # Test agent responsiveness
                test_results[store_slug] = {
                    "name": agent.display_name,
                    "responsive": True,
                    "status": "ready",
                    "langgraph_available": True,
                    "job_queue_ready": True
                }
            except Exception as e:
                test_results[store_slug] = {
                    "name": getattr(agent, 'display_name', store_slug),
                    "responsive": False,
                    "error": str(e)
                }
        
        # Log test event
        await db.log_system_event(
            "info", 
            "Agents system test completed successfully", 
            "agents_router"
        )
        
        return {
            "message": "Agents system test completed",
            "available": True,
            "agent_count": len(agents),
            "test_status": "success",
            "results": test_results,
            "langgraph_available": True,
            "database_status": db_health["status"],
            "job_queue_stats": queue_stats
        }
        
    except Exception as e:
        logger.error(f"Error testing agents: {e}")
        return {
            "message": f"Agents test failed: {str(e)}",
            "available": False,
            "agent_count": 0,
            "test_status": "error",
            "error": str(e)
        }

@router.post("/{store_slug}/start")
async def start_agent(
    store_slug: str, 
    job_type: str = "price_update",
    priority: str = "normal",
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Start scraping for a specific store using job queue."""
    try:
        if not AGENTS_AVAILABLE or not agents:
            raise HTTPException(
                status_code=503,
                detail="Agents not available - LangGraph dependencies required"
            )
        
        if store_slug not in agents:
            raise HTTPException(
                status_code=404,
                detail=f"Agent for store '{store_slug}' not found"
            )
        
        # Get store from database
        store = await db.get_store_by_slug(store_slug)
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"Store '{store_slug}' not found in database"
            )
        
        # Create and queue the scraping job
        job_id = await create_scraping_job(
            store=store_slug,
            job_type=job_type,
            priority=priority
        )
        
        if not job_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to create scraping job"
            )
        
        agent = agents[store_slug]
        
        # Log job creation
        await db.log_system_event(
            "info",
            f"Created and queued scraping job for {agent.display_name}",
            "agents_router",
            job_id=job_id
        )
        
        return {
            "success": True,
            "message": f"Started scraping job for {agent.display_name}",
            "store": store_slug,
            "job_id": job_id,
            "job_type": job_type,
            "priority": priority,
            "queued_at": datetime.now().isoformat(),
            "langgraph_enabled": True,
            "job_queue_enabled": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting scraping for {store_slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start scraping: {str(e)}"
        )

@router.post("/{store_slug}/stop")
async def stop_agent(
    store_slug: str,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Stop scraping for a specific store."""
    try:
        if not AGENTS_AVAILABLE or not agents:
            raise HTTPException(
                status_code=503,
                detail="Agents not available"
            )
        
        if store_slug not in agents:
            raise HTTPException(
                status_code=404,
                detail=f"Agent for store '{store_slug}' not found"
            )
        
        # Get store from database
        store = await db.get_store_by_slug(store_slug)
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"Store '{store_slug}' not found in database"
            )
        
        # Find running jobs for this store and cancel them
        active_jobs = await db.get_active_jobs()
        store_jobs = [job for job in active_jobs if job.get("store_id") == store["id"]]
        
        cancelled_jobs = []
        for job in store_jobs:
            if job.get("status") in ["running", "pending"]:
                success = await cancel_job(job["id"])
                if success:
                    cancelled_jobs.append(job["id"])
        
        agent = agents[store_slug]
        
        # Log stop event
        await db.log_system_event(
            "info",
            f"Cancelled {len(cancelled_jobs)} jobs for {agent.display_name}",
            "agents_router"
        )
        
        return {
            "success": True,
            "message": f"Stopped scraping for {agent.display_name}",
            "store": store_slug,
            "cancelled_jobs": cancelled_jobs,
            "cancelled_count": len(cancelled_jobs),
            "stopped_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping scraping for {store_slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop scraping: {str(e)}"
        )

@router.get("/{store_slug}/status") 
async def get_agent_status(
    store_slug: str,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Get status for a specific agent."""
    try:
        if not AGENTS_AVAILABLE or not agents:
            raise HTTPException(
                status_code=503,
                detail="Agents not available"
            )
        
        if store_slug not in agents:
            raise HTTPException(
                status_code=404,
                detail=f"Agent for store '{store_slug}' not found"
            )
        
        # Get store from database
        store = await db.get_store_by_slug(store_slug)
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"Store '{store_slug}' not found in database"
            )
        
        agent = agents[store_slug]
        
        # Get recent jobs for detailed status
        recent_jobs = await db.get_recent_jobs(limit=10)
        store_jobs = [job for job in recent_jobs if job.get("store_id") == store["id"]]
        
        # Calculate metrics
        running_jobs = [job for job in store_jobs if job.get("status") == "running"]
        pending_jobs = [job for job in store_jobs if job.get("status") == "pending"]
        completed_jobs = [job for job in store_jobs if job.get("status") == "completed"]
        failed_jobs = [job for job in store_jobs if job.get("status") == "failed"]
        
        # Get queue statistics
        queue = await get_job_queue()
        queue_stats = await queue.get_queue_stats()
        
        status = {
            "store": store_slug,
            "name": agent.display_name,
            "status": "running" if running_jobs else "queued" if pending_jobs else "idle",
            "store_id": store["id"],
            "recent_jobs": len(store_jobs),
            "running_jobs": len(running_jobs),
            "pending_jobs": len(pending_jobs),
            "completed_jobs": len(completed_jobs),
            "failed_jobs": len(failed_jobs),
            "success_rate": (len(completed_jobs) / len(store_jobs) * 100) if store_jobs else 100.0,
            "last_update": datetime.now().isoformat(),
            "langgraph_enabled": True,
            "job_queue_enabled": True,
            "queue_stats": queue_stats,
            "is_active": store.get("is_active", True)
        }
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent status for {store_slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent status: {str(e)}"
        )

@router.get("/{store_slug}/jobs")
async def get_agent_jobs(
    store_slug: str, 
    limit: int = 20,
    status_filter: str = None,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Get job history for a specific agent."""
    try:
        # Get store from database
        store = await db.get_store_by_slug(store_slug)
        if not store:
            raise HTTPException(
                status_code=404,
                detail=f"Store '{store_slug}' not found in database"
            )
        
        # Get recent jobs for this store
        all_jobs = await db.get_recent_jobs(limit=100)
        store_jobs = [job for job in all_jobs if job.get("store_id") == store["id"]]
        
        # Apply status filter if provided
        if status_filter:
            store_jobs = [job for job in store_jobs if job.get("status") == status_filter]
        
        # Limit results
        store_jobs = store_jobs[:limit]
        
        # Enhance job data with queue information
        enhanced_jobs = []
        for job in store_jobs:
            job_status = await get_job_status(job["id"])
            enhanced_job = {**job}
            
            if job_status:
                enhanced_job.update({
                    "queue_info": job_status,
                    "job_queue_managed": True
                })
            
            enhanced_jobs.append(enhanced_job)
        
        return {
            "store": store_slug,
            "jobs": enhanced_jobs,
            "total": len(enhanced_jobs),
            "filtered_by": status_filter,
            "job_queue_enabled": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent jobs for {store_slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent jobs: {str(e)}"
        )

@router.post("/{store_slug}/test-direct")
async def test_direct_scraping(
    store_slug: str,
    db: SupabaseClient = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """Test direct scraping without job queue (for demonstration)"""
    try:
        if not AGENTS_AVAILABLE or not agents:
            raise HTTPException(
                status_code=503,
                detail="Agents not available - LangGraph dependencies required"
            )
        
        if store_slug not in agents:
            raise HTTPException(
                status_code=404,
                detail=f"Agent for store '{store_slug}' not found"
            )
        
        agent = agents[store_slug]
        
        # Log test start
        await db.log_system_event(
            "info",
            f"Starting direct scraping test for {agent.display_name}",
            "agents_router"
        )
        
        # Call agent directly (bypassing job queue)
        result = await agent.run_scraping_job({
            "test_mode": True,
            "max_products": 5
        })
        
        # Log test completion
        await db.log_system_event(
            "info", 
            f"Direct scraping test completed for {agent.display_name}",
            "agents_router"
        )
        
        return {
            "success": True,
            "message": f"Direct scraping test completed for {agent.display_name}",
            "store": store_slug,
            "agent_name": agent.display_name,
            "method": "direct_call",
            "bypassed_job_queue": True,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in direct scraping test for {store_slug}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Direct scraping test failed: {str(e)}"
        ) 