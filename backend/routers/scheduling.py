"""
Scheduling Router
API endpoints for managing store scraping schedules.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from scheduler.store_scheduler import store_scheduler
from scheduler.schedule_config import ScheduleConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])

# Pydantic models
class ScheduleCreate(BaseModel):
    store_id: str = Field(..., description="Store UUID")
    schedule_type: str = Field(..., description="Type of schedule")
    cron_expression: str = Field(..., description="Cron expression")
    timezone: str = Field(default=ScheduleConfig.DEFAULT_TIMEZONE, description="Timezone")

class ScheduleUpdate(BaseModel):
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None

class ManualRunRequest(BaseModel):
    store_slug: str = Field(..., description="Store slug")
    schedule_type: str = Field(default="weekly_price_update", description="Type of scraping")

@router.on_event("startup")
async def startup_event():
    """Initialize the store scheduler on startup."""
    try:
        await store_scheduler.initialize()
        logger.info("Store scheduler initialized")
    except Exception as e:
        logger.error(f"Failed to initialize store scheduler: {str(e)}")

@router.on_event("shutdown")
async def shutdown_event():
    """Shutdown the store scheduler."""
    try:
        await store_scheduler.shutdown()
        logger.info("Store scheduler shutdown")
    except Exception as e:
        logger.error(f"Failed to shutdown store scheduler: {str(e)}")

@router.get("/schedules")
async def get_schedules(store_id: Optional[str] = None):
    """Get all schedules, optionally filtered by store."""
    try:
        schedules = await store_scheduler.get_schedules(store_id=store_id)
        return {"success": True, "data": schedules}
    except Exception as e:
        logger.error(f"Failed to get schedules: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schedules: {str(e)}"
        )

@router.post("/schedules")
async def create_schedule(schedule: ScheduleCreate):
    """Create a new schedule."""
    try:
        # Validate schedule type
        if schedule.schedule_type not in ScheduleConfig.SCHEDULE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid schedule type. Must be one of: {list(ScheduleConfig.SCHEDULE_TYPES.keys())}"
            )
        
        # Validate cron expression
        if not ScheduleConfig.validate_cron_expression(schedule.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression"
            )
        
        success = await store_scheduler.create_schedule(
            store_id=schedule.store_id,
            schedule_type=schedule.schedule_type,
            cron_expression=schedule.cron_expression,
            timezone=schedule.timezone
        )
        
        if success:
            return {"success": True, "message": "Schedule created successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create schedule"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create schedule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create schedule: {str(e)}"
        )

@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, updates: ScheduleUpdate):
    """Update an existing schedule."""
    try:
        # Validate cron expression if provided
        if updates.cron_expression and not ScheduleConfig.validate_cron_expression(updates.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression"
            )
        
        # Validate schedule type if provided
        if updates.schedule_type and updates.schedule_type not in ScheduleConfig.SCHEDULE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid schedule type. Must be one of: {list(ScheduleConfig.SCHEDULE_TYPES.keys())}"
            )
        
        # Convert to dict and remove None values
        update_data = {k: v for k, v in updates.dict().items() if v is not None}
        
        success = await store_scheduler.update_schedule(schedule_id, **update_data)
        
        if success:
            return {"success": True, "message": "Schedule updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found or update failed"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schedule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update schedule: {str(e)}"
        )

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Delete a schedule."""
    try:
        success = await store_scheduler.delete_schedule(schedule_id)
        
        if success:
            return {"success": True, "message": "Schedule deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found or delete failed"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schedule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete schedule: {str(e)}"
        )

@router.post("/schedules/manual-run")
async def trigger_manual_run(request: ManualRunRequest):
    """Trigger a manual run of a scraper."""
    try:
        success = await store_scheduler.trigger_manual_run(
            store_slug=request.store_slug,
            schedule_type=request.schedule_type
        )
        
        if success:
            return {"success": True, "message": f"Manual {request.schedule_type} triggered for {request.store_slug}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to trigger manual run"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger manual run: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger manual run: {str(e)}"
        )

@router.get("/config")
async def get_schedule_config():
    """Get scheduling configuration options."""
    try:
        return {
            "success": True,
            "data": {
                "schedule_types": ScheduleConfig.SCHEDULE_TYPES,
                "common_patterns": ScheduleConfig.COMMON_PATTERNS,
                "default_timezone": ScheduleConfig.DEFAULT_TIMEZONE,
                "default_schedules": ScheduleConfig.DEFAULT_SCHEDULES
            }
        }
    except Exception as e:
        logger.error(f"Failed to get schedule config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schedule config: {str(e)}"
        )

@router.get("/validate-cron")
async def validate_cron_expression(expression: str):
    """Validate a cron expression."""
    try:
        is_valid = ScheduleConfig.validate_cron_expression(expression)
        
        if is_valid:
            description = ScheduleConfig.get_schedule_description(expression)
            next_run = ScheduleConfig.get_next_run_time(expression)
            
            return {
                "success": True,
                "valid": True,
                "description": description,
                "next_run": next_run.isoformat() if next_run else None
            }
        else:
            return {
                "success": True,
                "valid": False,
                "error": "Invalid cron expression format"
            }
    except Exception as e:
        logger.error(f"Failed to validate cron expression: {str(e)}")
        return {
            "success": True,
            "valid": False,
            "error": str(e)
        }

@router.get("/stores")
async def get_stores():
    """Get all stores for schedule management."""
    try:
        from database.client import SupabaseClient
        
        db = SupabaseClient()
        if not db._initialized:
            await db.initialize()
            
        result = db._client.table('stores').select(
            'id, name, slug, is_active'
        ).eq('is_active', True).execute()
        
        stores = result.data or []
        
        return {"success": True, "data": stores}
    except Exception as e:
        logger.error(f"Failed to get stores: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stores: {str(e)}"
        ) 