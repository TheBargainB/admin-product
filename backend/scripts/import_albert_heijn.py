#!/usr/bin/env python3
"""
Import pre-scraped Albert Heijn products from JSON into database
Usage: python scripts/import_albert_heijn.py
"""

import asyncio
import json
import sys
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database.client import get_database
from utils.logging import get_logger

logger = get_logger(__name__)

class AlbertHeijnImporter:
    """Import Albert Heijn products from JSON file to database"""
    
    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.db = None
        self.store_id = None
        self.stats = {
            "total_products": 0,
            "products_imported": 0,
            "products_updated": 0,
            "products_skipped": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None
        }
    
    async def initialize(self):
        """Initialize database connection and get Albert Heijn store ID"""
        self.db = await get_database()
        
        # Get Albert Heijn store
        store = await self.db.get_store_by_slug("albert_heijn")
        if not store:
            logger.error("❌ Albert Heijn store not found in database")
            raise Exception("Albert Heijn store not found")
        
        self.store_id = store["id"]
        logger.info(f"✅ Found Albert Heijn store: {store['name']} (ID: {self.store_id})")
    
    def parse_unit_info(self, sales_unit_size: str) -> Tuple[Optional[float], Optional[str]]:
        """Parse unit size and type from salesUnitSize like '500 g', '0,75 l'"""
        if not sales_unit_size:
            return None, None
        
        # Clean the string and handle Dutch decimal format
        clean_size = sales_unit_size.strip().replace(',', '.')
        
        # Extract number and unit
        match = re.match(r'([0-9.]+)\s*([a-zA-Z]+)', clean_size)
        if match:
            try:
                unit_size = float(match.group(1))
                unit_type = match.group(2).lower()
                return unit_size, unit_type
            except ValueError:
                pass
        
        return None, None
    
    def extract_image_url(self, image_pack: list) -> Optional[str]:
        """Extract the best image URL from imagePack"""
        if not image_pack or not isinstance(image_pack, list):
            return None
        
        # Prefer medium size image
        for img in image_pack:
            if img.get("medium", {}).get("url"):
                return img["medium"]["url"]
        
        # Fallback to small if medium not available
        for img in image_pack:
            if img.get("small", {}).get("url"):
                return img["small"]["url"]
        
        return None
    
    def calculate_discount(self, now_price: float, was_price: float) -> Optional[float]:
        """Calculate discount percentage if there's a price difference"""
        if not now_price or not was_price or now_price >= was_price:
            return None
        
        return round(((was_price - now_price) / was_price) * 100, 1)
    
    async def process_product(self, product_data: Dict[str, Any]) -> bool:
        """Process a single product and save to database"""
        try:
            # Extract basic info
            name = product_data.get("title", "").strip()
            if not name:
                logger.warning("⚠️ Skipping product without title")
                return False
            
            brand = product_data.get("brand", "").strip() or None
            category = product_data.get("category", "").strip() or None
            description = product_data.get("summary", "").strip() or None
            external_id = str(product_data.get("id", ""))
            
            # Parse unit info
            sales_unit_size = product_data.get("salesUnitSize", "")
            unit_size, unit_type = self.parse_unit_info(sales_unit_size)
            
            # Extract pricing
            price_info = product_data.get("priceV2", {})
            now_price = price_info.get("now", {}).get("amount")
            was_price = price_info.get("was", {}).get("amount")
            
            if not now_price:
                logger.warning(f"⚠️ Skipping {name} - no price information")
                return False
            
            # Check for promotions
            original_price = was_price if was_price and was_price != now_price else None
            discount_percentage = self.calculate_discount(now_price, was_price) if original_price else None
            is_promotion = bool(original_price)
            
            # Extract image URL
            image_url = self.extract_image_url(product_data.get("imagePack", []))
            
            # Create store URL
            web_path = product_data.get("webPath", "")
            store_url = f"https://www.ah.nl{web_path}" if web_path else None
            
            # Save product to database
            product_id = await self.db.save_product(
                name=name,
                brand=brand,
                category=category,
                unit_size=unit_size,
                unit_type=unit_type,
                description=description,
                image_url=image_url,
                external_id=external_id
            )
            
            if not product_id:
                logger.error(f"❌ Failed to save product: {name}")
                return False
            
            # Link product to Albert Heijn store
            await self.db.save_store_product(
                store_id=self.store_id,
                product_id=product_id,
                store_product_id=external_id,
                store_url=store_url
            )
            
            # Save current price
            await self.db.save_current_price(
                store_id=self.store_id,
                product_id=product_id,
                price=now_price,
                original_price=original_price,
                discount_percentage=discount_percentage,
                is_promotion=is_promotion,
                promotion_text=None  # Could extract from highlights if needed
            )
            
            logger.info(f"✅ Imported: {name} - €{now_price}" + 
                       (f" (was €{original_price})" if original_price else ""))
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing product {product_data.get('title', 'unknown')}: {e}")
            return False
    
    async def import_products(self, max_products: Optional[int] = None, batch_size: int = 100):
        """Import all products from JSON file"""
        self.stats["start_time"] = datetime.now()
        
        logger.info(f"🚀 Starting Albert Heijn import from {self.json_file_path}")
        
        try:
            # Load JSON data
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            self.stats["total_products"] = len(products)
            
            if max_products:
                products = products[:max_products]
                logger.info(f"📝 Limited to first {max_products} products for testing")
            
            logger.info(f"📊 Processing {len(products)} Albert Heijn products...")
            
            # Process in batches
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]
                batch_start = i + 1
                batch_end = min(i + batch_size, len(products))
                
                logger.info(f"📦 Processing batch {batch_start}-{batch_end} of {len(products)}")
                
                for product in batch:
                    success = await self.process_product(product)
                    
                    if success:
                        self.stats["products_imported"] += 1
                    else:
                        self.stats["errors"] += 1
                
                # Small delay between batches to avoid overwhelming the database
                await asyncio.sleep(0.1)
            
            self.stats["end_time"] = datetime.now()
            duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
            
            logger.info(f"🎉 Albert Heijn import completed!")
            logger.info(f"📊 Statistics:")
            logger.info(f"   ⏱️  Duration: {duration:.1f}s")
            logger.info(f"   📦 Total products: {self.stats['total_products']}")
            logger.info(f"   ✅ Imported: {self.stats['products_imported']}")
            logger.info(f"   ❌ Errors: {self.stats['errors']}")
            logger.info(f"   📈 Success rate: {(self.stats['products_imported'] / len(products)) * 100:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Import failed: {e}")
            raise

async def main():
    """Main entry point"""
    # Setup logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Path to the JSON file
    json_file = "/Users/yusephswessi/Documents/GitHub/admin-product/combined_albert_products.json"
    
    if not os.path.exists(json_file):
        logger.error(f"❌ JSON file not found: {json_file}")
        return
    
    # Create importer and run
    importer = AlbertHeijnImporter(json_file)
    
    try:
        await importer.initialize()
        
        # Import all products (remove max_products to import all 30,665)
        await importer.import_products()
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return

if __name__ == "__main__":
    asyncio.run(main()) 