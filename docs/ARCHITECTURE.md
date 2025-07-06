# LangGraph Agents Architecture for Grocery Scraping System

## Overview
The LangGraph agents system provides an intelligent, autonomous approach to managing grocery price scraping across multiple Dutch supermarkets. Each agent specializes in specific tasks while coordinating through a central orchestrator.

## Agent Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    MASTER ORCHESTRATOR AGENT                    │
│  • Task Scheduling & Prioritization                            │
│  • Resource Management                                          │
│  • Error Recovery & Retry Logic                                │
│  • Performance Monitoring                                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   SCRAPER   │ │ PROCESSING  │ │  DATABASE   │
│   AGENTS    │ │   AGENTS    │ │   AGENTS    │
└─────────────┘ └─────────────┘ └─────────────┘
```

## 1. Master Orchestrator Agent

### Purpose
Central coordinator that manages all other agents, schedules tasks, and maintains system health.

### Core Responsibilities
- **Task Scheduling**: Coordinate scraping schedules across all stores
- **Resource Management**: Monitor system resources and distribute workload
- **Error Recovery**: Handle failures and implement retry strategies
- **Performance Monitoring**: Track metrics and optimize operations
- **Communication Hub**: Facilitate inter-agent communication

### LangGraph Implementation
```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langchain_core.messages import HumanMessage, SystemMessage
from typing import TypedDict, List, Dict, Any
import asyncio
from datetime import datetime, timedelta

class OrchestratorState(TypedDict):
    messages: List[HumanMessage]
    current_task: str
    active_jobs: List[Dict[str, Any]]
    system_health: Dict[str, Any]
    error_count: int
    last_health_check: datetime

class MasterOrchestratorAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.active_scrapers = {}
        self.job_queue = []
        self.system_metrics = {}
    
    def _build_graph(self):
        workflow = StateGraph(OrchestratorState)
        
        # Define nodes
        workflow.add_node("health_check", self.health_check)
        workflow.add_node("task_scheduler", self.task_scheduler)
        workflow.add_node("resource_manager", self.resource_manager)
        workflow.add_node("error_handler", self.error_handler)
        workflow.add_node("performance_monitor", self.performance_monitor)
        workflow.add_node("agent_coordinator", self.agent_coordinator)
        
        # Define edges
        workflow.set_entry_point("health_check")
        workflow.add_edge("health_check", "task_scheduler")
        workflow.add_edge("task_scheduler", "resource_manager")
        workflow.add_edge("resource_manager", "agent_coordinator")
        workflow.add_edge("agent_coordinator", "performance_monitor")
        workflow.add_edge("performance_monitor", "error_handler")
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()
    
    async def health_check(self, state: OrchestratorState) -> OrchestratorState:
        """Check system health and update metrics"""
        health_data = {
            "cpu_usage": await self.get_cpu_usage(),
            "memory_usage": await self.get_memory_usage(),
            "active_connections": len(self.active_scrapers),
            "queue_length": len(self.job_queue),
            "timestamp": datetime.now()
        }
        
        state["system_health"] = health_data
        state["last_health_check"] = datetime.now()
        
        return state
    
    async def task_scheduler(self, state: OrchestratorState) -> OrchestratorState:
        """Schedule and prioritize scraping tasks"""
        scheduled_tasks = []
        
        # Check for scheduled scrapes
        for store in ["dirk", "albert_heijn", "hoogvliet", "jumbo"]:
            if self.should_scrape(store):
                task = {
                    "store": store,
                    "type": "price_update",
                    "priority": self.calculate_priority(store),
                    "scheduled_at": datetime.now(),
                    "estimated_duration": self.estimate_duration(store)
                }
                scheduled_tasks.append(task)
        
        # Sort by priority
        scheduled_tasks.sort(key=lambda x: x["priority"], reverse=True)
        
        state["active_jobs"] = scheduled_tasks
        return state
    
    def should_scrape(self, store: str) -> bool:
        """Determine if store should be scraped based on schedule and last update"""
        # Implementation logic for scheduling
        pass
    
    def calculate_priority(self, store: str) -> int:
        """Calculate task priority based on various factors"""
        # Implementation logic for priority calculation
        pass
