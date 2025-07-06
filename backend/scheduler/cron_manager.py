"""
Cron Manager
APScheduler integration for managing scheduled scraping jobs.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.jobstores.memory import MemoryJobStore

from .schedule_config import ScheduleConfig

logger = logging.getLogger(__name__)

class CronManager:
    """Manages cron jobs using APScheduler for store scrapers."""
    
    def __init__(self):
        """Initialize the cron manager with APScheduler."""
        self.scheduler = BackgroundScheduler(
            jobstores={'default': MemoryJobStore()},
            timezone=pytz.timezone(ScheduleConfig.DEFAULT_TIMEZONE)
        )
        
        # Add event listeners for job monitoring
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error_listener, 
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._job_missed_listener,
            EVENT_JOB_MISSED
        )
        
        self._job_callbacks: Dict[str, Callable] = {}
        
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            logger.info("Starting cron scheduler")
            self.scheduler.start()
            
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            logger.info("Stopping cron scheduler")
            self.scheduler.shutdown(wait=False)
            
    def add_job(self, 
                job_id: str,
                func: Callable,
                cron_expression: str,
                timezone: str = ScheduleConfig.DEFAULT_TIMEZONE,
                max_instances: int = 1,
                replace_existing: bool = True,
                **kwargs) -> bool:
        """
        Add a scheduled job.
        
        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            cron_expression: Cron expression for scheduling
            timezone: Timezone for the schedule
            max_instances: Maximum concurrent instances
            replace_existing: Whether to replace existing job with same ID
            **kwargs: Additional arguments to pass to the function
            
        Returns:
            bool: True if job added successfully
        """
        try:
            # Validate cron expression
            if not ScheduleConfig.validate_cron_expression(cron_expression):
                logger.error(f"Invalid cron expression: {cron_expression}")
                return False
                
            # Create trigger
            trigger = CronTrigger.from_crontab(
                cron_expression,
                timezone=pytz.timezone(timezone)
            )
            
            # Store callback for monitoring
            self._job_callbacks[job_id] = func
            
            # Add job to scheduler
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                max_instances=max_instances,
                replace_existing=replace_existing,
                kwargs=kwargs
            )
            
            next_run = self.get_next_run_time(job_id)
            logger.info(f"Added job {job_id} with schedule {cron_expression}. Next run: {next_run}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {str(e)}")
            return False
            
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.
        
        Args:
            job_id: Job identifier to remove
            
        Returns:
            bool: True if job removed successfully
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self._job_callbacks:
                del self._job_callbacks[job_id]
            logger.info(f"Removed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {str(e)}")
            return False
            
    def pause_job(self, job_id: str) -> bool:
        """
        Pause a scheduled job.
        
        Args:
            job_id: Job identifier to pause
            
        Returns:
            bool: True if job paused successfully
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {str(e)}")
            return False
            
    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job.
        
        Args:
            job_id: Job identifier to resume
            
        Returns:
            bool: True if job resumed successfully
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {str(e)}")
            return False
            
    def get_jobs(self) -> List[Dict]:
        """
        Get all scheduled jobs.
        
        Returns:
            List of job information dictionaries
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name or job.id,
                'func': str(job.func),
                'trigger': str(job.trigger),
                'next_run_time': job.next_run_time,
                'max_instances': job.max_instances,
                'pending': job.pending,
            })
        return jobs
        
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Get status of a specific job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status dictionary or None if not found
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    'id': job.id,
                    'name': job.name or job.id,
                    'next_run_time': job.next_run_time,
                    'pending': job.pending,
                    'running': len([j for j in self.scheduler.get_jobs() if j.id == job_id and j.pending]) > 0
                }
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {str(e)}")
        return None
        
    def get_next_run_time(self, job_id: str) -> Optional[datetime]:
        """
        Get the next run time for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Next run time or None if not found
        """
        try:
            job = self.scheduler.get_job(job_id)
            return job.next_run_time if job else None
        except Exception as e:
            logger.error(f"Failed to get next run time for {job_id}: {str(e)}")
            return None
            
    def modify_job(self, job_id: str, **changes) -> bool:
        """
        Modify an existing job.
        
        Args:
            job_id: Job identifier
            **changes: Job attributes to modify
            
        Returns:
            bool: True if job modified successfully
        """
        try:
            self.scheduler.modify_job(job_id, **changes)
            logger.info(f"Modified job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to modify job {job_id}: {str(e)}")
            return False
            
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.scheduler.running
        
    def _job_executed_listener(self, event):
        """Handle job execution events."""
        job_id = event.job_id
        logger.info(f"Job {job_id} executed successfully")
        
    def _job_error_listener(self, event):
        """Handle job error events."""
        job_id = event.job_id
        exception = event.exception
        logger.error(f"Job {job_id} failed with error: {exception}")
        
    def _job_missed_listener(self, event):
        """Handle missed job events."""
        job_id = event.job_id
        scheduled_run_time = event.scheduled_run_time
        logger.warning(f"Job {job_id} missed scheduled run time: {scheduled_run_time}")

# Global instance
cron_manager = CronManager() 