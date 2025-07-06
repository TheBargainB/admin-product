"""
Albert Heijn Scraper Agent
LangGraph-powered intelligent scraping agent for Albert Heijn supermarket
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import random
import logging
import aiohttp
import json
import time
from pathlib import Path

# LangGraph imports - now available
try:
    from langgraph.graph import StateGraph, START, END
    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# Local imports
from agents.base_agent import BaseAgent, AgentState, AgentStatus
from database.models import AgentConfig
from database.client import get_database
from config.settings import settings

logger = logging.getLogger(__name__)

class AlbertHeijnScrapingState(AgentState):
    """Albert Heijn specific scraping state"""
    store_name: str = "Albert Heijn"
    store_slug: str = "albert_heijn"
    base_url: str = "https://www.ah.nl"
    api_url: str = "https://www.ah.nl/zoeken/api/products/search"
    products: List[Dict] = None
    current_batch: List[str] = None
    current_batch_num: int = 0
    batches_processed: int = 0
    retry_count: int = 0
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    last_request_time: datetime = None

class AlbertHeijnAgent(BaseAgent):
    """Albert Heijn scraper agent with LangGraph state management."""
    
    def __init__(self):
        super().__init__("albert_heijn", "Albert Heijn Scraper Agent")
        self.categories = [
            "aardappelen-groente-fruit", "vlees-kip-vis-vegetarisch", 
            "kaas-vleeswaren-tapas", "zuivel-plantaardig-eieren",
            "bakkerij", "ontbijt-beleg-tussendoor", "frisdrank-sappen-koffie-thee",
            "wijn-bier-aperitieven", "diepvries", "conserven-soepen-sauzen",
            "pasta-rijst-internationale-keuken", "snoep-koek-chips-noten",
            "baby-verzorging", "huishouden-huisdier", "koken-tafelen-non-food",
            "drogisterij-parfum", "biologisch"
        ]
        
        # Scraping configuration (matching working script)
        self.max_concurrent = 10
        self.batch_size = 100  # Match working script
        self.delay_range = (1, 3)
        self.session = None
        
        self.state = AlbertHeijnScrapingState()
        self.graph = self._build_graph()
        
        # 🔧 HOW TO GET VALID COOKIES & HEADERS (when AH site is working):
        # 1. Visit https://www.ah.nl in Chrome/Firefox
        # 2. Open Developer Tools (F12)
        # 3. Go to Network tab
        # 4. Search for any product to trigger API calls
        # 5. Look for requests to "/zoeken/api/products/search"
        # 6. Right-click → Copy → Copy as cURL
        # 7. Extract cookies and headers from the cURL command
        # 8. Update the headers below with real values
        
        self.headers = {
            "authority": "www.ah.nl",
            "method": "GET",
            "scheme": "https",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,ar;q=0.8",
            "cache-control": "max-age=0",
            # TODO: Add real cookies when AH site is working
            # "cookie": "sessionid=abc123; csrftoken=def456; _ga=GA1.2.123456789",
            "dnt": "1",
            "priority": "u=0, i",
            "referer": "https://www.ah.nl/",
            "sec-ch-ua": "\"Google Chrome\";v=\"137\", \"Chromium\";v=\"137\", \"Not/A)Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
        }
        self.timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        # Progress tracking
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limited = 0
        self.product_ids = []
    
    async def create_session(self):
        """Create aiohttp session with proper configuration"""
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=self.max_concurrent,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers=self.headers
        )
        logger.info("Created Albert Heijn scraping session")

    async def close_session(self):
        """Properly close the session"""
        if self.session:
            await self.session.close()
            logger.info("Closed Albert Heijn scraping session")

    def load_product_ids(self) -> List[str]:
        """Load product IDs from file"""
        file_path = Path(__file__).parent / "product_urls.txt"
        try:
            with open(file_path, "r") as f:
                urls = [line.strip() for line in f if line.strip()]
            
            # Extract product IDs from URLs
            product_ids = []
            for url in urls:
                try:
                    # Extract product ID from URL format: https://www.ah.nl/producten/product/wi12/petfles-0-25
                    if '/product/' in url:
                        parts = url.split('/product/')
                        if len(parts) > 1:
                            product_part = parts[1].split('/')[0]  # Get the ID part (e.g., 'wi12')
                            if product_part:
                                product_ids.append(product_part)
                except Exception as e:
                    logger.warning(f"Could not extract product ID from URL: {url} - {e}")
                    continue
            
            logger.info(f"Loaded {len(product_ids)} product IDs from {len(urls)} URLs in {file_path}")
            return product_ids
        except FileNotFoundError:
            logger.error(f"File {file_path} not found")
            return []
        except Exception as e:
            logger.error(f"Error loading product IDs: {str(e)}")
            return []

    async def fetch_product(self, product_id: str, semaphore: asyncio.Semaphore, retry_count: int = 0) -> Dict[str, Any]:
        """Fetch a single product with retry logic"""
        async with semaphore:
            url = f"https://www.ah.nl/zoeken/api/products/search?query={product_id}"
            max_retries = 3
            
            try:
                # Random delay to avoid being too predictable
                delay = random.uniform(*self.delay_range)
                await asyncio.sleep(delay)
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.successful_requests += 1
                        logger.info(f"✅ Successfully fetched {product_id}")
                        return {
                            "product_id": product_id,
                            "status": "success",
                            "data": data
                        }
                    
                    elif response.status == 429:  # Rate limited
                        self.rate_limited += 1
                        if retry_count < max_retries:
                            wait_time = (2 ** retry_count) * 5  # Exponential backoff
                            logger.warning(f"🔄 Rate limited for {product_id}, retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)
                            return await self.fetch_product(product_id, semaphore, retry_count + 1)
                        else:
                            logger.error(f"❌ Max retries exceeded for {product_id} (Rate limited)")
                            self.failed_requests += 1
                            return {
                                "product_id": product_id,
                                "status": "rate_limited",
                                "error": "Max retries exceeded"
                            }
                    
                    else:  # Other HTTP errors
                        if retry_count < max_retries and response.status >= 500:
                            wait_time = (2 ** retry_count) * 2
                            logger.warning(f"🔄 Server error for {product_id} (Status: {response.status}), retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)
                            return await self.fetch_product(product_id, semaphore, retry_count + 1)
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ Failed to fetch {product_id} (Status: {response.status})")
                            self.failed_requests += 1
                            return {
                                "product_id": product_id,
                                "status": "error",
                                "http_status": response.status,
                                "error": error_text[:200]  # Limit error text length
                            }
            
            except asyncio.TimeoutError:
                if retry_count < max_retries:
                    logger.warning(f"🔄 Timeout for {product_id}, retrying...")
                    await asyncio.sleep(2 ** retry_count)
                    return await self.fetch_product(product_id, semaphore, retry_count + 1)
                else:
                    logger.error(f"❌ Timeout exceeded for {product_id}")
                    self.failed_requests += 1
                    return {
                        "product_id": product_id,
                        "status": "timeout",
                        "error": "Request timeout"
                    }
            
            except Exception as e:
                logger.error(f"❌ Unexpected error for {product_id}: {str(e)}")
                self.failed_requests += 1
                return {
                    "product_id": product_id,
                    "status": "exception",
                    "error": str(e)
                }

    async def process_batch(self, product_batch: List[str], batch_num: int) -> List[Dict[str, Any]]:
        """Process a batch of products concurrently"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        logger.info(f"🚀 Processing batch {batch_num} with {len(product_batch)} products")
        
        tasks = [
            self.fetch_product(product_id, semaphore)
            for product_id in product_batch
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that weren't caught
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Batch exception for {product_batch[i]}: {str(result)}")
                processed_results.append({
                    "product_id": product_batch[i],
                    "status": "batch_exception",
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for Albert Heijn scraping"""
        
        # Define the workflow graph
        workflow = StateGraph(AlbertHeijnScrapingState)
        
        # Add nodes (states)
        workflow.add_node("initialize", self._initialize_scraping)
        workflow.add_node("process_batch", self._process_batch)
        workflow.add_node("complete", self._complete_scraping)
        
        # Define the flow
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "process_batch")
        workflow.add_edge("process_batch", "complete")
        workflow.add_edge("complete", END)
        
        return workflow.compile()
    
    async def _initialize_scraping(self, state: AlbertHeijnScrapingState) -> AlbertHeijnScrapingState:
        """Initialize the scraping process."""
        logger.info("🚀 Initializing Albert Heijn scraping")
        
        state.status = AgentStatus.RUNNING
        state.start_time = datetime.now()
        state.products = []
        state.errors = []
        
        # Load product IDs and create session
        self.product_ids = self.load_product_ids()
        if not self.product_ids:
            logger.error("No product IDs loaded - cannot proceed with scraping")
            state.status = AgentStatus.FAILED
            return state
            
        await self.create_session()
        logger.info(f"✅ Initialized Albert Heijn scraping with {len(self.product_ids)} products")
        
        # Reset progress tracking
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limited = 0
        
        return state
    
    async def _process_batch(self, state: AlbertHeijnScrapingState) -> AlbertHeijnScrapingState:
        """Process a batch of Albert Heijn products"""
        logger.info("📂 Starting to process Albert Heijn products")
        
        # For testing, process a small batch
        test_batch = self.product_ids[:5] if self.product_ids else []
        
        if test_batch:
            batch_results = await self.process_batch(test_batch, 1)
            
            # Convert API results to product format
            products = []
            for result in batch_results:
                if result.get("status") == "success" and result.get("data"):
                    product_data = self._parse_product_data(result["data"], result["product_id"])
                    if product_data:
                        products.extend(product_data)
            
            state.products.extend(products)
            state.batches_processed = 1
            state.products_processed = len(products)
            
            logger.info(f"✅ Processed {len(products)} products from test batch")
        else:
            logger.warning("⚠️ No product IDs available for processing")
        
        return state
    
    async def _complete_scraping(self, state: AlbertHeijnScrapingState) -> AlbertHeijnScrapingState:
        """Complete the scraping session"""
        logger.info("🎉 Completing Albert Heijn scraping")
        
        # Close session
        await self.close_session()
        
        # Final stats
        state.status = AgentStatus.COMPLETED
        state.end_time = datetime.now()
        
        logger.info(f"✅ Albert Heijn scraping completed successfully")
        logger.info(f"📊 Final stats: {len(state.products)} products processed")
        
        return state
    
    def _parse_product_data(self, api_data: Dict[str, Any], product_id: str) -> List[Dict[str, Any]]:
        """Parse API response data into product format."""
        products = []
        
        try:
            # Extract products from API response
            if "products" in api_data and isinstance(api_data["products"], list):
                for product in api_data["products"]:
                    try:
                        # Extract basic product info
                        product_info = {
                            "id": product.get("id", product_id),
                            "name": product.get("title", "Unknown Product"),
                            "price": self._extract_price(product),
                            "original_price": self._extract_original_price(product),
                            "category": product.get("category", {}).get("name", "Unknown"),
                            "brand": product.get("brand", {}).get("name", "Unknown"),
                            "description": product.get("description", ""),
                            "image_url": self._extract_image_url(product),
                            "availability": product.get("availability", {}).get("label", "Unknown"),
                            "is_available": product.get("availability", {}).get("orderable", False),
                            "unit_size": product.get("unitSize", ""),
                            "promotion_text": self._extract_promotion_text(product),
                            "store_id": "albert_heijn",
                            "scraped_at": datetime.now().isoformat()
                        }
                        
                        products.append(product_info)
                        
                    except Exception as e:
                        logger.error(f"Error parsing individual product: {e}")
                        continue
                        
            else:
                logger.warning(f"No products found in API response for {product_id}")
                
        except Exception as e:
            logger.error(f"Error parsing API data for {product_id}: {e}")
            
        return products
    
    def _extract_price(self, product: Dict[str, Any]) -> float:
        """Extract price from product data."""
        try:
            price_info = product.get("price", {})
            if "now" in price_info:
                return float(price_info["now"])
            elif "unitPrice" in price_info:
                return float(price_info["unitPrice"])
            else:
                return 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _extract_original_price(self, product: Dict[str, Any]) -> Optional[float]:
        """Extract original price before discount."""
        try:
            price_info = product.get("price", {})
            if "was" in price_info:
                return float(price_info["was"])
            return None
        except (ValueError, TypeError):
            return None
    
    def _extract_image_url(self, product: Dict[str, Any]) -> str:
        """Extract image URL from product data."""
        try:
            images = product.get("images", [])
            if images and isinstance(images, list):
                return images[0].get("url", "")
            return ""
        except (KeyError, IndexError, TypeError):
            return ""
    
    def _extract_promotion_text(self, product: Dict[str, Any]) -> str:
        """Extract promotion text from product data."""
        try:
            promotions = product.get("promotions", [])
            if promotions and isinstance(promotions, list):
                return promotions[0].get("description", "")
            return ""
        except (KeyError, IndexError, TypeError):
            return ""
    
    async def _generate_mock_products(self, category: str) -> List[Dict[str, Any]]:
        """Generate realistic mock products."""
        products = []
        count = random.randint(20, 50)
        
        for i in range(count):
            price = round(random.uniform(1.0, 15.0), 2)
            products.append({
                "id": f"ah_{category}_{i+1}",
                "name": f"Product {category} {i+1}",
                "price": price,
                "category": category,
                "description": f"Fresh {category} product",
                "image_url": f"https://static.ah.nl/images/{category}_{i+1}.jpg"
            })
        
        return products
    
    async def run_scraping_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete scraping job using real Albert Heijn API"""
        try:
            logger.info("🚀 Starting real Albert Heijn scraping job")
            
            # Reset state for new job
            self.state = AlbertHeijnScrapingState()
            
            # For testing, use fallback method
            return await self._fallback_scraping()
                
        except Exception as e:
            logger.error(f"❌ Albert Heijn scraping job failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "products_processed": 0,
                "duration": 0,
                "langgraph_used": False
            }
    
    async def _fallback_scraping(self) -> Dict[str, Any]:
        """Fallback real scraping when LangGraph is not available."""
        logger.info("🔄 Running Albert Heijn fallback scraping")
        
        start_time = time.time()
        products = []
        errors = []
        
        # Load product IDs
        product_ids = self.load_product_ids()
        if not product_ids:
            return {
                "status": "failed",
                "message": "No product IDs found - check product_urls.txt file",
                "products_found": 0,
                "duration": 0,
                "langgraph_used": False
            }
        
        # Use a smaller batch size for testing
        test_batch_size = 5
        test_products = product_ids[:test_batch_size]
        
        logger.info(f"🧪 Testing with {len(test_products)} products")
        
        # Create session
        await self.create_session()
        
        try:
            # Process test batch
            batch_results = await self.process_batch(test_products, 1)
            
            # Convert results to products
            for result in batch_results:
                if result.get("status") == "success" and result.get("data"):
                    product_data = self._parse_product_data(result["data"], result["product_id"])
                    if product_data:
                        products.extend(product_data)
                elif result.get("status") != "success":
                    errors.append(result.get("error", "Unknown error"))
            
            logger.info(f"✅ Found {len(products)} products from Albert Heijn")
            
        except Exception as e:
            logger.error(f"❌ Error in Albert Heijn scraping: {e}")
            errors.append(str(e))
        
        finally:
            await self.close_session()
        
        duration = time.time() - start_time
        
        return {
            "status": "success" if len(products) > 0 else "failed",
            "message": f"Albert Heijn fallback scraping completed - {len(products)} products found",
            "products_found": len(products),
            "duration": duration,
            "batches_processed": 1,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limited": self.rate_limited,
            "errors": errors,
            "sample_products": products[:3],  # First 3 products
            "langgraph_used": False
        } 