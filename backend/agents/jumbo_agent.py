"""
Jumbo Scraper Agent
LangGraph-powered intelligent scraping agent for Jumbo supermarket
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import random
import aiohttp
import json
import math
import time
import logging
from pathlib import Path

# LangGraph imports
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

class JumboScrapingState(AgentState):
    """Jumbo specific scraping state"""
    store_name: str = "Jumbo"
    store_slug: str = "jumbo"
    base_url: str = "https://www.jumbo.com"
    api_url: str = "https://www.jumbo.com/api/graphql"
    categories: List[Dict] = None
    products: List[Dict] = None
    current_category: str = None
    page_number: int = 1
    max_pages: int = 3  # Limit for testing
    retry_count: int = 0
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    last_request_time: datetime = None
    current_page_urls: List[str] = None

class JumboAgent(BaseAgent):
    """Jumbo scraper agent with real API integration and LangGraph state management."""
    
    def __init__(self):
        super().__init__("jumbo", "Jumbo Scraper Agent")
        
        # Real Jumbo scraping configuration
        self.max_concurrent = 5
        self.batch_size = 50
        self.delay_range = (1, 3)
        self.session = None
        
        # Jumbo API configuration
        self.base_url = "https://www.jumbo.com"
        self.api_url = f"{self.base_url}/api/graphql"
        self.products_per_page = 24
        
        # Real Jumbo categories (matching working script)
        self.categories = [
            "drogisterij-en-baby",
            "diepvries",
            "baby-peuter", 
            "brood-en-gebak",
            "conserven,-soepen,-sauzen,-olien",
            "koffie-en-thee",
            "ontbijt,-broodbeleg-en-bakproducten",
            "wereldkeukens,-kruiden,-pasta-en-rijst",
            "vleeswaren,-kaas-en-tapas",
            "aardappelen,-groente-en-fruit",
            "zuivel,-eieren,-boter",
            "vlees,-vis-en-vega",
            "verse-maaltijden-en-gemak",
            "koek,-snoep,-chocolade-en-chips",
            "bier-en-wijn",
            "frisdrank-en-sappen",
            "huishouden-en-dieren"
        ]
        
        # Headers from working script
        self.headers = {
            "authority": "www.jumbo.com",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://www.jumbo.com",
            "referer": "https://www.jumbo.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }
        
        # GraphQL query from working script
        self.graphql_query = """
        query SearchProducts($input: ProductSearchInput!, $shelfTextInput: ShelfTextInput!) {
          searchProducts(input: $input) {
            pageHeader {
              headerText
              count
              __typename
            }
            start
            count
            products {
              ...SearchProductDetails
              __typename
            }
            __typename
          }
          getCategoryShelfText(input: $shelfTextInput) {
            shelfText
            __typename
          }
        }
        
        fragment SearchProductDetails on Product {
          id: sku
          brand
          category: rootCategory
          subtitle: packSizeDisplay
          title
          image
          inAssortment
          availability {
            availability
            isAvailable
            label
            stockLimit
            reason
            availabilityNote
            __typename
          }
          sponsored
          auctionId
          link
          retailSet
          prices: price {
            price
            promoPrice
            pricePerUnit {
              price
              unit
              __typename
            }
            __typename
          }
          quantityDetails {
            maxAmount
            minAmount
            stepAmount
            defaultAmount
            __typename
          }
          primaryBadge: primaryProductBadges {
            alt
            image
            __typename
          }
          secondaryBadges: secondaryProductBadges {
            alt
            image
            __typename
          }
          promotions {
            id
            group
            isKiesAndMix
            image
            tags {
              text
              inverse
              __typename
            }
            start {
              dayShort
              date
              monthShort
              __typename
            }
            end {
              dayShort
              date
              monthShort
              __typename
            }
            primaryBadge: primaryBadges {
              alt
              image
              __typename
            }
            volumeDiscounts {
              discount
              volume
              __typename
            }
            durationTexts {
              shortTitle
              __typename
            }
            __typename
          }
          surcharges {
            type
            value {
              amount
              currency
              __typename
            }
            __typename
          }
          characteristics {
            freshness {
              name
              value
              url
              __typename
            }
            logo {
              name
              value
              url
              __typename
            }
            tags {
              url
              name
              value
              __typename
            }
            __typename
          }
          __typename
        }
        """
        
        # Progress tracking
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limited = 0
        
        self.state = JumboScrapingState()
        self.graph = self._build_graph()

    async def create_session(self):
        """Create aiohttp session with proper configuration (from working script)"""
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=self.max_concurrent,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        # Create cookie jar
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            cookie_jar=cookie_jar,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        # Get initial cookies like working script
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"'
            }
            async with self.session.get(self.base_url, headers=headers, allow_redirects=True) as response:
                await response.text()
                logger.info("Got initial Jumbo cookies")
        except Exception as e:
            logger.error(f"Failed to get initial cookies: {str(e)}")

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            logger.info("Closed Jumbo scraping session")

    async def execute_graphql_query(self, variables: dict, retry_count: int = 0) -> Optional[dict]:
        """Execute GraphQL query with retry logic (from working script)"""
        max_retries = 3
        try:
            # Add delay to avoid rate limiting
            await asyncio.sleep(random.uniform(*self.delay_range))
            
            # Update headers with proper referrer
            headers = self.headers.copy()
            category_url = variables["input"]["friendlyUrl"]
            headers["referer"] = f"https://www.jumbo.com/{category_url}"
            
            payload = {
                "operationName": "SearchProducts",
                "query": self.graphql_query,
                "variables": variables
            }
            
            async with self.session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data:
                        self.successful_requests += 1
                        return data
                    else:
                        logger.error(f"Invalid response structure: {data}")
                        return None
                
                elif response.status == 429:  # Rate limited
                    self.rate_limited += 1
                    if retry_count < max_retries:
                        wait_time = (2 ** retry_count) * 5
                        logger.warning(f"⏳ Rate limited, retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        return await self.execute_graphql_query(variables, retry_count + 1)
                    return None
                
                else:
                    response_text = await response.text()
                    logger.error(f"❌ HTTP {response.status} response: {response_text}")
                    if retry_count < max_retries:
                        wait_time = (2 ** retry_count) * 2
                        logger.warning(f"🔄 HTTP {response.status}, retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        return await self.execute_graphql_query(variables, retry_count + 1)
                    self.failed_requests += 1
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Request failed: {str(e)}")
            if retry_count < max_retries:
                wait_time = (2 ** retry_count) * 2
                logger.warning(f"🔄 Request failed: {str(e)}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                return await self.execute_graphql_query(variables, retry_count + 1)
            self.failed_requests += 1
            return None

    async def get_category_products(self, category: str) -> List[Dict[str, Any]]:
        """Get all products for a category (from working script)"""
        logger.info(f"🚀 Processing category: {category}")
        
        # Get initial count using correct Jumbo API structure
        variables = {
            "input": {
                "searchType": "category",
                "searchTerms": "producten",
                "friendlyUrl": category,
                "offSet": 0,
                "currentUrl": f"/producten/{category}",
                "previousUrl": "",
                "bloomreachCookieId": ""
            },
            "shelfTextInput": {
                "searchType": "category",
                "friendlyUrl": category
            }
        }
        
        initial_data = await self.execute_graphql_query(variables)
        if not initial_data or 'data' not in initial_data:
            logger.error(f"❌ Failed to get initial data for {category}")
            return []
        
        try:
            total_count = initial_data['data']['searchProducts']['pageHeader']['count']
            pages = math.ceil(total_count / self.products_per_page)
            logger.info(f"ℹ️ Category {category}: {total_count} products across {pages} pages")
            
            all_products = []
            initial_products = initial_data['data']['searchProducts']['products']
            all_products.extend(initial_products)
            
            # Process remaining pages (limit to 3 pages for testing)
            max_test_pages = min(pages, 3)
            for page in range(1, max_test_pages):
                offset = page * self.products_per_page
                variables = {
                    "input": {
                        "searchType": "category",
                        "searchTerms": "producten",
                        "friendlyUrl": category,
                        "offSet": offset,
                        "currentUrl": f"/producten/{category}",
                        "previousUrl": "",
                        "bloomreachCookieId": ""
                    },
                    "shelfTextInput": {
                        "searchType": "category",
                        "friendlyUrl": category
                    }
                }
                
                page_data = await self.execute_graphql_query(variables)
                if page_data and 'data' in page_data:
                    products = page_data['data']['searchProducts']['products']
                    all_products.extend(products)
                    logger.info(f"📥 {category} page {page}: Found {len(products)} products")
                else:
                    logger.error(f"❌ Failed to fetch {category} page {page}")
            
            return all_products
            
        except Exception as e:
            logger.error(f"❌ Error processing {category}: {str(e)}")
            return []

    def _parse_jumbo_products(self, products: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
        """Parse Jumbo product data into standardized format"""
        parsed_products = []
        
        for product in products:
            try:
                # Extract basic product info
                product_info = {
                    "id": product.get("id", ""),
                    "name": product.get("title", "Unknown Product"),
                    "brand": product.get("brand", "Unknown"),
                    "category": category,
                    "subtitle": product.get("subtitle", ""),
                    "description": product.get("title", ""),
                    "image_url": product.get("image", ""),
                    "link": product.get("link", ""),
                    "in_stock": product.get("availability", {}).get("isAvailable", False),
                    "availability_label": product.get("availability", {}).get("label", ""),
                    "store_id": "jumbo",
                    "scraped_at": datetime.now().isoformat()
                }
                
                # Extract price information
                prices = product.get("prices", {})
                if prices:
                    product_info["price"] = prices.get("price", 0.0)
                    product_info["promo_price"] = prices.get("promoPrice")
                    
                    # Unit price info
                    unit_price = prices.get("pricePerUnit", {})
                    if unit_price:
                        product_info["unit_price"] = unit_price.get("price", 0.0)
                        product_info["unit"] = unit_price.get("unit", "")
                
                # Extract promotions
                promotions = product.get("promotions", [])
                if promotions:
                    promotion = promotions[0]  # Get first promotion
                    product_info["has_promotion"] = True
                    product_info["promotion_id"] = promotion.get("id", "")
                    promotion_tags = promotion.get("tags", [])
                    if promotion_tags:
                        product_info["promotion_text"] = promotion_tags[0].get("text", "")
                else:
                    product_info["has_promotion"] = False
                
                parsed_products.append(product_info)
                
            except Exception as e:
                logger.error(f"Error parsing product: {e}")
                continue
                
        return parsed_products

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for Jumbo scraping"""
        
        # Define the workflow graph
        workflow = StateGraph(JumboScrapingState)
        
        # Add nodes (states)
        workflow.add_node("initialize", self._initialize_scraping)
        workflow.add_node("scrape_categories", self._scrape_categories)
        workflow.add_node("complete", self._complete_scraping)
        
        # Define the flow
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "scrape_categories")
        workflow.add_edge("scrape_categories", "complete")
        workflow.add_edge("complete", END)
        
        return workflow.compile()
    
    async def _initialize_scraping(self, state: JumboScrapingState) -> JumboScrapingState:
        """Initialize the scraping session"""
        logger.info("🚀 Initializing Jumbo scraping")
        
        state.status = AgentStatus.RUNNING
        state.start_time = datetime.now()
        state.products = []
        state.errors = []
        
        # Create session
        await self.create_session()
        
        logger.info("✅ Initialized Jumbo scraping session")
        return state
    
    async def _scrape_categories(self, state: JumboScrapingState) -> JumboScrapingState:
        """Scrape products from Jumbo categories"""
        logger.info("📂 Starting to scrape Jumbo categories")
        
        all_products = []
        
        # Test with limited categories for now
        test_categories = self.categories[:2]  # Just first 2 categories
        
        for category in test_categories:
            try:
                logger.info(f"🚀 Processing category: {category}")
                
                # Get products for this category
                products = await self.get_category_products(category)
                
                if products:
                    # Parse products
                    parsed_products = self._parse_jumbo_products(products, category)
                    all_products.extend(parsed_products)
                    
                    logger.info(f"✅ {category}: Found {len(parsed_products)} products")
                    
                    # Add to state
                    state.products.extend(parsed_products)
                else:
                    logger.warning(f"⚠️ No products found for category: {category}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing category {category}: {e}")
                state.errors.append({
                    "category": category,
                    "error": str(e),
                    "timestamp": datetime.now()
                })
                continue
        
        state.products_processed = len(all_products)
        
        logger.info(f"📊 Scraping completed: {len(all_products)} products from {len(test_categories)} categories")
        
        return state
    
    async def _complete_scraping(self, state: JumboScrapingState) -> JumboScrapingState:
        """Complete the scraping session"""
        logger.info("🎉 Completing Jumbo scraping")
        
        # Close session
        await self.close_session()
        
        # Final stats
        state.status = AgentStatus.COMPLETED
        state.end_time = datetime.now()
        
        logger.info(f"✅ Jumbo scraping completed successfully")
        logger.info(f"📊 Final stats: {len(state.products)} products processed")
        
        return state
    
    async def test_scraper(self, max_products: int = 5) -> Dict[str, Any]:
        """Test the scraper with limited products"""
        logger.info("🧪 Testing Jumbo scraper")
        
        try:
            # Create session
            await self.create_session()
            
            # Test with one category
            test_category = self.categories[0]  # First category
            
            start_time = time.time()
            
            # Get products
            products = await self.get_category_products(test_category)
            
            if products:
                # Parse and limit products
                parsed_products = self._parse_jumbo_products(products, test_category)
                limited_products = parsed_products[:max_products]
                
                duration = time.time() - start_time
                
                return {
                    "status": "success",
                    "products_found": len(limited_products),
                    "duration": duration,
                    "errors": 0,
                    "products": limited_products
                }
            else:
                return {
                    "status": "failed",
                    "error": "No products found",
                    "products_found": 0,
                    "duration": time.time() - start_time
                }
                
        except Exception as e:
            logger.error(f"❌ Jumbo scraper test failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "products_found": 0,
                "duration": time.time() - start_time if 'start_time' in locals() else 0
            }
        finally:
            # Close session
            await self.close_session()
    
    async def run_scraping_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete scraping job using real Jumbo API"""
        try:
            logger.info("🚀 Starting real Jumbo scraping job")
            
            # Reset state for new job
            self.state = JumboScrapingState()
            
            # For testing, use fallback method
            return await self._fallback_scraping()
                
        except Exception as e:
            logger.error(f"❌ Jumbo scraping job failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "products_processed": 0,
                "duration": 0,
                "langgraph_used": False
            }
    
    async def _fallback_scraping(self) -> Dict[str, Any]:
        """Fallback real scraping when LangGraph is not available."""
        logger.info("🔄 Running Jumbo fallback scraping")
        
        start_time = time.time()
        products = []
        errors = []
        
        # Use a smaller test batch
        test_categories = self.categories[:1]  # Just first category
        
        logger.info(f"🧪 Testing with category: {test_categories[0]}")
        
        # Create session
        await self.create_session()
        
        try:
            # Process test category
            category = test_categories[0]
            raw_products = await self.get_category_products(category)
            
            if raw_products:
                # Parse and limit products for testing
                parsed_products = self._parse_jumbo_products(raw_products, category)
                products = parsed_products[:5]  # Limit to 5 for testing
                
                logger.info(f"✅ Found {len(products)} products from {category}")
            else:
                errors.append(f"No products found for category: {category}")
            
        except Exception as e:
            logger.error(f"❌ Error in fallback scraping: {e}")
            errors.append(str(e))
        
        finally:
            await self.close_session()
        
        duration = time.time() - start_time
        
        return {
            "status": "success" if len(products) > 0 else "failed",
            "message": f"Jumbo fallback scraping completed - {len(products)} products found",
            "products_found": len(products),
            "duration": duration,
            "categories_processed": len(test_categories) if products else 0,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limited": self.rate_limited,
            "errors": errors,
            "sample_products": products[:3],  # First 3 products
            "langgraph_used": False
        } 