"""
Store Scheduler
High-level interface for managing store-specific scraping schedules.
Integrates database operations with the cron manager.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio
from uuid import UUID

from database.client import SupabaseClient
from .cron_manager import cron_manager
from .schedule_config import ScheduleConfig
# Temporarily remove orchestrator import - will integrate later
# from agents.orchestrator import MasterOrchestrator

logger = logging.getLogger(__name__)

class StoreScheduler:
    """Manages store-specific scraping schedules."""
    
    def __init__(self):
        """Initialize the store scheduler."""
        self.db = SupabaseClient()
        # TODO: Integrate with orchestrator later
        # self.orchestrator = MasterOrchestrator()
        self._initialized = False
        
    async def initialize(self):
        """Initialize the scheduler with existing schedules from database."""
        if self._initialized:
            return
            
        try:
            logger.info("Initializing store scheduler...")
            
            # Start the cron manager
            cron_manager.start()
            
            # Load existing schedules from database
            await self._load_schedules_from_db()
            
            self._initialized = True
            logger.info("Store scheduler initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize store scheduler: {str(e)}")
            raise
            
    async def shutdown(self):
        """Shutdown the scheduler."""
        logger.info("Shutting down store scheduler...")
        cron_manager.stop()
        self._initialized = False
        
    async def _load_schedules_from_db(self):
        """Load all active schedules from database and register them."""
        try:
            # Get all active schedules
            # Initialize database if needed
            if not self.db._initialized:
                await self.db.initialize()
                
            result = self.db._client.table('store_schedules').select(
                'id, store_id, schedule_type, cron_expression, timezone, stores(slug, name)'
            ).eq('is_active', True).execute()
            
            schedules = result.data
            logger.info(f"Loading {len(schedules)} active schedules from database")
            
            for schedule in schedules:
                await self._register_schedule(schedule)
                
        except Exception as e:
            logger.error(f"Failed to load schedules from database: {str(e)}")
            
    async def _register_schedule(self, schedule: Dict[str, Any]):
        """Register a schedule with the cron manager."""
        try:
            store_slug = schedule['stores']['slug']
            store_name = schedule['stores']['name']
            schedule_id = schedule['id']
            schedule_type = schedule['schedule_type']
            cron_expression = schedule['cron_expression']
            timezone = schedule['timezone']
            
            # Create job ID
            job_id = f"{store_slug}_{schedule_type}_{schedule_id}"
            
            # Register the job
            success = cron_manager.add_job(
                job_id=job_id,
                func=self._execute_scheduled_scraping,
                cron_expression=cron_expression,
                timezone=timezone,
                store_slug=store_slug,
                store_name=store_name,
                schedule_id=schedule_id,
                schedule_type=schedule_type
            )
            
            if success:
                # Update next_run_at in database
                next_run = cron_manager.get_next_run_time(job_id)
                if next_run:
                    self.db._client.table('store_schedules').update({
                        'next_run_at': next_run.isoformat()
                    }).eq('id', schedule_id).execute()
                    
                logger.info(f"Registered schedule for {store_name} ({schedule_type}): {cron_expression}")
            else:
                logger.error(f"Failed to register schedule for {store_name}")
                
        except Exception as e:
            logger.error(f"Failed to register schedule: {str(e)}")
            
    def _execute_scheduled_scraping(self, store_slug: str, store_name: str, 
                                   schedule_id: str, schedule_type: str):
        """Execute scheduled scraping for a store."""
        try:
            logger.info(f"Executing scheduled {schedule_type} for {store_name}")
            
            # Update last_run_at in database
            asyncio.create_task(self._update_last_run(schedule_id))
            
            # Execute scraping based on schedule type
            if schedule_type == 'weekly_price_update':
                asyncio.create_task(self._run_price_update(store_slug, store_name))
            elif schedule_type == 'daily_price_check':
                asyncio.create_task(self._run_price_check(store_slug, store_name))
            elif schedule_type == 'full_catalog_sync':
                asyncio.create_task(self._run_full_sync(store_slug, store_name))
            elif schedule_type == 'promotional_scan':
                asyncio.create_task(self._run_promotional_scan(store_slug, store_name))
            else:
                logger.warning(f"Unknown schedule type: {schedule_type}")
                
        except Exception as e:
            logger.error(f"Failed to execute scheduled scraping for {store_name}: {str(e)}")
            
    async def _update_last_run(self, schedule_id: str):
        """Update the last_run_at timestamp for a schedule."""
        try:
            self.db._client.table('store_schedules').update({
                'last_run_at': datetime.now().isoformat()
            }).eq('id', schedule_id).execute()
        except Exception as e:
            logger.error(f"Failed to update last_run_at for schedule {schedule_id}: {str(e)}")
            
    async def _run_price_update(self, store_slug: str, store_name: str):
        """Run weekly price update for a store."""
        try:
            logger.info(f"Starting weekly price update for {store_name}")
            
            # TODO: Use orchestrator to run scraping
            # result = await self.orchestrator.run_store_scraper(
            #     store_slug=store_slug,
            #     job_type='price_update'
            # )
            
            # Placeholder for testing - simulate successful run
            result = {
                'success': True,
                'message': f'Price update scheduled for {store_name}',
                'job_id': f'test_job_{store_slug}_{datetime.now().isoformat()}'
            }
            
            if result.get('success'):
                logger.info(f"Weekly price update completed for {store_name}")
            else:
                logger.error(f"Weekly price update failed for {store_name}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Failed to run price update for {store_name}: {str(e)}")
            
    async def _run_price_check(self, store_slug: str, store_name: str):
        """Run daily price check for a store."""
        try:
            logger.info(f"Starting daily price check for {store_name}")
            
            # TODO: Light scraping - check only current prices
            # result = await self.orchestrator.run_store_scraper(
            #     store_slug=store_slug,
            #     job_type='price_check',
            #     sample_size=100  # Only check sample of products
            # )
            
            # Placeholder for testing
            result = {
                'success': True,
                'message': f'Price check scheduled for {store_name}',
                'job_id': f'test_check_{store_slug}_{datetime.now().isoformat()}'
            }
            
            if result.get('success'):
                logger.info(f"Daily price check completed for {store_name}")
            else:
                logger.error(f"Daily price check failed for {store_name}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Failed to run price check for {store_name}: {str(e)}")
            
    async def _run_full_sync(self, store_slug: str, store_name: str):
        """Run full catalog synchronization for a store."""
        try:
            logger.info(f"Starting full catalog sync for {store_name}")
            
            # TODO: Full sync scraping
            # result = await self.orchestrator.run_store_scraper(
            #     store_slug=store_slug,
            #     job_type='full_sync'
            # )
            
            # Placeholder for testing
            result = {
                'success': True,
                'message': f'Full sync scheduled for {store_name}',
                'job_id': f'test_sync_{store_slug}_{datetime.now().isoformat()}'
            }
            
            if result.get('success'):
                logger.info(f"Full catalog sync completed for {store_name}")
            else:
                logger.error(f"Full catalog sync failed for {store_name}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Failed to run full sync for {store_name}: {str(e)}")
            
    async def _run_promotional_scan(self, store_slug: str, store_name: str):
        """Run promotional scan for a store."""
        try:
            logger.info(f"Starting promotional scan for {store_name}")
            
            # TODO: Promotional scan
            # result = await self.orchestrator.run_store_scraper(
            #     store_slug=store_slug,
            #     job_type='promotional_scan'
            # )
            
            # Placeholder for testing
            result = {
                'success': True,
                'message': f'Promotional scan scheduled for {store_name}',
                'job_id': f'test_promo_{store_slug}_{datetime.now().isoformat()}'
            }
            
            if result.get('success'):
                logger.info(f"Promotional scan completed for {store_name}")
            else:
                logger.error(f"Promotional scan failed for {store_name}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Failed to run promotional scan for {store_name}: {str(e)}")
            
    async def create_schedule(self, store_id: str, schedule_type: str, 
                            cron_expression: str, timezone: str = ScheduleConfig.DEFAULT_TIMEZONE) -> bool:
        """
        Create a new schedule for a store.
        
        Args:
            store_id: Store UUID
            schedule_type: Type of schedule ('weekly_price_update', etc.)
            cron_expression: Cron expression for scheduling
            timezone: Timezone for the schedule
            
        Returns:
            bool: True if schedule created successfully
        """
        try:
            # Validate cron expression
            if not ScheduleConfig.validate_cron_expression(cron_expression):
                logger.error(f"Invalid cron expression: {cron_expression}")
                return False
                
            # Calculate next run time
            next_run = ScheduleConfig.get_next_run_time(cron_expression, timezone)
            
            # Initialize database if needed
            if not self.db._initialized:
                await self.db.initialize()
            
            # Insert into database
            result = self.db._client.table('store_schedules').insert({
                'store_id': store_id,
                'schedule_type': schedule_type,
                'cron_expression': cron_expression,
                'timezone': timezone,
                'next_run_at': next_run.isoformat() if next_run else None,
                'is_active': True
            }).execute()
            
            if result.data:
                schedule = result.data[0]
                
                # Load store info and register the schedule
                store_result = self.db._client.table('stores').select(
                    'slug, name'
                ).eq('id', store_id).execute()
                
                if store_result.data:
                    store = store_result.data[0]
                    schedule['stores'] = store
                    await self._register_schedule(schedule)
                    
                logger.info(f"Created schedule for store {store_id}: {schedule_type}")
                return True
            else:
                logger.error(f"Failed to create schedule in database")
                return False
                
        except Exception as e:
            logger.error(f"Failed to create schedule: {str(e)}")
            return False
            
    async def update_schedule(self, schedule_id: str, **updates) -> bool:
        """
        Update an existing schedule.
        
        Args:
            schedule_id: Schedule UUID
            **updates: Fields to update
            
        Returns:
            bool: True if schedule updated successfully
        """
        try:
            # Initialize database if needed
            if not self.db._initialized:
                await self.db.initialize()
                
            # Get current schedule
            current_result = self.db._client.table('store_schedules').select(
                'id, store_id, schedule_type, cron_expression, timezone, stores(slug, name)'
            ).eq('id', schedule_id).execute()
            
            if not current_result.data:
                logger.error(f"Schedule {schedule_id} not found")
                return False
                
            current_schedule = current_result.data[0]
            store_slug = current_schedule['stores']['slug']
            
            # Remove old job from cron manager
            old_job_id = f"{store_slug}_{current_schedule['schedule_type']}_{schedule_id}"
            cron_manager.remove_job(old_job_id)
            
            # Update in database
            if 'cron_expression' in updates:
                # Validate new cron expression
                if not ScheduleConfig.validate_cron_expression(updates['cron_expression']):
                    logger.error(f"Invalid cron expression: {updates['cron_expression']}")
                    return False
                    
                # Calculate new next run time
                timezone = updates.get('timezone', current_schedule['timezone'])
                next_run = ScheduleConfig.get_next_run_time(updates['cron_expression'], timezone)
                updates['next_run_at'] = next_run.isoformat() if next_run else None
                
            result = self.db._client.table('store_schedules').update(
                updates
            ).eq('id', schedule_id).execute()
            
            if result.data:
                # Get updated schedule and re-register
                updated_result = self.db._client.table('store_schedules').select(
                    'id, store_id, schedule_type, cron_expression, timezone, stores(slug, name)'
                ).eq('id', schedule_id).execute()
                
                if updated_result.data:
                    updated_schedule = updated_result.data[0]
                    await self._register_schedule(updated_schedule)
                    
                logger.info(f"Updated schedule {schedule_id}")
                return True
            else:
                logger.error(f"Failed to update schedule in database")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update schedule: {str(e)}")
            return False
            
    async def delete_schedule(self, schedule_id: str) -> bool:
        """
        Delete a schedule.
        
        Args:
            schedule_id: Schedule UUID
            
        Returns:
            bool: True if schedule deleted successfully
        """
        try:
            # Initialize database if needed
            if not self.db._initialized:
                await self.db.initialize()
                
            # Get schedule info for job removal
            result = self.db._client.table('store_schedules').select(
                'id, schedule_type, stores(slug)'
            ).eq('id', schedule_id).execute()
            
            if result.data:
                schedule = result.data[0]
                store_slug = schedule['stores']['slug']
                schedule_type = schedule['schedule_type']
                
                # Remove job from cron manager
                job_id = f"{store_slug}_{schedule_type}_{schedule_id}"
                cron_manager.remove_job(job_id)
                
            # Delete from database
            self.db._client.table('store_schedules').delete().eq('id', schedule_id).execute()
            
            logger.info(f"Deleted schedule {schedule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete schedule: {str(e)}")
            return False
            
    async def get_schedules(self, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get schedules, optionally filtered by store.
        
        Args:
            store_id: Optional store UUID filter
            
        Returns:
            List of schedule dictionaries
        """
        try:
            # Initialize database if needed
            if not self.db._initialized:
                await self.db.initialize()
                
            query = self.db._client.table('store_schedules').select(
                'id, store_id, schedule_type, cron_expression, timezone, is_active, '
                'next_run_at, last_run_at, created_at, stores(slug, name)'
            )
            
            if store_id:
                query = query.eq('store_id', store_id)
                
            result = query.execute()
            
            schedules = result.data or []
            
            # Add job status from cron manager
            for schedule in schedules:
                store_slug = schedule['stores']['slug']
                job_id = f"{store_slug}_{schedule['schedule_type']}_{schedule['id']}"
                job_status = cron_manager.get_job_status(job_id)
                
                schedule['job_status'] = job_status
                schedule['description'] = ScheduleConfig.get_schedule_description(
                    schedule['cron_expression']
                )
                
            return schedules
            
        except Exception as e:
            logger.error(f"Failed to get schedules: {str(e)}")
            return []
            
    async def trigger_manual_run(self, store_slug: str, schedule_type: str = 'weekly_price_update') -> bool:
        """
        Trigger a manual run of a scraper.
        
        Args:
            store_slug: Store identifier
            schedule_type: Type of scraping to run
            
        Returns:
            bool: True if triggered successfully
        """
        try:
            # Initialize database if needed
            if not self.db._initialized:
                await self.db.initialize()
                
            # Get store info
            store_result = self.db._client.table('stores').select(
                'name'
            ).eq('slug', store_slug).execute()
            
            if not store_result.data:
                logger.error(f"Store {store_slug} not found")
                return False
                
            store_name = store_result.data[0]['name']
            
            # Execute scraping
            if schedule_type == 'weekly_price_update':
                await self._run_price_update(store_slug, store_name)
            elif schedule_type == 'daily_price_check':
                await self._run_price_check(store_slug, store_name)
            elif schedule_type == 'full_catalog_sync':
                await self._run_full_sync(store_slug, store_name)
            elif schedule_type == 'promotional_scan':
                await self._run_promotional_scan(store_slug, store_name)
            else:
                logger.error(f"Unknown schedule type: {schedule_type}")
                return False
                
            logger.info(f"Manual {schedule_type} triggered for {store_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger manual run: {str(e)}")
            return False

# Global instance
store_scheduler = StoreScheduler() 