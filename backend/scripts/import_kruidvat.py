#!/usr/bin/env python3

"""
Import Kruidvat products from JSON file to Supabase database
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.client import get_database
from config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KruidvatImporter:
    def __init__(self):
        self.db = None
        self.store_id = None
        self.processed = 0
        self.errors = 0
        self.batch_size = 50
        
    async def initialize(self):
        """Initialize database connection and get store ID"""
        try:
            self.db = await get_database()
            logger.info("✅ Database connection established")
            
            # Get Kruidvat store
            stores = self.db._client.table('stores').select('*').eq('slug', 'kruidvat').execute()
            
            if not stores.data:
                logger.info("➕ Creating Kruidvat store...")
                result = self.db._client.table('stores').insert({
                    'name': 'Kruidvat',
                    'slug': 'kruidvat',
                    'base_url': 'https://www.kruidvat.nl',
                    'logo_url': 'https://www.kruidvat.nl/logo.png',
                    'is_active': True
                }).execute()
                
                if result.data:
                    self.store_id = result.data[0]['id']
                    logger.info(f"✅ Created Kruidvat store with ID: {self.store_id}")
                else:
                    raise Exception("Failed to create Kruidvat store")
            else:
                self.store_id = stores.data[0]['id']
                logger.info(f"✅ Found existing Kruidvat store with ID: {self.store_id}")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {str(e)}")
            raise
    
    def parse_kruidvat_product(self, raw_product: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Kruidvat product data into normalized format"""
        try:
            # Basic product information
            name = raw_product.get('name', raw_product.get('title', '')).strip()
            if not name:
                return None
            
            brand = raw_product.get('brand', raw_product.get('masterBrand', {}).get('name', '')).strip()
            
            # Price information
            price_info = raw_product.get('price', {})
            if isinstance(price_info, dict):
                current_price = price_info.get('current', price_info.get('value'))
                original_price = price_info.get('original', price_info.get('wasPrice'))
            else:
                current_price = price_info
                original_price = None
            
            # Description
            description = raw_product.get('description', raw_product.get('summary', '')).strip()
            
            # EAN/Barcode
            ean = raw_product.get('ean', raw_product.get('code', ''))
            
            # Stock information
            stock_info = raw_product.get('stock', {})
            if isinstance(stock_info, dict):
                stock_status = stock_info.get('status', 'Unknown')
                stock_level = stock_info.get('level', 0)
            else:
                stock_status = 'Unknown'
                stock_level = 0
            
            # Categories
            categories = []
            if 'categories' in raw_product:
                if isinstance(raw_product['categories'], list):
                    for cat in raw_product['categories']:
                        if isinstance(cat, dict):
                            cat_name = cat.get('name', '')
                        else:
                            cat_name = str(cat)
                        if cat_name:
                            categories.append(cat_name)
                elif isinstance(raw_product['categories'], str):
                    categories = [cat.strip() for cat in raw_product['categories'].split(';') if cat.strip()]
            
            # Images
            image_urls = []
            if 'images' in raw_product:
                if isinstance(raw_product['images'], list):
                    for img in raw_product['images']:
                        if isinstance(img, dict):
                            url = img.get('url', '')
                        else:
                            url = str(img)
                        if url:
                            image_urls.append(url)
                elif isinstance(raw_product['images'], str):
                    image_urls = [url.strip() for url in raw_product['images'].split(';') if url.strip()]
            
            # Product URL
            product_url = raw_product.get('url', '')
            if product_url and not product_url.startswith('http'):
                product_url = f"https://www.kruidvat.nl{product_url}"
            
            # Promotion information
            promotion_text = raw_product.get('promotion', '')
            is_promotion = bool(promotion_text or (original_price and current_price and original_price > current_price))
            
            # Calculate discount percentage
            discount_percentage = None
            if original_price and current_price and original_price > current_price:
                discount_percentage = round(((original_price - current_price) / original_price) * 100, 2)
            
            return {
                'name': name,
                'brand': brand,
                'description': description,
                'current_price': current_price,
                'original_price': original_price,
                'ean': ean,
                'categories': categories,
                'image_urls': image_urls,
                'product_url': product_url,
                'stock_status': stock_status,
                'stock_level': stock_level,
                'promotion_text': promotion_text,
                'is_promotion': is_promotion,
                'discount_percentage': discount_percentage,
                'extraction_timestamp': raw_product.get('extraction_timestamp', datetime.now().isoformat())
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing product {raw_product.get('id', 'unknown')}: {str(e)}")
            return None
    
    async def import_products_from_json(self, json_file_path: str):
        """Import products from JSON file"""
        try:
            logger.info(f"📂 Loading products from: {json_file_path}")
            
            with open(json_file_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            logger.info(f"📊 Found {len(products)} products to import")
            
            # Process products in batches
            for i in range(0, len(products), self.batch_size):
                batch = products[i:i + self.batch_size]
                logger.info(f"🔄 Processing batch {i//self.batch_size + 1}: products {i+1}-{min(i+self.batch_size, len(products))}")
                
                for product_data in batch:
                    try:
                        # Parse the product
                        normalized_product = self.parse_kruidvat_product(product_data)
                        if not normalized_product:
                            logger.warning(f"⚠️ Skipped product due to parsing error")
                            self.errors += 1
                            continue
                        
                        # Save to database using the database client methods
                        product_id = await self.db.save_product(
                            name=normalized_product['name'],
                            brand=normalized_product['brand'],
                            description=normalized_product['description'],
                            image_url=normalized_product['image_urls'][0] if normalized_product['image_urls'] else None,
                            external_id=product_data.get('id', '')
                        )
                        
                        if product_id:
                            # Link to store
                            store_product_saved = await self.db.save_store_product(
                                store_id=self.store_id,
                                product_id=product_id,
                                store_product_id=product_data.get('id', ''),
                                store_url=normalized_product['product_url']
                            )
                            
                            if store_product_saved and normalized_product['current_price']:
                                # Save current price
                                await self.db.save_current_price(
                                    store_id=self.store_id,
                                    product_id=product_id,
                                    price=normalized_product['current_price'],
                                    original_price=normalized_product['original_price'],
                                    discount_percentage=normalized_product['discount_percentage'],
                                    is_promotion=normalized_product['is_promotion'],
                                    promotion_text=normalized_product['promotion_text']
                                )
                                
                                self.processed += 1
                                
                                if self.processed % 100 == 0:
                                    logger.info(f"✅ Processed {self.processed} products so far...")
                            else:
                                logger.error(f"❌ Failed to create store_product for: {normalized_product['name']}")
                                self.errors += 1
                        else:
                            logger.error(f"❌ Failed to create product: {normalized_product['name']}")
                            self.errors += 1
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing product: {str(e)}")
                        self.errors += 1
                        continue
            
            logger.info(f"🎉 Import completed!")
            logger.info(f"✅ Successfully imported: {self.processed} products")
            logger.info(f"❌ Errors: {self.errors}")
            logger.info(f"📊 Success rate: {self.processed/(self.processed + self.errors)*100:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Failed to import products: {str(e)}")
            raise

async def main():
    """Main import function"""
    try:
        # Check if JSON file exists
        json_file = "/Users/yusephswessi/Documents/GitHub/admin-product/kruidvat_products_final.json"
        
        if not os.path.exists(json_file):
            logger.error(f"❌ JSON file not found: {json_file}")
            logger.info("📝 Please run the Kruidvat scraper first to generate the JSON file")
            return
        
        # Initialize importer
        importer = KruidvatImporter()
        await importer.initialize()
        
        # Start import
        logger.info("🚀 Starting Kruidvat product import...")
        start_time = datetime.now()
        
        await importer.import_products_from_json(json_file)
        
        end_time = datetime.now()
        elapsed = end_time - start_time
        
        logger.info(f"⏱️ Import completed in {elapsed}")
        
    except Exception as e:
        logger.error(f"❌ Import failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 