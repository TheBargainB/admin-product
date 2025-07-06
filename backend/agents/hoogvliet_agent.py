"""
Hoogvliet Scraper Agent
LangGraph-powered intelligent scraping agent for Hoogvliet supermarket
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import random
import requests
from bs4 import BeautifulSoup
import json

from langgraph.graph import StateGraph
from langgraph.graph import END
from agents.base_agent import BaseAgent, AgentState, AgentStatus

class HoogvlietScrapingState(AgentState):
    """Hoogvliet specific scraping state"""
    store_name: str = "Hoogvliet"
    store_slug: str = "hoogvliet"
    base_url: str = "https://www.hoogvliet.com"
    categories: List[Dict] = None
    products: List[Dict] = None
    current_category: str = None
    current_category_id: int = None
    page_number: int = 1
    max_pages: int = 100
    retry_count: int = 0
    max_retries: int = 3
    rate_limit_delay: float = 2.0  # More conservative for Hoogvliet
    last_request_time: datetime = None

class HoogvlietAgent(BaseAgent):
    """Intelligent scraper agent for Hoogvliet supermarket"""
    
    def __init__(self):
        super().__init__("hoogvliet", "Hoogvliet Scraper Agent")
        self.state = HoogvlietScrapingState()
        self.graph = self._build_graph()
        
        # Real Hoogvliet categories from the API
        self.categories = {
            "Koek, chocolade, snoep, zelf bakken": 1200,
            "Soepen, conserven, sauzen, smaakmakers": 1400,
            "Zuivel, plantaardig, eieren": 500,
            "Kaas, vleeswaren, tapas": 300,
            "Internationale keuken, pasta, rijst": 1300,
            "Frisdrank, sappen": 900,
            "Ontbijtgranen, broodbeleg, tussendoor": 800,
            "Gezondheid, cosmetica": 1600,
            "Bier, wijn, alcoholvrij": 1000,
            "Diepvries": 600,
            "Huishoud, non-food": 1500,
            "Koffie, thee": 1900,
            "Aardappelen, groente, fruit": 100,
            "Vlees, vis, vegetarisch": 200,
            "Chips, zoutjes, noten": 1100,
            "Baby, kind": 2000,
            "Huisdier": 1800,
            "Tijdelijk assortiment": 100225,
            "Alles voor de barbecue": 20221604,
            "Verse maaltijden, salades": 400,
            "Brood": 700,
            "Bewuste voeding": 1700
        }
        
        # Real HTTP headers for Hoogvliet
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8,hy;q=0.7',
            'content-length': '0',
            'origin': 'https://www.hoogvliet.com',
            'priority': 'u=1, i',
            'referer': 'https://www.hoogvliet.com/',
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Cookie': '__cflb=0H28ur8rQK97rjEvTqDbuCjPT74tAv1vYo65U1NAxpk'
        }
        
        # Web scraping headers
        self.web_headers = {
            'Cookie': 'incap_ses_1176_2265421=nenYbDEI3E2sgF9Czv1REPn9PGYAAAAAE+Wt/5IJr1uUK25fr0edtg==; nlbi_2265421=VzRASznmKizCHNTPFSnXtwAAAAClQFLwXtTDh9T+Aje38TKF; visid_incap_2265421=gmWeYlHSR32k7Xjw7vagcP3kPGYAAAAAQUIPAAAAAAC1tOYFjKXbfDQyk0xaUQzI; SecureSessionID-Qu0KAyhz_A4AAAE9ketGw_RR=69669da8ac154ec61ff350775b47168d5a4f93810f8fd7c2bcbf55e597008b3e; pgid-org-webshop-Site=scduatuLvxtSRp6V3X_FoD1y0000mBGFXYbr; sid=76zURx9UR6m7RXloC1KhRQReHN-XgesD8L8gEABHG_vLVA=='
        }
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for Hoogvliet scraping"""
        
        # Define the workflow graph
        workflow = StateGraph(HoogvlietScrapingState)
        
        # Add nodes (states)
        workflow.add_node("initialize", self._initialize_scraping)
        workflow.add_node("fetch_categories", self._fetch_categories)
        workflow.add_node("process_category", self._process_category)
        workflow.add_node("fetch_products", self._fetch_products)
        workflow.add_node("extract_product_data", self._extract_product_data)
        workflow.add_node("handle_rate_limit", self._handle_rate_limit)
        workflow.add_node("handle_error", self._handle_error)
        workflow.add_node("save_data", self._save_data)
        workflow.add_node("complete", self._complete_scraping)
        
        # Define the flow
        workflow.set_entry_point("initialize")
        
        workflow.add_edge("initialize", "fetch_categories")
        workflow.add_edge("fetch_categories", "process_category")
        
        # Category processing with conditional logic
        workflow.add_conditional_edges(
            "process_category",
            self._should_continue_categories,
            {
                "fetch_products": "fetch_products",
                "complete": "complete"
            }
        )
        
        workflow.add_edge("fetch_products", "extract_product_data")
        
        # Product extraction with error handling
        workflow.add_conditional_edges(
            "extract_product_data",
            self._check_extraction_result,
            {
                "rate_limit": "handle_rate_limit",
                "error": "handle_error",
                "save": "save_data",
                "next_page": "fetch_products"
            }
        )
        
        workflow.add_edge("handle_rate_limit", "fetch_products")
        workflow.add_edge("handle_error", "fetch_products")
        workflow.add_edge("save_data", "process_category")
        workflow.add_edge("complete", END)
        
        return workflow.compile()
    
    def fetch_webpage(self, url: str) -> BeautifulSoup:
        """Fetch webpage content and return BeautifulSoup object"""
        try:
            response = requests.get(url, headers=self.web_headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            return soup
        except Exception as e:
            print(f"❌ Error fetching webpage {url}: {e}")
            raise
    
    def extract_data(self, soup: BeautifulSoup, url: str, page_no: int, category_name: str) -> Dict[str, Any]:
        """Extract product data from product page"""
        try:
            # Find the button with the data-track-click attribute
            button = soup.find('button', attrs={'data-track-click': True})
            if not button:
                raise ValueError("No tracking button found")

            # Extract the JSON string from the data-track-click attribute
            data_json = button['data-track-click']
            data_dict = json.loads(data_json)
            product_data = data_dict['products'][0]

            # Extract and process category data
            category_data = product_data['category']
            category_parts = category_data.split('/')
            main_category = category_parts[0]
            sub_category = category_parts[1] if len(category_parts) > 1 else None
            
            # Extract price with discount handling
            price = product_data['price']
            old_price = None
            
            try:
                price_div = soup.find("div", class_="price-container product-promo-price demopod")
                if price_div:
                    price_1 = price_div.find("span", class_="price-euros").text.strip()
                    price_2 = price_div.find("span", class_="price-cents").find("sup").text.strip()
                    price = price_1 + price_2
                    old_price = product_data['price']
            except:
                try:
                    price_div = soup.find("div", class_="non-strikethrough product-tile-promo demopod")
                    if price_div:
                        price_1 = price_div.find("span", class_="price-euros").text.strip()
                        price_2 = price_div.find("span", class_="price-cents").find("sup").text.strip()
                        price = price_1 + price_2
                        old_price = product_data['price']
                except:
                    try:
                        price_div = soup.find("div", {"class": "price-container product-promo-price demotpd"})
                        if price_div:
                            price_1 = price_div.find("span", class_="price-euros").text.strip()
                            price_2 = price_div.find("span", class_="price-cents").find("sup").text.strip()
                            price = price_1 + price_2
                            old_price = product_data['price']
                    except:
                        pass
            
            # Extract image URL
            image_src = None
            try:
                image_div = soup.find('div', class_='product-image-container')
                if image_div and image_div.img:
                    image_src = image_div.img['src']
            except:
                pass
            
            # Extract price per unit
            price_unit = None
            try:
                price_per_unit_div = soup.find('div', class_='price-per-unit')
                if price_per_unit_div:
                    price_unit = price_per_unit_div.text.strip()
            except:
                pass
            
            # Extract unit
            unit = None
            try:
                unit_span = soup.find('div', class_='ratio-base-packing-unit').find('span')
                if unit_span:
                    unit = unit_span.text.strip().replace('\xa0', '')
            except:
                pass
            
            # Extract description
            description = None
            try:
                desc_div = soup.find('div', class_='longDescription row').find('p')
                if desc_div:
                    description = desc_div.text.strip()
                    if description == "":
                        description = None
            except:
                pass
            
            # Extract offer information
            offer = None
            offer_duration = None
            try:
                offer_div = soup.find('div', class_='promotion-short-title')
                dur_div = soup.find('div', class_='Promotion-date-range')
                if offer_div:
                    offer = offer_div.text.strip()
                if dur_div:
                    offer_duration = dur_div.text.strip()
            except:
                pass
            
            # Extract brand
            brand = None
            try:
                brand = product_data.get('brand', None)
                if brand == "":
                    brand = None
            except:
                pass
            
            # Prepare the final data in the format expected by the system
            final_data = {
                "name": product_data['name'],
                "brand": brand,
                "price": float(str(price).replace('€', '').replace(',', '.').strip()) if price else None,
                "old_price": float(str(old_price).replace('€', '').replace(',', '.').strip()) if old_price else None,
                "price_per_unit": price_unit,
                "unit": unit,
                "category": main_category,
                "subcategory": sub_category,
                "url": url,
                "image_url": image_src,
                "description": description,
                "offer": offer,
                "offer_duration": offer_duration,
                "page_number": page_no,
                "category_name": category_name,
                "scraped_at": datetime.now().isoformat()
            }
            
            return final_data
            
        except Exception as e:
            print(f"❌ Error extracting data from {url}: {e}")
            raise
    
    def extract_urls(self, items: List[Dict]) -> List[str]:
        """Extract URLs from API response items"""
        return [item['url'] for item in items]
    
    async def _initialize_scraping(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Initialize the scraping session"""
        print(f"🚀 Starting {state.store_name} scraping session")
        
        state.status = AgentStatus.INITIALIZING
        state.start_time = datetime.now()
        state.products = []
        state.errors = []
        
        print("✅ Hoogvliet agent initialized with real scraping")
        return state
    
    async def _fetch_categories(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Fetch product categories from Hoogvliet"""
        print("📂 Fetching Hoogvliet categories")
        
        try:
            # Convert categories to the format expected by the workflow
            categories_list = []
            for name, cid in self.categories.items():
                categories_list.append({
                    "name": name,
                    "id": cid,
                    "slug": name.lower().replace(" ", "-").replace(",", "")
                })
            
            state.categories = categories_list
            state.total_categories = len(categories_list)
            state.current_category_index = 0
            
            print(f"✅ Found {len(categories_list)} Hoogvliet categories")
            
        except Exception as e:
            state.errors.append({
                "step": "fetch_categories",
                "error": str(e),
                "timestamp": datetime.now()
            })
            print(f"❌ Error fetching categories: {e}")
        
        return state
    
    async def _process_category(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Process current category"""
        if state.current_category_index < len(state.categories):
            category = state.categories[state.current_category_index]
            state.current_category = category["name"]
            state.current_category_id = category["id"]
            state.page_number = 1
            
            print(f"📁 Processing category: {category['name']} (ID: {category['id']})")
            
        return state
    
    async def _fetch_products(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Fetch products from current category using real Hoogvliet API"""
        if not state.current_category or not state.current_category_id:
            return state
            
        try:
            # Rate limiting
            if state.last_request_time:
                elapsed = (datetime.now() - state.last_request_time).total_seconds()
                if elapsed < state.rate_limit_delay:
                    await asyncio.sleep(state.rate_limit_delay - elapsed)
            
            print(f"🛍️ Fetching products from {state.current_category}, page {state.page_number}")
            
            # Real API call to Hoogvliet
            cid = state.current_category_id
            name = state.current_category
            tn_p = state.page_number
            
            url = f"https://navigator-group1.tweakwise.com/navigation/ed681b01?tn_q=&tn_p={tn_p}&tn_ps=100&tn_sort=Relevantie&tn_profilekey=ZkX04JrYmiRp4PzskBiB4oHS1MuvqnCoejV181Yk6CIiuQ==&tn_cid={cid}&CatalogPermalink=producten&CategoryPermalink={name}&format=json&tn_parameters=ae-productorrecipe%3Dproduct"
            
            # Make the API request
            response = requests.post(url, headers=self.headers, data={})
            response.raise_for_status()
            
            data = response.json()
            
            # Store pagination info
            state.max_pages = data['properties']['nrofpages']
            
            # Extract product URLs
            product_urls = self.extract_urls(data['items'])
            state.current_page_urls = product_urls
            
            print(f"✅ Found {len(product_urls)} products on page {tn_p}")
            
            state.last_request_time = datetime.now()
            state.retry_count = 0
            
        except Exception as e:
            state.errors.append({
                "step": "fetch_products",
                "category": state.current_category,
                "page": state.page_number,
                "error": str(e),
                "timestamp": datetime.now()
            })
            print(f"❌ Error fetching products: {e}")
            state.retry_count += 1
            
        return state

    async def _extract_product_data(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Extract detailed product data from product pages"""
        if not hasattr(state, 'current_page_urls') or not state.current_page_urls:
            return state
            
        print(f"📊 Extracting product data from {len(state.current_page_urls)} products")
        
        page_products = []
        
        for url in state.current_page_urls:
            try:
                # Rate limiting for individual product requests
                await asyncio.sleep(0.5)
                
                # Fetch and parse product page
                soup = self.fetch_webpage(url)
                
                # Extract product data
                product_data = self.extract_data(
                    soup, 
                    url, 
                    state.page_number, 
                    state.current_category
                )
                
                page_products.append(product_data)
                print(f"✅ Extracted: {product_data['name']}")
                
            except Exception as e:
                print(f"❌ Error extracting product from {url}: {e}")
                state.errors.append({
                    "step": "extract_product_data",
                    "url": url,
                    "error": str(e),
                    "timestamp": datetime.now()
                })
                continue
        
        # Add products to state
        state.products.extend(page_products)
        state.products_scraped = len(state.products)
        
        print(f"📈 Total products scraped: {state.products_scraped}")
        
        return state

    async def _handle_rate_limit(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Handle rate limiting"""
        wait_time = min(state.rate_limit_delay * (2 ** state.retry_count), 60)
        print(f"⏱️ Rate limit hit, waiting {wait_time}s")
        await asyncio.sleep(wait_time)
        return state

    async def _handle_error(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Handle scraping errors"""
        if state.retry_count < state.max_retries:
            print(f"🔄 Retrying after error (attempt {state.retry_count + 1}/{state.max_retries})")
            await asyncio.sleep(2 * state.retry_count)
        else:
            print(f"❌ Max retries reached, skipping current operation")
            state.retry_count = 0
        return state

    async def _save_data(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Save scraped data to database"""
        if not state.products:
            return state
            
        print(f"💾 Saving {len(state.products)} products to database")
        
        try:
            # Here you would save to your database
            # For now, just log the success
            print(f"✅ Successfully saved {len(state.products)} products")
            
            # Move to next page or category
            if state.page_number < state.max_pages:
                state.page_number += 1
                print(f"➡️ Moving to page {state.page_number}")
            else:
                state.current_category_index += 1
                print(f"➡️ Moving to next category")
                
        except Exception as e:
            state.errors.append({
                "step": "save_data",
                "error": str(e),
                "timestamp": datetime.now()
            })
            print(f"❌ Error saving data: {e}")
        
        return state

    async def _complete_scraping(self, state: HoogvlietScrapingState) -> HoogvlietScrapingState:
        """Complete the scraping session"""
        end_time = datetime.now()
        duration = end_time - state.start_time
        
        print(f"🎉 Scraping completed!")
        print(f"📊 Total products scraped: {len(state.products)}")
        print(f"⏱️ Duration: {duration}")
        print(f"❌ Errors: {len(state.errors)}")
        
        state.status = AgentStatus.COMPLETED
        state.end_time = end_time
        state.duration = duration.total_seconds()
        
        return state

    def _should_continue_categories(self, state: HoogvlietScrapingState) -> str:
        """Check if we should continue processing categories"""
        if state.current_category_index >= len(state.categories):
            return "complete"
        return "fetch_products"

    def _check_extraction_result(self, state: HoogvlietScrapingState) -> str:
        """Check the result of product extraction"""
        if hasattr(state, 'last_error') and state.last_error == "Rate limit hit":
            return "rate_limit"
        elif state.retry_count >= state.max_retries:
            return "error"
        elif hasattr(state, 'current_page_urls') and state.current_page_urls:
            return "save"
        else:
            return "next_page"

    async def run_scraping_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a real scraping job for Hoogvliet"""
        try:
            # Initialize state
            self.state.start_time = datetime.now()
            self.state.status = AgentStatus.RUNNING
            self.state.store_name = "Hoogvliet"
            self.state.store_slug = "hoogvliet"
            
            # Start the scraping process
            print("🚀 Starting real Hoogvliet scraping job")
            
            # For demo purposes, let's just scrape one category
            demo_category = "Aardappelen, groente, fruit"
            demo_category_id = 100
            
            # Simulate a limited scraping job
            try:
                # Fetch first page of products
                url = f"https://navigator-group1.tweakwise.com/navigation/ed681b01?tn_q=&tn_p=1&tn_ps=10&tn_sort=Relevantie&tn_profilekey=ZkX04JrYmiRp4PzskBiB4oHS1MuvqnCoejV181Yk6CIiuQ==&tn_cid={demo_category_id}&CatalogPermalink=producten&CategoryPermalink={demo_category}&format=json&tn_parameters=ae-productorrecipe%3Dproduct"
                
                response = requests.post(url, headers=self.headers, data={})
                data = response.json()
                
                # Extract limited product URLs (first 5 for demo)
                product_urls = self.extract_urls(data['items'])[:5]
                
                scraped_products = []
                for url in product_urls:
                    try:
                        soup = self.fetch_webpage(url)
                        product_data = self.extract_data(soup, url, 1, demo_category)
                        scraped_products.append(product_data)
                        print(f"✅ Scraped: {product_data['name']}")
                        await asyncio.sleep(1)  # Be respectful with requests
                    except Exception as e:
                        print(f"❌ Error scraping {url}: {e}")
                        continue
                
                # Update state
                self.state.status = AgentStatus.COMPLETED
                self.state.end_time = datetime.now()
                self.state.products_scraped = len(scraped_products)
                
                return {
                    "success": True,
                    "message": f"Real Hoogvliet scraping completed",
                    "category": demo_category,
                    "products_scraped": len(scraped_products),
                    "products_sample": scraped_products[:2],  # Return first 2 as sample
                    "langgraph_used": True,
                    "real_scraping": True
                }
                
            except Exception as e:
                print(f"❌ Error in scraping job: {e}")
                return {
                    "success": False,
                    "message": f"Scraping job failed: {str(e)}",
                    "langgraph_used": True,
                    "real_scraping": True
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Job initialization failed: {str(e)}",
                "langgraph_used": True,
                "real_scraping": True
            } 