#!/usr/bin/env python3
"""
Import pre-scraped Jumbo products from JSON into database
Usage: python scripts/import_jumbo.py
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

class JumboImporter:
    """Import Jumbo products from JSON file to database"""
    
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
        """Initialize database connection and get Jumbo store ID"""
        self.db = await get_database()
        
        # Get Jumbo store
        store = await self.db.get_store_by_slug("jumbo")
        if not store:
            logger.error("❌ Jumbo store not found in database")
            raise Exception("Jumbo store not found")
        
        self.store_id = store["id"]
        logger.info(f"✅ Found Jumbo store: {store['name']} (ID: {self.store_id})")
    
    def parse_unit_info(self, subtitle: str) -> Tuple[Optional[float], Optional[str]]:
        """Parse unit size and type from subtitle like '840 g', '1,5 l', '12 stuks'"""
        if not subtitle:
            return None, None
        
        # Clean the string and handle Dutch decimal format
        clean_subtitle = subtitle.strip().lower().replace(',', '.')
        
        # Extract number and unit
        # Patterns: "840 g", "1.5 l", "12 stuks", "500 ml"
        match = re.match(r'([0-9.]+)\s*([a-zA-Z]+)', clean_subtitle)
        if match:
            try:
                unit_size = float(match.group(1))
                unit_type = match.group(2).lower()
                # Normalize unit types
                if unit_type in ['stuks', 'stuk']:
                    unit_type = 'pieces'
                elif unit_type in ['ml']:
                    unit_type = 'ml'
                elif unit_type in ['l', 'liter']:
                    unit_type = 'l'
                elif unit_type in ['g', 'gram']:
                    unit_type = 'g'
                elif unit_type in ['kg', 'kilo']:
                    unit_type = 'kg'
                
                return unit_size, unit_type
            except ValueError:
                pass
        
        return None, None
    
    def calculate_discount(self, price: float, promo_price: float) -> Optional[float]:
        """Calculate discount percentage if there's a promotion"""
        if not promo_price or promo_price >= price:
            return None
        
        return round(((price - promo_price) / price) * 100, 1)
    
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
            external_id = str(product_data.get("id", ""))
            
            # Parse unit info from subtitle
            subtitle = product_data.get("subtitle", "")
            unit_size, unit_type = self.parse_unit_info(subtitle)
            
            # Extract pricing (convert from cents to euros)
            prices = product_data.get("prices", {})
            price_cents = prices.get("price")
            promo_price_cents = prices.get("promoPrice")
            
            if not price_cents:
                logger.warning(f"⚠️ Skipping {name} - no price information")
                return False
            
            current_price = price_cents / 100.0  # Convert cents to euros
            original_price = None
            discount_percentage = None
            is_promotion = False
            
            if promo_price_cents and promo_price_cents < price_cents:
                # Promotion: promoPrice is the discounted price
                original_price = current_price
                current_price = promo_price_cents / 100.0
                discount_percentage = self.calculate_discount(original_price, current_price)
                is_promotion = True
            
            # Extract image URL
            image_url = product_data.get("image", "").strip() or None
            
            # Create store URL
            link = product_data.get("link", "")
            store_url = f"https://www.jumbo.com{link}" if link else None
            
            # Check availability
            availability = product_data.get("availability", {})
            is_available = availability.get("isAvailable", True)
            
            # Save product to database
            product_id = await self.db.save_product(
                name=name,
                brand=brand,
                category=category,
                unit_size=unit_size,
                unit_type=unit_type,
                description=None,  # No description in Jumbo data
                image_url=image_url,
                external_id=external_id
            )
            
            if not product_id:
                logger.error(f"❌ Failed to save product: {name}")
                return False
            
            # Link product to Jumbo store
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
                price=current_price,
                original_price=original_price,
                discount_percentage=discount_percentage,
                is_promotion=is_promotion,
                promotion_text=None  # Could extract from availability label if needed
            )
            
            price_text = f"€{current_price:.2f}"
            if original_price:
                price_text += f" (was €{original_price:.2f})"
            
            logger.info(f"✅ Imported: {name} - {price_text}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing product {product_data.get('title', 'unknown')}: {e}")
            return False
    
    async def import_products(self, max_products: Optional[int] = None, batch_size: int = 100):
        """Import all products from JSON file"""
        self.stats["start_time"] = datetime.now()
        
        logger.info(f"🚀 Starting Jumbo import from {self.json_file_path}")
        
        try:
            # Load JSON data
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            self.stats["total_products"] = len(products)
            
            if max_products:
                products = products[:max_products]
                logger.info(f"📝 Limited to first {max_products} products for testing")
            
            logger.info(f"📊 Processing {len(products)} Jumbo products...")
            
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
            
            logger.info(f"🎉 Jumbo import completed!")
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
    json_file = "/Users/yusephswessi/Documents/GitHub/admin-product/jumbo_products.json"
    
    if not os.path.exists(json_file):
        logger.error(f"❌ JSON file not found: {json_file}")
        return
    
    # Create importer and run
    importer = JumboImporter(json_file)
    
    try:
        await importer.initialize()
        
        # Import all products (remove max_products to import all 34,812)
        await importer.import_products()
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return

if __name__ == "__main__":
    asyncio.run(main()) 