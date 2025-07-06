"""
Database Models
Pydantic models for data validation and structure
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Job type enumeration."""
    FULL_SCRAPE = "full_scrape"
    PRICE_UPDATE = "price_update"
    VALIDATION = "validation"
    CLEANUP = "cleanup"


class Store(BaseModel):
    """Store model."""
    id: Optional[str] = None
    name: str
    slug: str
    logo_url: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Product(BaseModel):
    """Product model."""
    id: Optional[str] = None
    name: str
    normalized_name: str
    brand: Optional[str] = None
    category_id: Optional[str] = None
    barcode: Optional[str] = None
    unit_type: Optional[str] = None
    unit_size: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    store_id: str
    store_product_id: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    is_promotion: bool = False
    promotion_text: Optional[str] = None
    is_available: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScrapingJob(BaseModel):
    """Scraping job model."""
    id: Optional[str] = None
    store_id: str
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    products_processed: int = 0
    products_updated: int = 0
    errors_count: int = 0
    error_details: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class SystemLog(BaseModel):
    """System log model."""
    id: Optional[str] = None
    level: str
    message: str
    component: str = "system"
    store_id: Optional[str] = None
    job_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class AgentState(BaseModel):
    """Agent state model for LangGraph."""
    agent_id: str
    store_slug: str
    status: str = "idle"
    current_category: Optional[str] = None
    categories_processed: List[str] = Field(default_factory=list)
    products_found: List[Dict[str, Any]] = Field(default_factory=list)
    error_count: int = 0
    retry_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentConfig(BaseModel):
    """Agent configuration model."""
    store_slug: str
    rate_limit: float = 1.0
    max_retries: int = 3
    timeout: int = 30
    batch_size: int = 100
    categories: List[str] = Field(default_factory=list)
    headers: Dict[str, str] = Field(default_factory=dict)
    use_proxy: bool = False
    proxy_url: Optional[str] = None 