```

## 2. Store-Specific Scraper Agents

### Purpose
Individual agents for each supermarket chain, specialized for their specific website structure and data extraction patterns.

### Dirk Scraper Agent
```python
class DirkScraperAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.base_url = "https://www.dirk.nl"
        self.session = None
        self.rate_limit = 2  # seconds between requests
    
    def _build_graph(self):
        workflow = StateGraph(ScraperState)
        
        workflow.add_node("initialize_session", self.initialize_session)
        workflow.add_node("fetch_categories", self.fetch_categories)
        workflow.add_node("scrape_products", self.scrape_products)
        workflow.add_node("extract_prices", self.extract_prices)
        workflow.add_node("validate_data", self.validate_data)
        workflow.add_node("handle_errors", self.handle_errors)
        
        # Define conditional edges
        workflow.add_conditional_edges(
            "scrape_products",
            self.should_continue_scraping,
            {
                "continue": "extract_prices",
                "error": "handle_errors",
                "complete": END
            }
        )
        
        return workflow.compile()
    
    async def scrape_products(self, state: ScraperState) -> ScraperState:
        """Scrape product data from Dirk website"""
        try:
            # Dirk-specific scraping logic
            products = []
            
            for category_url in state["categories"]:
                await asyncio.sleep(self.rate_limit)
                
                response = await self.session.get(category_url)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract products using Dirk's specific HTML structure
                product_elements = soup.find_all('div', class_='product-item')
                
                for element in product_elements:
                    product = self.extract_product_data(element)
                    if product:
                        products.append(product)
            
            state["scraped_products"] = products
            state["status"] = "success"
            
        except Exception as e:
            state["status"] = "error"
            state["error_message"] = str(e)
            
        return state
    
    def extract_product_data(self, element) -> Dict[str, Any]:
        """Extract product data from HTML element"""
        try:
            return {
                "name": element.find('h3', class_='product-name').text.strip(),
                "price": float(element.find('span', class_='price').text.replace('€', '').replace(',', '.')),
                "unit": element.find('span', class_='unit').text.strip(),
                "brand": element.find('span', class_='brand').text.strip(),
                "image_url": element.find('img')['src'],
                "product_url": element.find('a')['href'],
                "in_stock": not element.find('span', class_='out-of-stock'),
                "scraped_at": datetime.now()
            }
        except Exception as e:
            return None
