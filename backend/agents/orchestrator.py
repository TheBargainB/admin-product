"""
Master Orchestrator Agent
Coordinates all scraping activities, manages task scheduling and prioritization,
handles error recovery and retry logic, monitors system resources and performance.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio

from langgraph.graph import StateGraph, START, END
from langchain.schema import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent, AgentState
from config.database import db_manager
from config.settings import settings


class OrchestratorState(AgentState):
    """State for orchestrator operations."""
    active_jobs: List[Dict[str, Any]] = None
    system_health: Dict[str, Any] = None
    scheduled_tasks: List[Dict[str, Any]] = None
    performance_metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.active_jobs is None:
            self.active_jobs = []
        if self.scheduled_tasks is None:
            self.scheduled_tasks = []
        if self.performance_metrics is None:
            self.performance_metrics = {}


class MasterOrchestrator(BaseAgent):
    """Master Orchestrator Agent for coordinating all system activities."""
    
    def __init__(self):
        super().__init__("master_orchestrator", "gpt-4-turbo-preview")
        self.max_concurrent_jobs = 3
        self.health_check_interval = 300  # 5 minutes
        self.retry_max_attempts = 3
    
    def _build_graph(self):
        """Build the orchestrator state graph."""
        workflow = StateGraph(OrchestratorState)
        
        # Add nodes
        workflow.add_node("assess_system", self._assess_system_health)
        workflow.add_node("check_scheduled_tasks", self._check_scheduled_tasks)
        workflow.add_node("manage_active_jobs", self._manage_active_jobs)
        workflow.add_node("prioritize_tasks", self._prioritize_tasks)
        workflow.add_node("execute_tasks", self._execute_tasks)
        workflow.add_node("monitor_performance", self._monitor_performance)
        workflow.add_node("handle_errors", self._handle_errors)
        
        # Define the flow
        workflow.add_edge(START, "assess_system")
        workflow.add_edge("assess_system", "check_scheduled_tasks")
        workflow.add_edge("check_scheduled_tasks", "manage_active_jobs")
        workflow.add_edge("manage_active_jobs", "prioritize_tasks")
        workflow.add_edge("prioritize_tasks", "execute_tasks")
        workflow.add_edge("execute_tasks", "monitor_performance")
        workflow.add_edge("monitor_performance", END)
        
        # Conditional edges for error handling
        workflow.add_conditional_edges(
            "execute_tasks",
            self._should_handle_errors,
            {
                "handle_errors": "handle_errors",
                "continue": "monitor_performance"
            }
        )
        workflow.add_edge("handle_errors", "monitor_performance")
        
        self.graph = workflow.compile()
    
    async def execute(self, initial_state: OrchestratorState = None) -> OrchestratorState:
        """Execute orchestrator workflow."""
        if initial_state is None:
            initial_state = OrchestratorState(
                messages=[],
                current_task="orchestrate_system",
                metadata={"start_time": datetime.utcnow().isoformat()}
            )
        
        try:
            self.logger.log_action("Starting orchestration cycle")
            await self._log_to_database("info", "Orchestration cycle started")
            
            # Execute the graph
            result = await self.graph.ainvoke(initial_state)
            
            self.logger.log_action("Orchestration cycle completed", {
                "active_jobs": len(result.active_jobs),
                "performance_metrics": result.performance_metrics
            })
            
            return result
            
        except Exception as e:
            return await self._handle_error(initial_state, e)
    
    async def _assess_system_health(self, state: OrchestratorState) -> OrchestratorState:
        """Assess overall system health."""
        try:
            health_data = {
                "database_status": await self._check_database_health(),
                "active_scrapers": await self._count_active_scrapers(),
                "error_rate": await self._calculate_error_rate(),
                "memory_usage": await self._check_memory_usage(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            state.system_health = health_data
            
            # Log critical issues
            if health_data["error_rate"] > 10:  # 10% error rate threshold
                await self._log_to_database("warning", 
                    f"High error rate detected: {health_data['error_rate']}%")
            
            self.logger.log_action("System health assessed", health_data)
            
        except Exception as e:
            self.logger.log_error("Failed to assess system health", e)
            state.system_health = {"status": "unknown", "error": str(e)}
        
        return state
    
    async def _check_scheduled_tasks(self, state: OrchestratorState) -> OrchestratorState:
        """Check for scheduled scraping tasks."""
        try:
            # Get pending scraping jobs
            pending_jobs = await db_manager.execute_query(
                "SELECT * FROM scraping_jobs WHERE status = 'pending' ORDER BY created_at"
            )
            
            # Check for scheduled daily price updates
            stores = await db_manager.get_stores()
            current_time = datetime.utcnow()
            
            scheduled_tasks = []
            
            for store in stores:
                # Check if store needs daily price update
                last_update = await self._get_last_scraping_job(store['id'], 'price_update')
                
                if not last_update or self._should_schedule_update(last_update, current_time):
                    scheduled_tasks.append({
                        "type": "price_update",
                        "store_id": store['id'],
                        "store_slug": store['slug'],
                        "priority": self._calculate_priority(store, "price_update"),
                        "scheduled_for": current_time.isoformat()
                    })
            
            state.scheduled_tasks = scheduled_tasks + [
                {
                    "type": "existing_job",
                    "job_id": job['id'],
                    "store_id": job['store_id'],
                    "job_type": job['job_type'],
                    "priority": self._calculate_job_priority(job),
                    "created_at": job['created_at']
                }
                for job in pending_jobs
            ]
            
            self.logger.log_action("Scheduled tasks checked", {
                "pending_jobs": len(pending_jobs),
                "new_scheduled": len(scheduled_tasks)
            })
            
        except Exception as e:
            self.logger.log_error("Failed to check scheduled tasks", e)
            state.scheduled_tasks = []
        
        return state
    
    async def _manage_active_jobs(self, state: OrchestratorState) -> OrchestratorState:
        """Manage currently active scraping jobs."""
        try:
            # Get currently running jobs
            active_jobs = await db_manager.execute_query(
                "SELECT * FROM scraping_jobs WHERE status = 'running'"
            )
            
            # Check for stale jobs (running for too long)
            stale_threshold = datetime.utcnow() - timedelta(hours=2)
            
            for job in active_jobs:
                if job['started_at'] and job['started_at'] < stale_threshold:
                    # Mark stale job as failed
                    await db_manager.update_scraping_job(
                        job['id'],
                        status='failed',
                        completed_at=datetime.utcnow(),
                        error_details={"reason": "Job timeout - marked as stale"}
                    )
                    
                    await self._log_to_database("warning", 
                        f"Marked stale job as failed: {job['id']}")
            
            # Refresh active jobs list
            state.active_jobs = await db_manager.execute_query(
                "SELECT * FROM scraping_jobs WHERE status = 'running'"
            )
            
            self.logger.log_action("Active jobs managed", {
                "active_count": len(state.active_jobs)
            })
            
        except Exception as e:
            self.logger.log_error("Failed to manage active jobs", e)
            state.active_jobs = []
        
        return state
    
    async def _prioritize_tasks(self, state: OrchestratorState) -> OrchestratorState:
        """Prioritize scheduled tasks based on various factors."""
        try:
            # Sort tasks by priority (higher number = higher priority)
            state.scheduled_tasks.sort(key=lambda x: x.get('priority', 0), reverse=True)
            
            # Limit concurrent jobs
            available_slots = self.max_concurrent_jobs - len(state.active_jobs)
            state.scheduled_tasks = state.scheduled_tasks[:available_slots]
            
            self.logger.log_action("Tasks prioritized", {
                "tasks_to_execute": len(state.scheduled_tasks),
                "available_slots": available_slots
            })
            
        except Exception as e:
            self.logger.log_error("Failed to prioritize tasks", e)
        
        return state
    
    async def _execute_tasks(self, state: OrchestratorState) -> OrchestratorState:
        """Execute prioritized tasks."""
        executed_tasks = []
        
        for task in state.scheduled_tasks:
            try:
                if task['type'] == 'price_update':
                    # Create new scraping job
                    job = await db_manager.create_scraping_job(
                        task['store_id'], 
                        'price_update'
                    )
                    executed_tasks.append({
                        "task": task,
                        "job_id": job['id'],
                        "status": "started"
                    })
                    
                elif task['type'] == 'existing_job':
                    # Update existing job to running
                    await db_manager.update_scraping_job(
                        task['job_id'],
                        status='running',
                        started_at=datetime.utcnow()
                    )
                    executed_tasks.append({
                        "task": task,
                        "job_id": task['job_id'],
                        "status": "resumed"
                    })
                
                self.logger.log_action("Task executed", {
                    "task_type": task['type'],
                    "store_id": task.get('store_id')
                })
                
            except Exception as e:
                self.logger.log_error(f"Failed to execute task: {task}", e)
                executed_tasks.append({
                    "task": task,
                    "status": "failed",
                    "error": str(e)
                })
        
        state.metadata['executed_tasks'] = executed_tasks
        return state
    
    async def _monitor_performance(self, state: OrchestratorState) -> OrchestratorState:
        """Monitor system performance metrics."""
        try:
            performance_data = {
                "active_jobs_count": len(state.active_jobs),
                "scheduled_tasks_count": len(state.scheduled_tasks),
                "system_health_score": self._calculate_health_score(state.system_health),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Get additional metrics from database
            metrics = await self._gather_performance_metrics()
            performance_data.update(metrics)
            
            state.performance_metrics = performance_data
            
            self.logger.log_action("Performance monitored", performance_data)
            
        except Exception as e:
            self.logger.log_error("Failed to monitor performance", e)
            state.performance_metrics = {"error": str(e)}
        
        return state
    
    async def _handle_errors(self, state: OrchestratorState) -> OrchestratorState:
        """Handle errors and implement recovery strategies."""
        try:
            # Check for failed jobs that can be retried
            failed_jobs = await db_manager.execute_query("""
                SELECT * FROM scraping_jobs 
                WHERE status = 'failed' 
                AND (error_details->>'retry_count')::int < %s
                AND completed_at > %s
            """, self.retry_max_attempts, datetime.utcnow() - timedelta(hours=1))
            
            for job in failed_jobs:
                retry_count = int(job.get('error_details', {}).get('retry_count', 0))
                
                # Implement exponential backoff
                backoff_delay = 2 ** retry_count * 60  # Minutes
                retry_time = job['completed_at'] + timedelta(minutes=backoff_delay)
                
                if datetime.utcnow() >= retry_time:
                    # Reset job for retry
                    await db_manager.update_scraping_job(
                        job['id'],
                        status='pending',
                        error_details={
                            **job.get('error_details', {}),
                            'retry_count': retry_count + 1,
                            'last_retry': datetime.utcnow().isoformat()
                        }
                    )
                    
                    self.logger.log_action("Job queued for retry", {
                        "job_id": job['id'],
                        "retry_count": retry_count + 1
                    })
            
        except Exception as e:
            self.logger.log_error("Failed to handle errors", e)
        
        return state
    
    def _should_handle_errors(self, state: OrchestratorState) -> str:
        """Determine if error handling is needed."""
        executed_tasks = state.metadata.get('executed_tasks', [])
        failed_tasks = [t for t in executed_tasks if t.get('status') == 'failed']
        
        return "handle_errors" if failed_tasks else "continue"
    
    # Helper methods
    async def _check_database_health(self) -> str:
        """Check database connectivity and performance."""
        try:
            await db_manager.execute_query("SELECT 1")
            return "healthy"
        except Exception:
            return "unhealthy"
    
    async def _count_active_scrapers(self) -> int:
        """Count currently active scraper instances."""
        result = await db_manager.execute_query_one(
            "SELECT COUNT(*) as count FROM scraping_jobs WHERE status = 'running'"
        )
        return result['count'] if result else 0
    
    async def _calculate_error_rate(self) -> float:
        """Calculate error rate over last hour."""
        try:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            total_jobs = await db_manager.execute_query_one("""
                SELECT COUNT(*) as count FROM scraping_jobs 
                WHERE completed_at > %s
            """, one_hour_ago)
            
            failed_jobs = await db_manager.execute_query_one("""
                SELECT COUNT(*) as count FROM scraping_jobs 
                WHERE status = 'failed' AND completed_at > %s
            """, one_hour_ago)
            
            total_count = total_jobs['count'] if total_jobs else 0
            failed_count = failed_jobs['count'] if failed_jobs else 0
            
            return (failed_count / total_count * 100) if total_count > 0 else 0
            
        except Exception:
            return 0.0
    
    async def _check_memory_usage(self) -> Dict[str, Any]:
        """Check system memory usage (placeholder for now)."""
        return {"status": "unknown", "usage_percent": 0}
    
    async def _get_last_scraping_job(self, store_id: str, job_type: str) -> Dict[str, Any]:
        """Get the last scraping job for a store."""
        return await db_manager.execute_query_one("""
            SELECT * FROM scraping_jobs 
            WHERE store_id = %s AND job_type = %s 
            ORDER BY created_at DESC LIMIT 1
        """, store_id, job_type)
    
    def _should_schedule_update(self, last_update: Dict[str, Any], current_time: datetime) -> bool:
        """Determine if a price update should be scheduled."""
        if not last_update:
            return True
        
        last_update_time = last_update.get('completed_at') or last_update.get('created_at')
        if not last_update_time:
            return True
        
        # Schedule daily updates
        time_since_update = current_time - last_update_time
        return time_since_update >= timedelta(hours=24)
    
    def _calculate_priority(self, store: Dict[str, Any], task_type: str) -> int:
        """Calculate task priority based on store and task type."""
        base_priority = 10
        
        # Higher priority for major stores
        if store['slug'] in ['albert_heijn', 'jumbo']:
            base_priority += 5
        
        # Higher priority for price updates
        if task_type == 'price_update':
            base_priority += 3
        
        return base_priority
    
    def _calculate_job_priority(self, job: Dict[str, Any]) -> int:
        """Calculate priority for existing job."""
        base_priority = 5
        
        # Higher priority for older jobs
        age_hours = (datetime.utcnow() - job['created_at']).total_seconds() / 3600
        base_priority += min(int(age_hours), 10)
        
        return base_priority
    
    def _calculate_health_score(self, health_data: Dict[str, Any]) -> int:
        """Calculate overall system health score (0-100)."""
        if not health_data:
            return 0
        
        score = 100
        
        if health_data.get('database_status') != 'healthy':
            score -= 30
        
        error_rate = health_data.get('error_rate', 0)
        if error_rate > 5:
            score -= min(error_rate * 2, 50)
        
        return max(score, 0)
    
    async def _gather_performance_metrics(self) -> Dict[str, Any]:
        """Gather additional performance metrics."""
        try:
            # Get total products count
            products_count = await db_manager.get_products_count()
            
            # Get recent job completion rate
            recent_jobs = await db_manager.get_recent_scraping_jobs(50)
            completed_jobs = [j for j in recent_jobs if j['status'] == 'completed']
            completion_rate = len(completed_jobs) / len(recent_jobs) * 100 if recent_jobs else 0
            
            return {
                "total_products": products_count,
                "job_completion_rate": round(completion_rate, 2),
                "recent_jobs_count": len(recent_jobs)
            }
        except Exception as e:
            self.logger.log_error("Failed to gather performance metrics", e)
            return {} 