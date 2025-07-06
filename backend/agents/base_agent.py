"""
Base Agent Class
Common functionality and state for all scraping agents
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from langgraph.graph import StateGraph
from langchain.schema import BaseMessage
from langchain_openai import ChatOpenAI

from config.settings import settings
from config.database import db_manager
from utils.logging import AgentLogger


class AgentStatus(Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentState:
    """Base state class for all scraping agents"""
    # Basic state
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: AgentStatus = AgentStatus.IDLE
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Store information
    store_name: str = ""
    store_slug: str = ""
    base_url: str = ""
    
    # Counters
    products_processed: int = 0
    products_saved: int = 0
    categories_processed: int = 0
    pages_processed: int = 0
    
    # Configuration
    batch_size: int = 100
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    
    # Session data
    session_headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    
    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    last_error: Optional[str] = None
    
    # Category tracking
    current_category_index: int = 0
    total_categories: int = 0
    
    # Progress tracking
    progress_percentage: float = 0.0
    estimated_completion: Optional[datetime] = None


class BaseAgent(ABC):
    """Abstract base class for all scraping agents"""
    
    def __init__(self, agent_type: str, display_name: str):
        self.agent_type = agent_type
        self.display_name = display_name
        self.state = AgentState()
        self.is_running = False
        self.should_stop = False
        
    @abstractmethod
    async def run_scraping_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete scraping job"""
        pass
        
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            "agent_id": self.state.agent_id,
            "agent_type": self.agent_type,
            "display_name": self.display_name,
            "status": self.state.status.value,
            "store_name": self.state.store_name,
            "is_running": self.is_running,
            "start_time": self.state.start_time.isoformat() if self.state.start_time else None,
            "end_time": self.state.end_time.isoformat() if self.state.end_time else None,
            "progress": {
                "products_processed": self.state.products_processed,
                "products_saved": self.state.products_saved,
                "categories_processed": self.state.categories_processed,
                "total_categories": self.state.total_categories,
                "progress_percentage": self.state.progress_percentage,
                "estimated_completion": self.state.estimated_completion.isoformat() if self.state.estimated_completion else None
            },
            "errors": {
                "count": len(self.state.errors),
                "last_error": self.state.last_error,
                "recent_errors": self.state.errors[-5:] if self.state.errors else []
            }
        }
    
    def pause(self) -> bool:
        """Pause the agent"""
        if self.is_running and self.state.status == AgentStatus.RUNNING:
            self.state.status = AgentStatus.PAUSED
            return True
        return False
    
    def resume(self) -> bool:
        """Resume the agent"""
        if self.state.status == AgentStatus.PAUSED:
            self.state.status = AgentStatus.RUNNING
            return True
        return False
    
    def stop(self) -> bool:
        """Stop the agent"""
        if self.is_running:
            self.should_stop = True
            self.state.status = AgentStatus.CANCELLED
            return True
        return False
    
    def reset(self):
        """Reset agent state"""
        self.state = AgentState()
        self.is_running = False
        self.should_stop = False
    
    def update_progress(self):
        """Update progress percentage based on current state"""
        if self.state.total_categories > 0:
            self.state.progress_percentage = min(
                (self.state.current_category_index / self.state.total_categories) * 100,
                100.0
            )
        
        # Estimate completion time based on current progress
        if self.state.start_time and self.state.progress_percentage > 0:
            elapsed = (datetime.now() - self.state.start_time).total_seconds()
            if self.state.progress_percentage > 5:  # Only estimate after 5% completion
                total_estimated = elapsed / (self.state.progress_percentage / 100)
                remaining = total_estimated - elapsed
                self.state.estimated_completion = datetime.now() + timedelta(seconds=remaining)


class ScrapingAgentState(AgentState):
    """Extended state for scraping agents."""
    store_slug: Optional[str] = None
    products_processed: int = 0
    products_updated: int = 0
    errors_count: int = 0
    scraping_job_id: Optional[str] = None
    batch_size: int = 50
    rate_limit: float = 2.0


class ProcessingAgentState(AgentState):
    """Extended state for data processing agents."""
    input_data: Optional[List[Dict[str, Any]]] = None
    processed_data: Optional[List[Dict[str, Any]]] = None
    processing_rules: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[str]] = None 