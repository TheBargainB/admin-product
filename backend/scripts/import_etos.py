#!/usr/bin/env python3
"""
Import Etos products from JSON file to Supabase database
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

class EtosImporter:
    def __init__(self):
        self.db = None
        self.store_id = None
        self.processed = 0
        self.errors = 0
        self.batch_size = 50
        
    async def initialize(self):
        """Initialize database connection and get store ID"""
        logger.info("🔌 Initializing database connection...")
        self.db = await get_database()
        
        # Get or create Etos store
        await self.ensure_etos_store()
        
    async def ensure_etos_store(self):
        """Ensure Etos store exists in database"""
        logger.info("🏪 Checking if Etos store exists...")
        
        # Check if store exists
        stores = self.db._client.table('stores').select('*').eq('slug', 'etos').execute()
        
        if not stores.data:
            logger.info("➕ Creating Etos store...")
            result = self.db._client.table('stores').insert({
                'name': 'Etos',
                'slug': 'etos',
                'base_url': 'https://www.etos.nl',
                'logo_url': 'https://www.etos.nl/logo.png',
                'is_active': True
            }).execute()
            
            if result.data:
                self.store_id = result.data[0]['id']
                logger.info(f"✅ Created Etos store with ID: {self.store_id}")
            else:
                raise Exception("Failed to create Etos store")
        else:
            self.store_id = stores.data[0]['id']
            logger.info(f"✅ Found existing Etos store with ID: {self.store_id}")
    
    def normalize_etos_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Etos product data to match database schema"""
        try:
            # Extract price information
            price_info = product.get('price', {})
            current_price = None
            original_price = None
            
            if isinstance(price_info, dict):
                current_price = price_info.get('current')
                original_price = price_info.get('original')
            elif isinstance(price_info, (int, float)):
                current_price = float(price_info)
            
            # Extract stock information
            stock_info = product.get('stock', {})
            is_available = True
            if isinstance(stock_info, dict):
                is_available = stock_info.get('status') == 'inStock'
            
            # Clean brand name
            brand = product.get('brand', '')
            if brand and brand.startswith('Alles van '):
                brand = brand.replace('Alles van ', '')
            
            # Extract content/unit size
            content = product.get('content', '')
            unit_size = None
            unit_type = None
            
            if content:
                # Try to extract numeric value and unit
                import re
                match = re.search(r'(\d+(?:\.\d+)?)\s*(ML|ml|G|g|KG|kg|L|l|stuks?)', content)
                if match:
                    unit_size = float(match.group(1))
                    unit_type = match.group(2).lower()
                    if unit_type in ['ml', 'l']:
                        unit_type = 'liter'
                    elif unit_type in ['g', 'kg']:
                        unit_type = 'kg'
                    elif unit_type in ['stuks', 'stuk']:
                        unit_type = 'piece'
            
            # Build normalized product
            normalized = {
                'name': product.get('title', 'Unknown Product'),
                'normalized_name': product.get('title', 'Unknown Product').lower().strip(),
                'brand': brand if brand else None,
                'description': product.get('description', '')[:500],  # Limit description length
                'barcode': product.get('ean'),
                'unit_size': unit_size,
                'unit_type': unit_type,
                'image_url': product.get('image_urls', [None])[0] if product.get('image_urls') else None,
            }
            
            # Build store product data
            store_product = {
                'store_product_id': product.get('id'),
                'store_url': product.get('url'),
                'is_available': is_available,
            }
            
            # Build price data
            price_data = None
            if current_price is not None:
                price_data = {
                    'price': current_price,
                    'original_price': original_price,
                    'is_promotion': original_price is not None and original_price > current_price,
                    'promotion_text': product.get('promotion')
                }
                
                if price_data['is_promotion'] and price_data['original_price']:
                    discount = ((price_data['original_price'] - price_data['price']) / price_data['original_price']) * 100
                    price_data['discount_percentage'] = round(discount, 2)
            
            return {
                'product': normalized,
                'store_product': store_product,
                'price': price_data
            }
            
        except Exception as e:
            logger.error(f"Error normalizing product {product.get('id', 'unknown')}: {e}")
            return None
    
    async def import_product_batch(self, products: List[Dict[str, Any]]) -> int:
        """Import a batch of products"""
        success_count = 0
        
        for product in products:
            try:
                normalized = self.normalize_etos_product(product)
                if not normalized:
                    self.errors += 1
                    continue
                
                product_data = normalized['product']
                store_product_data = normalized['store_product']
                price_data = normalized['price']
                
                # Save product using database client method
                product_id = await self.db.save_product(
                    name=product_data['name'],
                    brand=product_data['brand'],
                    category=None,  # We can add category mapping later
                    unit_size=product_data['unit_size'],
                    unit_type=product_data['unit_type'],
                    description=product_data['description'],
                    image_url=product_data['image_url'],
                    external_id=store_product_data['store_product_id']
                )
                
                if not product_id:
                    logger.error(f"Failed to save product: {product_data['name']}")
                    self.errors += 1
                    continue
                
                # Link product to Etos store
                await self.db.save_store_product(
                    store_id=self.store_id,
                    product_id=product_id,
                    store_product_id=store_product_data['store_product_id'],
                    store_url=store_product_data['store_url']
                )
                
                # Save current price if available
                if price_data:
                    await self.db.save_current_price(
                        store_id=self.store_id,
                        product_id=product_id,
                        price=price_data['price'],
                        original_price=price_data.get('original_price'),
                        discount_percentage=price_data.get('discount_percentage'),
                        is_promotion=price_data.get('is_promotion', False),
                        promotion_text=price_data.get('promotion_text')
                    )
                
                success_count += 1
                self.processed += 1
                
                if self.processed % 100 == 0:
                    logger.info(f"📈 Processed {self.processed} products...")
                
            except Exception as e:
                logger.error(f"Error importing product {product.get('id', 'unknown')}: {e}")
                self.errors += 1
                continue
        
        return success_count
    
    async def import_products(self, json_file_path: str):
        """Import all products from JSON file"""
        logger.info(f"📁 Loading products from {json_file_path}")
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            total_products = len(products)
            logger.info(f"📊 Found {total_products} products to import")
            
            # Process in batches
            for i in range(0, total_products, self.batch_size):
                batch = products[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (total_products + self.batch_size - 1) // self.batch_size
                
                logger.info(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} products)")
                
                try:
                    success_count = await self.import_product_batch(batch)
                    logger.info(f"✅ Batch {batch_num} completed: {success_count}/{len(batch)} successful")
                except Exception as e:
                    logger.error(f"❌ Batch {batch_num} failed: {e}")
                    self.errors += len(batch)
                
                # Add a small delay between batches
                await asyncio.sleep(0.1)
            
            # Final statistics
            success_rate = ((self.processed) / total_products) * 100 if total_products > 0 else 0
            
            logger.info(f"")
            logger.info(f"🎉 Import completed!")
            logger.info(f"📊 Total products: {total_products}")
            logger.info(f"✅ Successfully imported: {self.processed}")
            logger.info(f"❌ Errors: {self.errors}")
            logger.info(f"📈 Success rate: {success_rate:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Failed to load JSON file: {e}")
            raise

async def main():
    """Main import function"""
    json_file = "/Users/yusephswessi/Documents/GitHub/admin-product/etos_products_final.json"
    
    if not os.path.exists(json_file):
        logger.error(f"❌ JSON file not found: {json_file}")
        sys.exit(1)
    
    importer = EtosImporter()
    
    try:
        await importer.initialize()
        await importer.import_products(json_file)
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 