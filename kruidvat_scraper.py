import asyncio
import json
import aiohttp
import logging
import xml.etree.ElementTree as ET
import csv
from datetime import datetime
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, LLMExtractionStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Product(BaseModel):
    """
    Data model for product information
    """
    name: str = Field(..., description="Name of the product")
    price: float = Field(..., description="Price of the product in EUR")
    description: str = Field(..., description="Product description")
    categories: List[str] = Field(..., description="List of categories the product belongs to")
    stock: int = Field(..., description="Current stock level")
    url: str = Field(..., description="Product URL")

class KruidvatCrawler:
    """
    Crawler for Kruidvat website to extract product data
    """
    def __init__(self):
        self.base_url = "https://www.kruidvat.nl"
        self.api_base = "https://www.kruidvat.nl/api/v2/kvn"
        self.headers = {
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
        self.timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout

    def extract_product_ids_from_xml(self, xml_file: str) -> List[str]:
        """
        Extract product IDs from XML file
        
        Args:
            xml_file: Path to the XML file containing product URLs
            
        Returns:
            List of product IDs
        """
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Handle both sitemap and urlset namespaces
            namespaces = {
                'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                '': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            product_ids = []
            for url in root.findall('.//ns:url', namespaces):
                loc = url.find('ns:loc', namespaces)
                if loc is not None and '/p/' in loc.text:
                    product_id = loc.text.split('/p/')[-1]
                    product_ids.append(product_id)
            
            logger.info(f"Found {len(product_ids)} product IDs in XML file")
            return product_ids
        except Exception as e:
            logger.error(f"Error parsing XML file: {str(e)}")
            return []

    async def get_product_data(self, product_id: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Fetch product data from Kruidvat API with retries
        
        Args:
            product_id: Product ID to fetch
            max_retries: Maximum number of retry attempts
            
        Returns:
            Product data dictionary or None if failed
        """
        for attempt in range(max_retries):
            try:
                url = f"{self.api_base}/products/{product_id}"
                logger.info(f"Fetching product data from API: {url} (Attempt {attempt + 1}/{max_retries})")
                
                async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                    async with session.get(url) as response:
                        logger.info(f"API response status: {response.status}")
                        
                        if response.status == 429:  # Too Many Requests
                            wait_time = (attempt + 1) * 2  # Exponential backoff
                            logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        if response.status != 200:
                            logger.error(f"Failed to fetch product data. Status: {response.status}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(1)  # Wait before retry
                                continue
                            return None
                            
                        data = await response.json()
                        logger.info(f"Successfully fetched product data for ID: {product_id}")
                        return data
                        
            except asyncio.TimeoutError:
                logger.error(f"Timeout while fetching product data (Attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"Error fetching product data: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return None
                
        return None

    async def extract_with_css(self, url: str) -> List[Dict]:
        """Extract data using CSS selectors"""
        try:
            schema = {
                "name": "Kruidvat Products",
                "baseSelector": "div.product-item",
                "fields": [
                    {"name": "name", "selector": "h2.product-title", "type": "text"},
                    {"name": "price", "selector": "span.price", "type": "text"},
                    {"name": "url", "selector": "a.product-link", "type": "attribute", "attribute": "href"},
                    {"name": "description", "selector": "div.product-description", "type": "text"},
                    {"name": "stock", "selector": "span.stock-status", "type": "text"}
                ]
            }

            browser_config = BrowserConfig(
                headless=True,
                java_script_enabled=True,
                user_agent=self.headers['User-Agent'],
                stealth_mode=True  # Enable stealth mode
            )

            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=JsonCssExtractionStrategy(schema),
                chunk_size=1000,  # Process content in chunks
                max_retries=3
            )

            logger.info(f"Attempting CSS extraction from: {url}")
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if result.success:
                    data = json.loads(result.extracted_content)
                    logger.info(f"Successfully extracted CSS data. Found {len(data)} items")
                    return data
                else:
                    logger.error(f"CSS extraction failed: {result.error_message}")
            return []
        except Exception as e:
            logger.error(f"Error in CSS extraction: {str(e)}")
            return []

    async def extract_with_llm(self, url: str) -> List[Dict]:
        """Extract data using LLM"""
        try:
            browser_config = BrowserConfig(
                headless=True,
                java_script_enabled=True,
                user_agent=self.headers['User-Agent'],
                stealth_mode=True  # Enable stealth mode
            )

            md_generator = DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(threshold=0.4, threshold_type="fixed"),
                chunk_size=1000  # Process content in chunks
            )

            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                markdown_generator=md_generator,
                extraction_strategy=LLMExtractionStrategy(
                    llm_config=LLMConfig(provider="ollama/llama2", api_token=None),
                    schema=Product.model_json_schema(),
                    extraction_type="schema",
                    instruction="""Extract product information from the page content. 
                    Focus on the main product details including name, price, description, categories, and stock level.
                    Also extract any additional product features, benefits, and specifications.""",
                    extra_args={
                        "temperature": 0,
                        "top_p": 0.9,
                        "max_tokens": 2000,
                        "chunk_size": 1000
                    }
                ),
                chunk_size=1000,  # Process content in chunks
                max_retries=3
            )

            logger.info(f"Attempting LLM extraction from: {url}")
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if result.success:
                    try:
                        data = json.loads(result.extracted_content)
                        logger.info(f"Successfully extracted LLM data. Found {len(data)} items")
                        return data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse LLM extraction results: {str(e)}")
                else:
                    logger.error(f"LLM extraction failed: {result.error_message}")
            return []
        except Exception as e:
            logger.error(f"Error in LLM extraction: {str(e)}")
            return []

    def save_products_to_json(self, products: List[Dict], filename: str):
        """
        Save products data to JSON file
        
        Args:
            products: List of product dictionaries
            filename: Output JSON filename
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2, ensure_ascii=False)
            logger.info(f"Successfully saved products data to {filename}")
        except Exception as e:
            logger.error(f"Error saving products data: {str(e)}")

    def save_products_to_csv(self, products: List[Dict], filename: str):
        """
        Save products data to CSV file
        
        Args:
            products: List of product dictionaries
            filename: Output CSV filename
        """
        try:
            # Define CSV headers
            headers = [
                'id', 'code', 'name', 'baseProductName', 'description', 'summary',
                'price_value', 'price_currency', 'stock_level', 'stock_status',
                'categories', 'categories_hierarchy', 'images', 'brand_code',
                'brand_name', 'brand_category', 'url', 'modified_time', 'crawled_at'
            ]
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                for product in products:
                    # Handle potential missing fields with safe dictionary access
                    price = product.get('price', {})
                    stock = product.get('stock', {})
                    master_brand = product.get('masterBrand', {})
                    
                    # Prepare row data
                    row = {
                        'id': product.get('id', ''),
                        'code': product.get('code', ''),
                        'name': product.get('name', ''),
                        'baseProductName': product.get('baseProductName', ''),
                        'description': product.get('description', ''),
                        'summary': product.get('summary', ''),
                        'price_value': price.get('value', ''),
                        'price_currency': price.get('currency', 'EUR'),
                        'stock_level': stock.get('level', ''),
                        'stock_status': stock.get('status', ''),
                        'categories': '; '.join(f"{cat.get('code', '')}: {cat.get('name', '')}" 
                                              for cat in product.get('categories', [])),
                        'categories_hierarchy': '; '.join(product.get('categoriesHierarchy', [])),
                        'images': '; '.join(f"{img.get('url', '')} ({img.get('altText', '')})" 
                                          for img in product.get('images', [])),
                        'brand_code': master_brand.get('code', ''),
                        'brand_name': master_brand.get('name', ''),
                        'brand_category': master_brand.get('category', ''),
                        'url': product.get('url', ''),
                        'modified_time': product.get('modifiedTime', ''),
                        'crawled_at': product.get('crawled_at', '')
                    }
                    writer.writerow(row)
                    
            logger.info(f"Successfully saved products data to {filename}")
        except Exception as e:
            logger.error(f"Error saving products data to CSV: {str(e)}")

    async def crawl_products(self, xml_file: str, batch_size: int = 100):
        """
        Main crawling function with batch processing
        
        Args:
            xml_file: Path to XML file with product URLs
            batch_size: Number of products to process in each batch
            
        Returns:
            List of product dictionaries
        """
        logger.info("=== Starting Kruidvat Product Crawl ===")
        
        # Extract product IDs from XML
        product_ids = self.extract_product_ids_from_xml(xml_file)
        if not product_ids:
            logger.error("No product IDs found in XML file")
            return []
        
        total_products = len(product_ids)
        logger.info(f"Found {total_products} products to process")
        
        # Process products in batches
        products = []
        for i in tqdm(range(0, total_products, batch_size), desc="Processing products"):
            batch_ids = product_ids[i:i + batch_size]
            batch_products = []
            
            for product_id in batch_ids:
                try:
                    # Get API data
                    api_data = await self.get_product_data(product_id)
                    if not api_data:
                        logger.error(f"Could not fetch API data for product {product_id}")
                        continue
                    
                    # Extract relevant data from API response
                    product = {
                        'id': product_id,
                        'code': api_data.get('code'),
                        'name': api_data.get('name'),
                        'baseProductName': api_data.get('baseProductName'),
                        'description': api_data.get('description'),
                        'summary': api_data.get('summary'),
                        'price': {
                            'value': api_data.get('price', {}).get('value'),
                            'currency': 'EUR'
                        },
                        'stock': {
                            'level': api_data.get('stock', {}).get('stockLevel'),
                            'status': api_data.get('stock', {}).get('stockLevelStatus')
                        },
                        'categories': [
                            {
                                'code': cat.get('code'),
                                'name': cat.get('name')
                            } for cat in api_data.get('categories', [])
                        ],
                        'categoriesHierarchy': api_data.get('categoriesHierarchy', []),
                        'images': [
                            {
                                'url': img.get('url'),
                                'altText': img.get('altText'),
                                'format': img.get('format'),
                                'imageType': img.get('imageType')
                            } for img in api_data.get('images', [])
                        ],
                        'masterBrand': {
                            'code': api_data.get('masterBrand', {}).get('code'),
                            'name': api_data.get('masterBrand', {}).get('name'),
                            'category': api_data.get('masterBrand', {}).get('category', {})
                        },
                        'url': f"{self.base_url}{api_data.get('url', '')}",
                        'modifiedTime': api_data.get('modifiedTime'),
                        'crawled_at': datetime.now().isoformat()
                    }
                    
                    batch_products.append(product)
                    logger.debug(f"Successfully processed product: {product_id}")
                    
                    # Add a small delay between requests to avoid rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error processing product {product_id}: {str(e)}")
                    continue
            
            products.extend(batch_products)
            
            # Save progress after each batch
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_filename = f'data/kruidvat_products_{timestamp}.json'
            csv_filename = f'data/kruidvat_products_{timestamp}.csv'
            self.save_products_to_json(products, json_filename)
            self.save_products_to_csv(products, csv_filename)
            
            logger.info(f"Processed {len(products)}/{total_products} products")
        
        return products

async def main():
    """
    Main function to run the crawler
    """
    try:
        # Run the full crawl
        crawler = KruidvatCrawler()
        products = await crawler.crawl_products('product.xml')
        
        if not products:
            logger.error("No products were processed")
            return
        
        # Print summary
        logger.info(f"\nCrawl completed successfully!")
        logger.info(f"Total products processed: {len(products)}")
        logger.info(f"Data saved to JSON and CSV files in the data/ directory")
        
    except Exception as e:
        logger.error(f"Main execution error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main()) 