```

### Albert Heijn Scraper Agent
```python
class AlbertHeijnScraperAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.base_url = "https://www.ah.nl"
        self.api_base = "https://api.ah.nl"
        self.session = None
        self.rate_limit = 1.5
    
    async def scrape_products(self, state: ScraperState) -> ScraperState:
        """Scrape product data from Albert Heijn API"""
        try:
            products = []
            
            # Albert Heijn uses API endpoints
            for category_id in state["category_ids"]:
                await asyncio.sleep(self.rate_limit)
                
                api_url = f"{self.api_base}/mobile-services/product/search/v2"
                params = {
                    "categoryId": category_id,
                    "size": 100,
                    "page": 0
                }
                
                response = await self.session.get(api_url, params=params)
                data = response.json()
                
                for product_data in data.get("products", []):
                    product = self.extract_api_product_data(product_data)
                    if product:
                        products.append(product)
            
            state["scraped_products"] = products
            state["status"] = "success"
            
        except Exception as e:
            state["status"] = "error"
            state["error_message"] = str(e)
            
        return state
    
    def extract_api_product_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product data from API response"""
        try:
            return {
                "name": data.get("title", ""),
                "price": float(data.get("priceBeforeBonus", data.get("currentPrice", 0))),
                "discounted_price": float(data.get("currentPrice", 0)),
                "unit": data.get("unitSize", ""),
                "brand": data.get("brandName", ""),
                "image_url": data.get("imageUrl", ""),
                "product_id": data.get("id", ""),
                "barcode": data.get("gtin", ""),
                "in_stock": data.get("availability", {}).get("isAvailable", False),
                "scraped_at": datetime.now()
            }
        except Exception as e:
            return None
```

## 3. Data Processing Agents

### Product Standardization Agent
```python
class ProductStandardizationAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.name_normalizer = NameNormalizer()
        self.category_mapper = CategoryMapper()
        self.brand_standardizer = BrandStandardizer()
    
    def _build_graph(self):
        workflow = StateGraph(ProcessingState)
        
        workflow.add_node("normalize_names", self.normalize_names)
        workflow.add_node("standardize_brands", self.standardize_brands)
        workflow.add_node("map_categories", self.map_categories)
        workflow.add_node("detect_duplicates", self.detect_duplicates)
        workflow.add_node("merge_products", self.merge_products)
        workflow.add_node("validate_results", self.validate_results)
        
        return workflow.compile()
    
    async def normalize_names(self, state: ProcessingState) -> ProcessingState:
        """Normalize product names for consistency"""
        normalized_products = []
        
        for product in state["raw_products"]:
            normalized_name = self.name_normalizer.normalize(product["name"])
            
            product["normalized_name"] = normalized_name
            product["name_tokens"] = self.name_normalizer.tokenize(normalized_name)
            
            normalized_products.append(product)
        
        state["processed_products"] = normalized_products
        return state
    
    async def detect_duplicates(self, state: ProcessingState) -> ProcessingState:
        """Detect potential duplicate products across stores"""
        products = state["processed_products"]
        duplicates = []
        
        # Use fuzzy matching to find similar products
        for i, product1 in enumerate(products):
            for j, product2 in enumerate(products[i+1:], i+1):
                similarity = self.calculate_similarity(product1, product2)
                
                if similarity > 0.85:  # Threshold for duplicate detection
                    duplicates.append({
                        "product1_id": product1["id"],
                        "product2_id": product2["id"],
                        "similarity": similarity,
                        "merge_strategy": self.determine_merge_strategy(product1, product2)
                    })
        
        state["duplicates"] = duplicates
        return state
    
    def calculate_similarity(self, product1: Dict, product2: Dict) -> float:
        """Calculate similarity between two products"""
        # Implementation using fuzzy string matching, brand comparison, etc.
        pass
```

### Price Validation Agent
```python
class PriceValidationAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.price_history = PriceHistoryManager()
        self.outlier_detector = OutlierDetector()
    
    def _build_graph(self):
        workflow = StateGraph(ValidationState)
        
        workflow.add_node("validate_prices", self.validate_prices)
        workflow.add_node("detect_outliers", self.detect_outliers)
        workflow.add_node("check_historical_trends", self.check_historical_trends)
        workflow.add_node("flag_suspicious_prices", self.flag_suspicious_prices)
        workflow.add_node("generate_alerts", self.generate_alerts)
        
        return workflow.compile()
    
    async def validate_prices(self, state: ValidationState) -> ValidationState:
        """Validate scraped prices against business rules"""
        validated_products = []
        validation_errors = []
        
        for product in state["scraped_products"]:
            validation_result = self.validate_single_price(product)
            
            if validation_result["valid"]:
                validated_products.append(product)
            else:
                validation_errors.append({
                    "product_id": product["id"],
                    "errors": validation_result["errors"]
                })
        
        state["validated_products"] = validated_products
        state["validation_errors"] = validation_errors
        
        return state
    
    async def detect_outliers(self, state: ValidationState) -> ValidationState:
        """Detect price outliers using statistical methods"""
        outliers = []
        
        for product in state["validated_products"]:
            historical_prices = await self.price_history.get_prices(product["id"])
            
            if len(historical_prices) > 10:  # Need enough data points
                is_outlier = self.outlier_detector.detect(
                    product["price"], 
                    historical_prices
                )
                
                if is_outlier:
                    outliers.append({
                        "product_id": product["id"],
                        "current_price": product["price"],
                        "expected_range": self.outlier_detector.get_expected_range(historical_prices),
                        "confidence": self.outlier_detector.get_confidence()
                    })
        
        state["outliers"] = outliers
        return state
```

## 4. Database Management Agents

### Database Operations Agent
```python
class DatabaseOperationsAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.supabase_client = SupabaseClient()
        self.batch_size = 1000
    
    def _build_graph(self):
        workflow = StateGraph(DatabaseState)
        
        workflow.add_node("prepare_data", self.prepare_data)
        workflow.add_node("upsert_products", self.upsert_products)
        workflow.add_node("update_prices", self.update_prices)
        workflow.add_node("log_operations", self.log_operations)
        workflow.add_node("optimize_indexes", self.optimize_indexes)
        workflow.add_node("cleanup_old_data", self.cleanup_old_data)
        
        return workflow.compile()
    
    async def upsert_products(self, state: DatabaseState) -> DatabaseState:
        """Insert or update products in database"""
        try:
            products = state["validated_products"]
            
            # Process in batches
            for i in range(0, len(products), self.batch_size):
                batch = products[i:i + self.batch_size]
                
                # Prepare upsert data
                upsert_data = []
                for product in batch:
                    upsert_data.append({
                        "name": product["name"],
                        "normalized_name": product["normalized_name"],
                        "brand": product["brand"],
                        "barcode": product.get("barcode"),
                        "unit_type": product.get("unit"),
                        "image_url": product.get("image_url"),
                        "updated_at": datetime.now().isoformat()
                    })
                
                # Execute upsert
                result = await self.supabase_client.table("products").upsert(
                    upsert_data,
                    on_conflict="normalized_name,brand"
                ).execute()
                
                state["products_processed"] += len(batch)
        
        except Exception as e:
            state["database_errors"].append(str(e))
        
        return state
    
    async def update_prices(self, state: DatabaseState) -> DatabaseState:
        """Update current prices and price history"""
        try:
            # Update current_prices table
            current_prices = []
            price_history = []
            
            for product in state["validated_products"]:
                current_prices.append({
                    "store_product_id": product["store_product_id"],
                    "price": product["price"],
                    "original_price": product.get("original_price"),
                    "discount_percentage": product.get("discount_percentage"),
                    "is_promotion": product.get("is_promotion", False),
                    "promotion_text": product.get("promotion_text"),
                    "last_updated": datetime.now().isoformat()
                })
                
                price_history.append({
                    "store_product_id": product["store_product_id"],
                    "price": product["price"],
                    "original_price": product.get("original_price"),
                    "discount_percentage": product.get("discount_percentage"),
                    "is_promotion": product.get("is_promotion", False),
                    "promotion_text": product.get("promotion_text"),
                    "scraped_at": product["scraped_at"]
                })
            
            # Execute updates
            await self.supabase_client.table("current_prices").upsert(
                current_prices,
                on_conflict="store_product_id"
            ).execute()
            
            await self.supabase_client.table("price_history").insert(
                price_history
            ).execute()
            
            state["prices_updated"] = len(current_prices)
            
        except Exception as e:
            state["database_errors"].append(str(e))
        
        return state
```

## 5. Agent Communication and Coordination

### Message Passing System
```python
class AgentCommunicationHub:
    def __init__(self):
        self.message_queue = asyncio.Queue()
        self.agents = {}
        self.event_listeners = {}
    
    async def register_agent(self, agent_id: str, agent: Any):
        """Register an agent with the communication hub"""
        self.agents[agent_id] = agent
        
    async def send_message(self, from_agent: str, to_agent: str, message: Dict[str, Any]):
        """Send message between agents"""
        await self.message_queue.put({
            "from": from_agent,
            "to": to_agent,
            "message": message,
            "timestamp": datetime.now()
        })
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all listening agents"""
        for agent_id, listeners in self.event_listeners.items():
            if event_type in listeners:
                await self.send_message("hub", agent_id, {
                    "event_type": event_type,
                    "data": data
                })
