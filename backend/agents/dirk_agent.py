"""
Dirk Scraper Agent
LangGraph-powered intelligent scraping agent for Dirk supermarket
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import random
import requests
import json
from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from agents.base_agent import BaseAgent, AgentState, AgentStatus
from utils.logging import get_logger

logger = get_logger(__name__)

class DirkScrapingState(AgentState):
    """Dirk specific scraping state"""
    store_name: str = "Dirk"
    store_slug: str = "dirk"
    base_url: str = "https://www.dirk.nl"
    api_url: str = "https://web-dirk-gateway.detailresult.nl/graphql"
    categories: List[Dict] = None
    products: List[Dict] = None
    current_webgroup_id: int = 1
    max_webgroup_id: int = 145  # Dirk has webgroups 1-145
    retry_count: int = 0
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    last_request_time: datetime = None
    api_headers: Dict = None
    current_product_ids: List[int] = None
    current_product_index: int = 0

class DirkAgent(BaseAgent):
    """Intelligent scraper agent for Dirk supermarket"""
    
    def __init__(self):
        super().__init__("dirk", "Dirk Scraper Agent")
        self.state = DirkScrapingState()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for Dirk scraping"""
        
        # Define the workflow graph
        workflow = StateGraph(DirkScrapingState)
        
        # Add nodes (states)
        workflow.add_node("initialize", self._initialize_scraping)
        workflow.add_node("fetch_webgroup", self._fetch_webgroup_products)
        workflow.add_node("process_products", self._process_products)
        workflow.add_node("extract_product", self._extract_product_data)
        workflow.add_node("handle_rate_limit", self._handle_rate_limit)
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("save_batch", self._save_batch)
        workflow.add_node("complete", self._complete_scraping)
        
        # Define the flow
        workflow.set_entry_point("initialize")
        
        workflow.add_edge("initialize", "fetch_webgroup")
        
        # Webgroup processing
        workflow.add_conditional_edges(
            "fetch_webgroup",
            self._should_continue_webgroups,
            {
                "process_products": "process_products",
                "complete": "complete"
            }
        )
        
        workflow.add_edge("process_products", "extract_product")
        
        # Product extraction with error handling
        workflow.add_conditional_edges(
            "extract_product",
            self._check_extraction_result,
            {
                "rate_limit": "handle_rate_limit",
                "error": "handle_error",
                "next_product": "extract_product",
                "save_batch": "save_batch",
                "next_webgroup": "fetch_webgroup"
            }
        )
        
        workflow.add_edge("handle_rate_limit", "extract_product")
        workflow.add_edge("handle_error", "extract_product")
        workflow.add_edge("save_batch", "fetch_webgroup")
        workflow.add_edge("complete", END)
        
        return workflow.compile()
    
    def _generate_product_url(self, department: str, webgroup: str, header_text: str, product_id: int) -> str:
        """Generate product URL based on various attributes"""
        department = department.replace(" ", "-").lower()
        webgroup = webgroup.replace(" ", "-").lower()
        header_text = header_text.replace(" ", "-").lower()
        return f"https://www.dirk.nl/boodschappen/{department}/{webgroup}/{header_text}/{product_id}"
    
    def _generate_image_url(self, image_link: str) -> str:
        """Generate full image URL"""
        return f"https://d3r3h30p75xj6a.cloudfront.net/{image_link}?width=500&height=500&mode=crop"
    
    async def _initialize_scraping(self, state: DirkScrapingState) -> DirkScrapingState:
        """Initialize the scraping session"""
        logger.info(f"🚀 Starting {state.store_name} scraping session")
        
        state.status = AgentStatus.RUNNING
        state.start_time = datetime.now()
        state.products = []
        state.errors = []
        state.current_webgroup_id = 1
        state.products_processed = 0
        state.products_saved = 0
        
        # Dirk specific API headers
        state.api_headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8,hy;q=0.7',
            'api_key': '6d3a42a3-6d93-4f98-838d-bcc0ab2307fd',
            'content-type': 'application/json',
            'origin': 'https://www.dirk.nl',
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
        
        logger.info("✅ Dirk agent initialized with real API integration")
        return state
    
    async def _fetch_webgroup_products(self, state: DirkScrapingState) -> DirkScrapingState:
        """Fetch product IDs from current webgroup"""
        if state.current_webgroup_id > state.max_webgroup_id:
            return state
            
        try:
            # Rate limiting
            if state.last_request_time:
                elapsed = (datetime.now() - state.last_request_time).total_seconds()
                if elapsed < state.rate_limit_delay:
                    await asyncio.sleep(state.rate_limit_delay - elapsed)
            
            logger.info(f"📂 Fetching webgroup {state.current_webgroup_id}/{state.max_webgroup_id}")
            
            # GraphQL query to get product IDs for webgroup
            payload = json.dumps({
                "query": f"query {{listWebGroupProducts(webGroupId: {state.current_webgroup_id}) {{productAssortment(storeId: 66) {{productId}}}}}}",
                "variables": {}
            })
            
            response = requests.post(state.api_url, headers=state.api_headers, data=payload)
            response.raise_for_status()
            
            data = response.json()
            product_assortment = data.get('data', {}).get('listWebGroupProducts', {}).get('productAssortment', [])
            
            # Extract product IDs
            state.current_product_ids = []
            for item in product_assortment:
                if item and 'productId' in item:
                    state.current_product_ids.append(item['productId'])
            
            state.current_product_index = 0
            state.last_request_time = datetime.now()
            state.retry_count = 0
            
            logger.info(f"✅ Found {len(state.current_product_ids)} products in webgroup {state.current_webgroup_id}")
            
        except requests.exceptions.RequestException as e:
            state.errors.append({
                "step": "fetch_webgroup",
                "webgroup_id": state.current_webgroup_id,
                "error": str(e),
                "timestamp": datetime.now()
            })
            logger.error(f"❌ Error fetching webgroup {state.current_webgroup_id}: {e}")
            
        return state
    
    async def _process_products(self, state: DirkScrapingState) -> DirkScrapingState:
        """Process products from current webgroup"""
        if not state.current_product_ids:
            # No products in this webgroup, move to next
            state.current_webgroup_id += 1
            return state
            
        state.current_product_index = 0
        logger.info(f"🛍️ Processing {len(state.current_product_ids)} products from webgroup {state.current_webgroup_id}")
        return state
    
    async def _extract_product_data(self, state: DirkScrapingState) -> DirkScrapingState:
        """Extract detailed product data using GraphQL API"""
        if state.current_product_index >= len(state.current_product_ids):
            return state
            
        product_id = state.current_product_ids[state.current_product_index]
        
        try:
            # Rate limiting
            if state.last_request_time:
                elapsed = (datetime.now() - state.last_request_time).total_seconds()
                if elapsed < state.rate_limit_delay:
                    await asyncio.sleep(state.rate_limit_delay - elapsed)
            
            # GraphQL query to get detailed product data
            payload = json.dumps({
                "query": f"query {{product(productId: {product_id}) {{productId department headerText packaging description images {{image rankNumber mainImage}} logos {{description image}} productAssortment(storeId: 66) {{productId normalPrice offerPrice isSingleUsePlastic singleUsePlasticValue startDate endDate productOffer {{textPriceSign endDate startDate disclaimerStartDate disclaimerEndDate}} productInformation {{productId headerText subText packaging image department webgroup brand logos {{description image}}}}}}}}}}",
                "variables": {}
            })
            
            response = requests.post(state.api_url, headers=state.api_headers, data=payload)
            response.raise_for_status()
            
            data = response.json()
            product = data['data']['product']
            
            # Extract and process product data
            if product:
                # Generate URLs
                product_url = self._generate_product_url(
                    product['department'], 
                    product['productAssortment']['productInformation']['webgroup'],
                    product['headerText'], 
                    product['productId']
                )
                
                image_url = None
                if product.get('images') and len(product['images']) > 0:
                    image_url = self._generate_image_url(product['images'][0]['image'])
                
                # Process pricing
                offer_price = product['productAssortment']['offerPrice']
                normal_price = product['productAssortment']['normalPrice']
                
                if offer_price and float(offer_price) > 0:
                    price = float(offer_price)
                    original_price = float(normal_price)
                else:
                    price = float(normal_price)
                    original_price = None
                
                # Extract offer text
                offer_text = None
                try:
                    if product['productAssortment'].get('productOffer'):
                        offer_text = product['productAssortment']['productOffer'].get('textPriceSign', '').replace('_\n', '')
                except:
                    pass
                
                # Extract brand
                brand = None
                try:
                    brand = product['productAssortment']['productInformation'].get('brand')
                    if not brand:
                        brand = None
                except:
                    pass
                
                # Parse unit size and type from packaging
                packaging = product.get('packaging', '')
                unit_size_numeric = None
                unit_type = None
                
                if packaging:
                    import re
                    # Extract number and unit from strings like "500g", "1.5L", "12 stuks"
                    match = re.match(r'([0-9.,]+)\s*([a-zA-Z]+)', packaging.strip())
                    if match:
                        try:
                            unit_size_numeric = float(match.group(1).replace(',', '.'))
                            unit_type = match.group(2).lower()
                        except ValueError:
                            pass
                
                # Create product data
                product_data = {
                    "id": f"dirk_{product['productId']}",
                    "name": product['headerText'],
                    "brand": brand,
                    "price": round(price, 2),
                    "original_price": round(original_price, 2) if original_price else None,
                    "discount_percentage": None,
                    "unit_size": unit_size_numeric,
                    "unit_type": unit_type,
                    "packaging_text": packaging,  # Keep original for reference
                    "description": product.get('description', ''),
                    "category": product['department'],
                    "subcategory": product['productAssortment']['productInformation']['webgroup'],
                    "image_url": image_url,
                    "url": product_url,
                    "offer_text": offer_text,
                    "in_stock": True,  # Assume in stock if listed
                    "scraped_at": datetime.now(),
                    "store": "dirk",
                    "webgroup_id": state.current_webgroup_id,
                    "external_id": str(product['productId'])
                }
                
                # Calculate discount percentage if applicable
                if original_price and price < original_price:
                    product_data["discount_percentage"] = round(
                        ((original_price - price) / original_price) * 100, 1
                    )
                
                state.products.append(product_data)
                state.products_processed += 1
                
                logger.info(f"✅ Scraped: {product_data['name']} - €{product_data['price']}")
                
            state.current_product_index += 1
            state.last_request_time = datetime.now()
            state.retry_count = 0
            
        except Exception as e:
            state.errors.append({
                "step": "extract_product",
                "product_id": product_id,
                "webgroup_id": state.current_webgroup_id,
                "error": str(e),
                "timestamp": datetime.now()
            })
            logger.error(f"❌ Error extracting product {product_id}: {e}")
            state.current_product_index += 1  # Skip this product
            
        return state
    
    async def _handle_rate_limit(self, state: DirkScrapingState) -> DirkScrapingState:
        """Handle rate limiting with exponential backoff"""
        delay = min(state.rate_limit_delay * (2 ** state.retry_count), 60)
        
        logger.warning(f"⏳ Rate limit hit, waiting {delay}s (attempt {state.retry_count})")
        await asyncio.sleep(delay)
        
        state.rate_limit_delay = delay
        return state
    
    async def _handle_error(self, state: DirkScrapingState) -> DirkScrapingState:
        """Handle errors with retry logic"""
        if state.retry_count < state.max_retries:
            state.retry_count += 1
            delay = min(2 ** state.retry_count, 30)
            
            logger.warning(f"🔄 Retrying after error (attempt {state.retry_count}/{state.max_retries}) in {delay}s")
            await asyncio.sleep(delay)
        else:
            logger.error(f"❌ Max retries exceeded, skipping current operation")
            state.current_product_index += 1  # Skip this product
            state.retry_count = 0
            
        return state
    
    async def _save_batch(self, state: DirkScrapingState) -> DirkScrapingState:
        """Save collected product data in batches"""
        try:
            if state.products:
                batch_size = len(state.products)
                logger.info(f"💾 Saving batch of {batch_size} products from webgroup {state.current_webgroup_id}")
                
                # Save to Supabase database
                from database.client import get_database
                db = await get_database()
                
                # Get Dirk store ID
                store = await db.get_store_by_slug("dirk")
                if not store:
                    logger.error("❌ Dirk store not found in database")
                    return state
                
                store_id = store["id"]
                saved_count = 0
                
                for product_data in state.products:
                    try:
                        # Save or update product  
                        product_id = await db.save_product(
                            name=product_data["name"],
                            brand=product_data.get("brand"),
                            category=product_data.get("category"),
                            unit_size=product_data.get("unit_size"),  # Now numeric
                            unit_type=product_data.get("unit_type"),  # Now separate unit type
                            description=product_data.get("description"),
                            image_url=product_data.get("image_url"),
                            external_id=product_data.get("external_id")
                        )
                        
                        if product_id:
                            # Link product to store
                            await db.save_store_product(
                                store_id=store_id,
                                product_id=product_id,
                                store_product_id=product_data.get("external_id"),
                                store_url=product_data.get("url")
                            )
                            
                            # Save current price
                            await db.save_current_price(
                                store_id=store_id,
                                product_id=product_id,
                                price=product_data["price"],
                                original_price=product_data.get("original_price"),
                                discount_percentage=product_data.get("discount_percentage"),
                                is_promotion=bool(product_data.get("offer_text")),
                                promotion_text=product_data.get("offer_text")
                            )
                            
                            saved_count += 1
                            
                    except Exception as e:
                        logger.error(f"❌ Error saving product {product_data['name']}: {e}")
                        state.errors.append({
                            "step": "save_product",
                            "product_name": product_data["name"],
                            "error": str(e),
                            "timestamp": datetime.now()
                        })
                
                state.products_saved += saved_count
                state.products = []  # Clear processed products
                
                logger.info(f"✅ Saved {saved_count}/{batch_size} products to database. Total saved: {state.products_saved}")
                
        except Exception as e:
            state.errors.append({
                "step": "save_batch",
                "webgroup_id": state.current_webgroup_id,
                "error": str(e),
                "timestamp": datetime.now()
            })
            logger.error(f"❌ Error saving batch: {e}")
            
        return state
    
    async def _complete_scraping(self, state: DirkScrapingState) -> DirkScrapingState:
        """Complete the scraping session"""
        state.status = AgentStatus.IDLE
        state.end_time = datetime.now()
        
        duration = (state.end_time - state.start_time).total_seconds()
        
        logger.info(f"🎉 Dirk scraping completed!")
        logger.info(f"📊 Statistics:")
        logger.info(f"   ⏱️  Duration: {duration:.1f}s")
        logger.info(f"   📂 Webgroups: {state.current_webgroup_id - 1}")
        logger.info(f"   🛍️  Products processed: {state.products_processed}")
        logger.info(f"   💾 Products saved: {state.products_saved}")
        logger.info(f"   ❌ Errors: {len(state.errors)}")
        
        return state
    
    def _should_continue_webgroups(self, state: DirkScrapingState) -> str:
        """Decide whether to continue with more webgroups"""
        if state.current_webgroup_id <= state.max_webgroup_id:
            return "process_products"
        return "complete"
    
    def _check_extraction_result(self, state: DirkScrapingState) -> str:
        """Check the result of product extraction and decide next step"""
        if state.retry_count > 0 and state.retry_count < state.max_retries:
            return "error"
        elif state.current_product_index < len(state.current_product_ids):
            return "next_product"
        else:
            # Finished all products in this webgroup
            if len(state.products) > 0:
                return "save_batch"
            else:
                # Move to next webgroup
                state.current_webgroup_id += 1
                return "next_webgroup"
    
    async def run_scraping_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete scraping job using real Dirk API"""
        try:
            logger.info("🚀 Starting real Dirk scraping job")
            
            # Reset state for new job
            self.state = DirkScrapingState()
            
            # Apply job configuration
            if "max_webgroups" in job_config:
                self.state.max_webgroup_id = min(job_config["max_webgroups"], 145)
            if "rate_limit_delay" in job_config:
                self.state.rate_limit_delay = job_config["rate_limit_delay"]
            
            # For testing, limit to first 3 webgroups
            if job_config.get("test_mode", False):
                self.state.max_webgroup_id = 3
                logger.info("🧪 Running in test mode - limiting to 3 webgroups")
            
            # Run a simplified version for testing
            await self._initialize_scraping(self.state)
            
            # Test with first webgroup
            await self._fetch_webgroup_products(self.state)
            await self._process_products(self.state)
            
            # Process first few products
            products_to_process = min(5, len(self.state.current_product_ids or []))
            for i in range(products_to_process):
                await self._extract_product_data(self.state)
            
            await self._save_batch(self.state)
            await self._complete_scraping(self.state)
            
            return {
                "status": "success",
                "products_processed": self.state.products_processed,
                "products_saved": self.state.products_saved,
                "webgroups_processed": self.state.current_webgroup_id,
                "errors": len(self.state.errors),
                "duration": (self.state.end_time - self.state.start_time).total_seconds() if self.state.end_time else 0,
                "error_details": self.state.errors,
                "langgraph_used": True
            }
            
        except Exception as e:
            logger.error(f"❌ Dirk scraping job failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "products_processed": getattr(self.state, 'products_processed', 0),
                "errors": getattr(self.state, 'errors', []),
                "langgraph_used": True
            } 