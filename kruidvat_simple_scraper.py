#!/usr/bin/env python3

"""
Simple Kruidvat Scraper
Extracts product data from Kruidvat using aiohttp and BeautifulSoup (no crawl4ai)
"""

import asyncio
import json
import aiohttp
import logging
import xml.etree.ElementTree as ET
import re
import random
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KruidvatSimpleScraper:
    """Simple Kruidvat scraper using aiohttp and BeautifulSoup"""
    
    def __init__(self):
        self.base_url = "https://www.kruidvat.nl"
        self.api_base = "https://www.kruidvat.nl/api/v2/kvn"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Cache-Control': 'max-age=0'
        }
        self.session = None
        self.delay_range = (1, 3)
        
    async def create_session(self):
        """Create aiohttp session with proper configuration"""
        connector = aiohttp.TCPConnector(
            limit=5,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )
        logger.info("Created Kruidvat scraping session")

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            logger.info("Closed Kruidvat scraping session")

    def extract_product_urls_from_xml(self, xml_file: str) -> List[str]:
        """Extract product URLs from XML sitemap"""
        try:
            logger.info(f"Parsing XML file: {xml_file}")
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Handle sitemap namespaces
            namespaces = {
                'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                '': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            product_urls = []
            for url_elem in root.findall('.//ns:url/ns:loc', namespaces):
                if url_elem is not None and '/p/' in url_elem.text:
                    product_urls.append(url_elem.text)
            
            logger.info(f"Found {len(product_urls)} product URLs in XML file")
            return product_urls
        except Exception as e:
            logger.error(f"Error parsing XML file: {str(e)}")
            return []

    def extract_product_id_from_url(self, url: str) -> str:
        """Extract product ID from URL"""
        try:
            # Example URL: https://www.kruidvat.nl/p/110002171
            if '/p/' in url:
                product_id = url.split('/p/')[-1].split('?')[0]
                return product_id
            
            logger.warning(f"Could not extract product ID from URL: {url}")
            return ""
        except Exception as e:
            logger.error(f"Error extracting product ID from URL {url}: {str(e)}")
            return ""

    async def get_product_via_api(self, product_id: str, max_retries: int = 3) -> Optional[Dict]:
        """Fetch product data from Kruidvat API with retries"""
        for attempt in range(max_retries):
            try:
                url = f"{self.api_base}/products/{product_id}"
                logger.info(f"Fetching from API: {url} (Attempt {attempt + 1}/{max_retries})")
                
                async with self.session.get(url) as response:
                    if response.status == 429:  # Too Many Requests
                        wait_time = (attempt + 1) * 2
                        logger.warning(f"⏰ Rate limited. Waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"✅ API success for product: {product_id}")
                        return data
                    else:
                        logger.debug(f"API failed with status {response.status} for product: {product_id}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout for product {product_id} (Attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"API error for product {product_id}: {str(e)}")
                
        return None

    async def scrape_product_page(self, url: str, product_id: str) -> Optional[Dict]:
        """Scrape product data from the product page using BeautifulSoup"""
        try:
            logger.debug(f"Scraping page: {url}")
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.debug(f"Failed to fetch page {url}: {response.status}")
                    return None
                    
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract product data using CSS selectors
                product_data = {
                    'id': product_id,
                    'url': url,
                    'extraction_timestamp': datetime.now().isoformat(),
                    'method': 'page_scraping'
                }
                
                # Product name
                name_elem = soup.select_one('h1[data-testid="product-name"]') or soup.select_one('.product-title')
                if name_elem:
                    product_data['name'] = name_elem.get_text(strip=True)
                
                # Price information
                price_elem = soup.select_one('[data-testid="price-current"]') or soup.select_one('.price-current')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', '.'))
                    if price_match:
                        product_data['price'] = float(price_match.group())
                
                # Original price (if on sale)
                original_price_elem = soup.select_one('[data-testid="price-original"]') or soup.select_one('.price-original')
                if original_price_elem:
                    original_price_text = original_price_elem.get_text(strip=True)
                    price_match = re.search(r'[\d,]+\.?\d*', original_price_text.replace(',', '.'))
                    if price_match:
                        product_data['original_price'] = float(price_match.group())
                
                # Brand
                brand_elem = soup.select_one('[data-testid="product-brand"]') or soup.select_one('.product-brand')
                if brand_elem:
                    product_data['brand'] = brand_elem.get_text(strip=True)
                
                # Description
                desc_elem = soup.select_one('[data-testid="product-description"]') or soup.select_one('.product-description')
                if desc_elem:
                    product_data['description'] = desc_elem.get_text(strip=True)
                
                # EAN/Barcode
                ean_elem = soup.select_one('[data-testid="product-ean"]')
                if ean_elem:
                    product_data['ean'] = ean_elem.get_text(strip=True)
                
                # Stock status
                stock_elem = soup.select_one('[data-testid="stock-status"]') or soup.select_one('.stock-status')
                if stock_elem:
                    product_data['stock_status'] = stock_elem.get_text(strip=True)
                
                # Images
                img_elems = soup.select('[data-testid="product-image"] img') or soup.select('.product-image img')
                if img_elems:
                    product_data['images'] = [img.get('src') for img in img_elems if img.get('src')]
                
                # Categories
                category_elems = soup.select('[data-testid="breadcrumb"] a') or soup.select('.breadcrumb a')
                if category_elems:
                    product_data['categories'] = [cat.get_text(strip=True) for cat in category_elems]
                
                # Promotion text
                promo_elem = soup.select_one('[data-testid="promotion-text"]') or soup.select_one('.promotion')
                if promo_elem:
                    product_data['promotion'] = promo_elem.get_text(strip=True)
                
                if 'name' in product_data:
                    logger.debug(f"✅ Scraped product: {product_data['name']}")
                    return product_data
                else:
                    logger.debug(f"❌ No product name found for {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error scraping product page {url}: {str(e)}")
            return None

    async def extract_product_data(self, url: str) -> Optional[Dict]:
        """Extract product data using multiple methods"""
        try:
            product_id = self.extract_product_id_from_url(url)
            if not product_id:
                return None
            
            # Add delay to avoid rate limiting
            await asyncio.sleep(random.uniform(*self.delay_range))
            
            # Try API first
            api_data = await self.get_product_via_api(product_id)
            if api_data:
                api_data['method'] = 'api'
                api_data['extraction_timestamp'] = datetime.now().isoformat()
                return api_data
            
            # Fallback to page scraping
            page_data = await self.scrape_product_page(url, product_id)
            if page_data:
                return page_data
            
            logger.warning(f"Failed to extract data for product: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting product data from {url}: {str(e)}")
            return None

    async def scrape_products(self, xml_file: str, output_file: str, max_products: Optional[int] = None):
        """Main scraping function"""
        try:
            # Extract product URLs from XML
            product_urls = self.extract_product_urls_from_xml(xml_file)
            
            if not product_urls:
                logger.error("No product URLs found in XML file")
                return
            
            if max_products:
                product_urls = product_urls[:max_products]
                logger.info(f"Limited to {max_products} products for testing")
            
            logger.info(f"Starting to scrape {len(product_urls)} products")
            
            # Create session
            await self.create_session()
            
            scraped_products = []
            failed_count = 0
            
            # Process products
            for i, url in enumerate(product_urls, 1):
                try:
                    logger.info(f"Processing product {i}/{len(product_urls)}: {url}")
                    
                    product_data = await self.extract_product_data(url)
                    
                    if product_data:
                        scraped_products.append(product_data)
                        logger.info(f"✅ Successfully scraped: {product_data.get('name', 'Unknown')}")
                    else:
                        failed_count += 1
                        logger.warning(f"❌ Failed to scrape: {url}")
                    
                    # Save progress every 100 products
                    if i % 100 == 0:
                        self.save_products_to_json(scraped_products, f"{output_file}.progress")
                        logger.info(f"Progress saved: {len(scraped_products)} products scraped, {failed_count} failed")
                        
                except Exception as e:
                    logger.error(f"Error processing product {url}: {str(e)}")
                    failed_count += 1
                    continue
            
            # Save final results
            self.save_products_to_json(scraped_products, output_file)
            
            logger.info(f"🎉 Scraping completed!")
            logger.info(f"✅ Successfully scraped: {len(scraped_products)} products")
            logger.info(f"❌ Failed: {failed_count}")
            logger.info(f"📊 Success rate: {len(scraped_products)/(len(scraped_products) + failed_count)*100:.1f}%")
            logger.info(f"💾 Results saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Error in main scraping function: {str(e)}")
            raise
        finally:
            await self.close_session()

    def save_products_to_json(self, products: List[Dict], filename: str):
        """Save products to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved {len(products)} products to {filename}")
        except Exception as e:
            logger.error(f"Error saving products to JSON: {str(e)}")

async def main():
    """Main function"""
    try:
        # Configuration
        xml_file = "product.xml"
        output_file = "kruidvat_products_final.json"
        max_products = 50  # Set to None for all products, or limit for testing
        
        # Check if XML file exists
        if not Path(xml_file).exists():
            logger.error(f"XML file not found: {xml_file}")
            return
        
        # Create scraper and run
        scraper = KruidvatSimpleScraper()
        await scraper.scrape_products(xml_file, output_file, max_products)
        
        logger.info("✅ Kruidvat scraping completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Scraping failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 