```

## 6. Error Handling and Recovery

### Error Recovery Agent
```python
class ErrorRecoveryAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.retry_strategies = {
            "network_error": self.network_error_recovery,
            "rate_limit": self.rate_limit_recovery,
            "parsing_error": self.parsing_error_recovery,
            "database_error": self.database_error_recovery
        }
    
    def _build_graph(self):
        workflow = StateGraph(ErrorState)
        
        workflow.add_node("classify_error", self.classify_error)
        workflow.add_node("determine_strategy", self.determine_strategy)
        workflow.add_node("execute_recovery", self.execute_recovery)
        workflow.add_node("log_recovery", self.log_recovery)
        workflow.add_node("notify_admin", self.notify_admin)
        
        return workflow.compile()
    
    async def classify_error(self, state: ErrorState) -> ErrorState:
        """Classify the type of error and determine recovery strategy"""
        error = state["error"]
        
        if "network" in str(error).lower() or "timeout" in str(error).lower():
            state["error_type"] = "network_error"
        elif "rate limit" in str(error).lower() or "429" in str(error):
            state["error_type"] = "rate_limit"
        elif "parsing" in str(error).lower() or "html" in str(error).lower():
            state["error_type"] = "parsing_error"
        elif "database" in str(error).lower() or "connection" in str(error).lower():
            state["error_type"] = "database_error"
        else:
            state["error_type"] = "unknown"
        
        return state
    
    async def execute_recovery(self, state: ErrorState) -> ErrorState:
        """Execute the appropriate recovery strategy"""
        error_type = state["error_type"]
        
        if error_type in self.retry_strategies:
            recovery_result = await self.retry_strategies[error_type](state)
            state["recovery_result"] = recovery_result
        else:
            state["recovery_result"] = {"success": False, "message": "No recovery strategy available"}
        
        return state
