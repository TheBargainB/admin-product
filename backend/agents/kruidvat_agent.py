"""
Kruidvat Scraper Agent
LangGraph-powered intelligent scraping agent for Kruidvat drugstore
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import field
import asyncio
import random
import aiohttp
import json
import xml.etree.ElementTree as ET
import re
import logging
from bs4 import BeautifulSoup
from pathlib import Path

from langgraph.graph import StateGraph
from langgraph.graph import END
from agents.base_agent import BaseAgent, AgentState, AgentStatus

logger = logging.getLogger(__name__)

# Simple function to create a Kruidvat state with the needed fields
def create_kruidvat_state() -> AgentState:
    """Create AgentState with Kruidvat-specific fields"""
    state = AgentState()
    
    # Add Kruidvat-specific fields
    state.products_found = []
    state.failed_products = []
    state.urls_to_scrape = []
    state.total_urls = 0
    state.scraped_count = 0
    state.failed_count = 0
    state.progress = 0
    state.raw_data = ""
    state.error_message = ""
    state.current_batch = 0
    state.total_batches = 0
    
    return state

class KruidvatAgent(BaseAgent):
    """LangGraph agent for scraping Kruidvat products"""
    
    def __init__(self):
        super().__init__("kruidvat", "Kruidvat Scraper Agent")
        self.store_name = "Kruidvat"
        self.store_slug = "kruidvat" 
        self.base_url = "https://www.kruidvat.nl"
        self.api_base = "https://www.kruidvat.nl/api/v2/kvn"
        
        # Build the workflow
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for Kruidvat scraping"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("fetch_sitemap", self._fetch_sitemap)
        workflow.add_node("extract_product_ids", self._extract_product_ids) 
        workflow.add_node("scrape_products", self._scrape_products)
        workflow.add_node("save_results", self._save_results)
        workflow.add_node("handle_error", self._handle_error)
        
        # Add edges
        workflow.set_entry_point("fetch_sitemap")
        workflow.add_edge("fetch_sitemap", "extract_product_ids")
        workflow.add_edge("extract_product_ids", "scrape_products")
        workflow.add_edge("scrape_products", "save_results")
        workflow.add_edge("save_results", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def _fetch_sitemap(self, state: AgentState) -> AgentState:
        """Fetch sitemap URLs for products"""
        sitemap_url = "https://www.kruidvat.nl/sitemap.xml"
        logger.info(f"🌐 Fetching Kruidvat sitemap from: {sitemap_url}")
        
        # Ensure all required fields exist on the state
        if not hasattr(state, 'products_found'):
            state.products_found = []
        if not hasattr(state, 'failed_products'):
            state.failed_products = []
        if not hasattr(state, 'urls_to_scrape'):
            state.urls_to_scrape = []
        if not hasattr(state, 'raw_data'):
            state.raw_data = ""
        if not hasattr(state, 'error_message'):
            state.error_message = ""
        if not hasattr(state, 'total_urls'):
            state.total_urls = 0
        if not hasattr(state, 'scraped_count'):
            state.scraped_count = 0
        if not hasattr(state, 'failed_count'):
            state.failed_count = 0
        if not hasattr(state, 'progress'):
            state.progress = 0
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://www.kruidvat.nl/',
                'Origin': 'https://www.kruidvat.nl',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                sitemap_url = "https://www.kruidvat.nl/sitemap.xml"
                async with session.get(sitemap_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        state.raw_data = content
                        state.status = AgentStatus.RUNNING
                        logger.info("✅ Successfully fetched Kruidvat sitemap")
                    else:
                        state.error_message = f"Failed to fetch sitemap: HTTP {response.status}"
                        state.status = AgentStatus.FAILED
                        logger.error(state.error_message)
        
        except Exception as e:
            state.error_message = f"Error fetching sitemap: {str(e)}"
            state.status = AgentStatus.FAILED
            logger.error(state.error_message)
        
        return state
    
    async def _extract_product_ids(self, state: AgentState) -> AgentState:
        """Extract product IDs from sitemap XML"""
        logger.info("🔍 Extracting product IDs from sitemap")
        
        try:
            if not state.raw_data:
                state.error_message = "No sitemap data available"
                state.status = AgentStatus.FAILED
                return state
            
            # Parse XML sitemap
            root = ET.fromstring(state.raw_data)
            
            # Handle sitemap namespaces
            namespaces = {
                'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                '': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            product_ids = []
            for url_elem in root.findall('.//ns:url/ns:loc', namespaces):
                if url_elem is not None and '/p/' in url_elem.text:
                    # Extract product ID from URL like /p/product-name-123456
                    product_id = url_elem.text.split('/p/')[-1]
                    if product_id:
                        product_ids.append(product_id)
            
            # Remove duplicates and sort
            product_ids = list(set(product_ids))
            
            # Limit for initial testing (remove this for full scraping)
            if len(product_ids) > 50:
                product_ids = product_ids[:50]
                logger.info(f"⚠️ Limited to first 50 products for testing")
            
            state.urls_to_scrape = product_ids
            state.total_urls = len(product_ids)
            
            logger.info(f"✅ Found {len(product_ids)} product IDs to scrape")
            
        except Exception as e:
            state.error_message = f"Error extracting product IDs: {str(e)}"
            state.status = AgentStatus.FAILED
            logger.error(state.error_message)
        
        return state
    
    async def _scrape_products(self, state: AgentState) -> AgentState:
        """Scrape individual products using API"""
        logger.info(f"🔄 Starting Kruidvat product scraping for {len(state.urls_to_scrape)} products")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://www.kruidvat.nl/',
            }
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                for i, product_id in enumerate(state.urls_to_scrape):
                    try:
                        # Update progress
                        state.progress = int((i / len(state.urls_to_scrape)) * 100)
                        
                        if i % 10 == 0:
                            logger.info(f"📈 Progress: {i}/{len(state.urls_to_scrape)} products processed")
                        
                        # Fetch product data from API
                        product_data = await self._get_product_from_api(session, product_id)
                        
                        if product_data:
                            # Extract and normalize product information
                            normalized_product = self._normalize_product_data(product_data, product_id)
                            if normalized_product:
                                state.products_found.append(normalized_product)
                                logger.debug(f"✅ Successfully scraped product: {product_id}")
                            else:
                                logger.warning(f"⚠️ Failed to normalize product data: {product_id}")
                                state.failed_products.append(product_id)
                        else:
                            logger.warning(f"⚠️ Failed to fetch product data: {product_id}")
                            state.failed_products.append(product_id)
                        
                        # Rate limiting - small delay between requests
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing product {product_id}: {str(e)}")
                        state.failed_products.append(product_id)
                        continue
            
            state.scraped_count = len(state.products_found)
            state.failed_count = len(state.failed_products)
            
            logger.info(f"✅ Kruidvat scraping completed!")
            logger.info(f"📊 Successfully scraped: {state.scraped_count}")
            logger.info(f"❌ Failed: {state.failed_count}")
            
        except Exception as e:
            state.error_message = f"Error during product scraping: {str(e)}"
            state.status = AgentStatus.FAILED
            logger.error(state.error_message)
        
        return state
    
    async def _get_product_from_api(self, session: aiohttp.ClientSession, product_id: str, max_retries: int = 3) -> Optional[Dict]:
        """Fetch product data from Kruidvat API with retries"""
        
        for attempt in range(max_retries):
            try:
                url = f"{self.api_base}/products/{product_id}"
                logger.debug(f"🌐 Fetching product from API: {url} (Attempt {attempt + 1}/{max_retries})")
                
                async with session.get(url) as response:
                    if response.status == 429:  # Too Many Requests
                        wait_time = (attempt + 1) * 2
                        logger.warning(f"⚠️ Rate limited. Waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"✅ Successfully fetched product data for: {product_id}")
                        return data
                    elif response.status == 404:
                        logger.debug(f"📭 Product not found (404): {product_id}")
                        return None
                    else:
                        logger.warning(f"⚠️ API returned status {response.status} for product: {product_id}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        return None
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout for product {product_id} (Attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"❌ Error fetching product {product_id}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return None
        
        return None
    
    def _normalize_product_data(self, api_data: Dict, product_id: str) -> Optional[Dict]:
        """Normalize product data from Kruidvat API response"""
        try:
            # Extract basic information
            name = api_data.get('name', '').strip()
            if not name:
                logger.warning(f"⚠️ Product {product_id} has no name")
                return None
            
            # Extract price information
            price_data = api_data.get('price', {})
            current_price = None
            original_price = None
            
            if isinstance(price_data, dict):
                current_price = price_data.get('value')
                # Check for discount pricing
                if 'wasPrice' in price_data:
                    original_price = price_data.get('wasPrice')
            
            # Extract stock information
            stock_data = api_data.get('stock', {})
            stock_status = stock_data.get('stockLevelStatus', 'Unknown')
            stock_level = stock_data.get('stockLevel', 0)
            is_available = stock_status.lower() == 'instock'
            
            # Extract brand
            brand_data = api_data.get('masterBrand', {})
            brand = brand_data.get('name', '').strip() if brand_data else None
            
            # Extract categories
            categories = []
            category_hierarchy = api_data.get('categoriesHierarchy', [])
            for cat in api_data.get('categories', []):
                if cat.get('name'):
                    categories.append(cat['name'])
            
            # Extract images
            image_urls = []
            for img in api_data.get('images', []):
                if img.get('url'):
                    image_urls.append(img['url'])
            
            # Extract description
            description = api_data.get('description', '').strip()
            summary = api_data.get('summary', '').strip()
            
            # Use summary if description is empty
            if not description and summary:
                description = summary
            
            # Create product URL
            product_url = f"{self.base_url}{api_data.get('url', '')}" if api_data.get('url') else f"{self.base_url}/p/{product_id}"
            
            # Calculate discount if applicable
            discount_percentage = None
            is_promotion = False
            if original_price and current_price and original_price > current_price:
                discount_percentage = round(((original_price - current_price) / original_price) * 100, 2)
                is_promotion = True
            
            return {
                'id': product_id,
                'url': product_url,
                'title': name,
                'brand': brand,
                'price': {
                    'current': current_price,
                    'original': original_price,
                    'per_unit': None  # Not typically provided by Kruidvat API
                },
                'description': description,
                'ean': api_data.get('ean'),
                'promotion': None,  # Could extract from highlights if needed
                'stock': {
                    'level': stock_level,
                    'status': 'inStock' if is_available else 'outOfStock'
                },
                'image_urls': image_urls,
                'categories': categories,
                'category_hierarchy': category_hierarchy,
                'specifications': {},  # Not typically in API response
                'discount_percentage': discount_percentage,
                'is_promotion': is_promotion,
                'extraction_method': 'api',
                'extraction_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error normalizing product data for {product_id}: {str(e)}")
            return None
    
    async def _save_results(self, state: AgentState) -> AgentState:
        """Save the scraped results"""
        logger.info(f"💾 Saving {len(state.products_found)} Kruidvat products")
        
        try:
            if state.products_found:
                # Save to database using the database client
                if hasattr(self, 'db') and self.db:
                    saved_count = await self.db.save_products(state.products_found, self.store_slug)
                    logger.info(f"✅ Saved {saved_count} products to database")
                    state.saved_count = saved_count
                else:
                    logger.warning("⚠️ No database connection available")
                
                # Also save to JSON file for backup
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"kruidvat_products_{timestamp}.json"
                
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(state.products_found, f, indent=2, ensure_ascii=False)
                    logger.info(f"💾 Backup saved to: {filename}")
                except Exception as e:
                    logger.error(f"❌ Failed to save backup file: {str(e)}")
            
            state.status = AgentStatus.COMPLETED
            state.end_time = datetime.now()
            
        except Exception as e:
            state.error_message = f"Error saving results: {str(e)}"
            state.status = AgentStatus.FAILED
            logger.error(state.error_message)
        
        return state
    
    async def _handle_error(self, state: AgentState) -> AgentState:
        """Handle errors in the workflow"""
        logger.error(f"❌ Kruidvat scraping failed: {state.error_message}")
        state.status = AgentStatus.FAILED
        state.end_time = datetime.now()
        return state
    
    async def run_scraping_job(self, max_products: Optional[int] = None) -> Dict[str, Any]:
        """Run a complete scraping job"""
        logger.info(f"🚀 Starting Kruidvat scraping job")
        
        # Initialize state
        initial_state = create_kruidvat_state()
        initial_state.start_time = datetime.now()
        initial_state.status = AgentStatus.RUNNING
        
        try:
            # Run the workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Return results
            return {
                'agent': self.store_name,
                'status': final_state.status.value,
                'products_found': len(final_state.products_found),
                'products_failed': len(final_state.failed_products),
                'start_time': final_state.start_time.isoformat() if final_state.start_time else None,
                'end_time': final_state.end_time.isoformat() if final_state.end_time else None,
                'error_message': final_state.error_message,
                'sample_products': final_state.products_found[:3] if final_state.products_found else []
            }
            
        except Exception as e:
            logger.error(f"❌ Kruidvat scraping job failed: {str(e)}")
            return {
                'agent': self.store_name,
                'status': AgentStatus.FAILED.value,
                'products_found': 0,
                'products_failed': 0,
                'start_time': initial_state.start_time.isoformat() if initial_state.start_time else None,
                'end_time': datetime.now().isoformat(),
                'error_message': str(e),
                'sample_products': []
            }
    
    async def test_single_product(self, product_id: str = None) -> Dict[str, Any]:
        """Test scraping a single product"""
        if not product_id:
            # Use a sample product ID for testing
            product_id = "110002171"  # Example Kruidvat product ID
        
        logger.info(f"🧪 Testing Kruidvat single product scraping: {product_id}")
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://www.kruidvat.nl/',
            }
            
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                # Try API first
                product_data = await self._get_product_from_api(session, product_id)
                
                if product_data:
                    normalized = self._normalize_product_data(product_data, product_id)
                    if normalized:
                        logger.info(f"✅ Successfully tested product: {normalized.get('title', 'Unknown')}")
                        return {
                            'success': True,
                            'method': 'api',
                            'product': normalized
                        }
                
                logger.warning(f"⚠️ API method failed for product: {product_id}")
                return {
                    'success': False,
                    'method': 'api',
                    'error': 'Failed to fetch from API'
                }
                
        except Exception as e:
            logger.error(f"❌ Test failed for product {product_id}: {str(e)}")
            return {
                'success': False,
                'method': 'test',
                'error': str(e)
            } 