```

## 7. Performance Monitoring and Optimization

### Performance Monitor Agent
```python
class PerformanceMonitorAgent:
    def __init__(self):
        self.graph = self._build_graph()
        self.metrics_collector = MetricsCollector()
        self.alert_thresholds = {
            "scrape_duration": 300,  # 5 minutes
            "error_rate": 0.05,      # 5%
            "memory_usage": 0.80,    # 80%
            "cpu_usage": 0.70        # 70%
        }
    
    async def monitor_performance(self, state: MonitoringState) -> MonitoringState:
        """Monitor system performance and generate alerts"""
        metrics = await self.metrics_collector.collect_metrics()
        
        alerts = []
        for metric_name, threshold in self.alert_thresholds.items():
            if metrics.get(metric_name, 0) > threshold:
                alerts.append({
                    "metric": metric_name,
                    "current_value": metrics[metric_name],
                    "threshold": threshold,
                    "severity": self.calculate_severity(metrics[metric_name], threshold)
                })
        
        state["performance_metrics"] = metrics
        state["alerts"] = alerts
        
        return state
```

## Integration with Next.js Admin Panel

### API Endpoints for Agent Management
```python
# FastAPI endpoints for agent control
@app.post("/api/agents/start-scraping")
async def start_scraping(store: str, scrape_type: str):
    """Start scraping for a specific store"""
    result = await orchestrator.start_scraping(store, scrape_type)
    return {"success": True, "job_id": result.job_id}

@app.get("/api/agents/status")
async def get_agent_status():
    """Get status of all agents"""
    return await orchestrator.get_all_agent_status()

@app.post("/api/agents/stop")
async def stop_agent(agent_id: str):
    """Stop a specific agent"""
    result = await orchestrator.stop_agent(agent_id)
    return {"success": result}
```

This LangGraph architecture provides a robust, scalable system for managing your grocery scraping operations with intelligent agents that can adapt, recover from errors, and optimize performance automatically.