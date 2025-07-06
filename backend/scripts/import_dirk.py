#!/usr/bin/env python3
"""
Import pre-scraped Dirk products from JSON into database
Usage: python scripts/import_dirk.py
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

class DirkImporter:
    """Import Dirk products from JSON file to database"""
    
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
        """Initialize database connection and get Dirk store ID"""
        self.db = await get_database()
        
        # Get Dirk store
        store = await self.db.get_store_by_slug("dirk")
        if not store:
            logger.error("❌ Dirk store not found in database")
            raise Exception("Dirk store not found")
        
        self.store_id = store["id"]
        logger.info(f"✅ Found Dirk store: {store['name']} (ID: {self.store_id})")
    
    def parse_unit_info(self, unit_text: str) -> Tuple[Optional[float], Optional[str]]:
        """Parse unit size and type from text like '500 g', '1,5 l', '12 stuks'"""
        if not unit_text:
            return None, None
        
        # Clean the string and handle Dutch decimal format
        clean_unit = unit_text.strip().lower().replace(',', '.')
        
        # Extract number and unit
        # Patterns: "500 g", "1.5 l", "12 stuks", "500 ml"
        match = re.match(r'([0-9.]+)\s*([a-zA-Z]+)', clean_unit)
        if match:
            try:
                unit_size = float(match.group(1))
                unit_type = match.group(2).lower()
                # Normalize unit types
                if unit_type in ['stuks', 'stuk', 'st']:
                    unit_type = 'pieces'
                elif unit_type in ['ml']:
                    unit_type = 'ml'
                elif unit_type in ['l', 'liter', 'litre']:
                    unit_type = 'l'
                elif unit_type in ['g', 'gram']:
                    unit_type = 'g'
                elif unit_type in ['kg', 'kilo']:
                    unit_type = 'kg'
                
                return unit_size, unit_type
            except ValueError:
                pass
        
        return None, None
    
    def calculate_discount(self, current_price: float, old_price: float) -> Optional[float]:
        """Calculate discount percentage if there's a promotion"""
        if not old_price or old_price <= current_price:
            return None
        
        return round(((old_price - current_price) / old_price) * 100, 1)
    
    async def process_product(self, product_data: Dict[str, Any]) -> bool:
        """Process a single product and save to database"""
        try:
            # Extract basic info
            name = (product_data.get("name") or "").strip()
            if not name:
                logger.warning("⚠️ Skipping product without name")
                return False
            
            brand = (product_data.get("brand") or "").strip() or None
            category = (product_data.get("category") or "").strip() or None
            subcategory = (product_data.get("sub category") or "").strip() or None
            description = (product_data.get("description") or "").strip() or None
            gtin = (product_data.get("gtin") or "").strip() or None
            external_id = str(product_data.get("product_number", ""))
            
            # Parse unit info
            unit_text = product_data.get("unit") or ""
            unit_size, unit_type = self.parse_unit_info(unit_text)
            
            # Extract pricing
            price_str = product_data.get("price", "")
            old_price_str = product_data.get("old")
            
            if not price_str:
                logger.warning(f"⚠️ Skipping {name} - no price information")
                return False
            
            try:
                # Clean price string and convert to float
                # Handle both string and numeric price formats
                if isinstance(price_str, (int, float)):
                    current_price = float(price_str)
                else:
                    current_price = float(str(price_str).replace('€', '').replace(',', '.').strip())
                
                original_price = None
                if old_price_str:
                    try:
                        if isinstance(old_price_str, (int, float)):
                            original_price = float(old_price_str)
                        else:
                            original_price = float(str(old_price_str).replace('€', '').replace(',', '.').strip())
                    except (ValueError, AttributeError, TypeError):
                        pass
                
                # Check for promotions
                discount_percentage = self.calculate_discount(current_price, original_price) if original_price else None
                is_promotion = bool(original_price and discount_percentage)
                
                # Get promotion text
                offer_text = (product_data.get("offer") or "").strip() or None
                offer_duration = (product_data.get("offer_duration") or "").strip() or None
                promotion_text = None
                if offer_text:
                    promotion_text = offer_text
                    if offer_duration:
                        promotion_text += f" ({offer_duration})"
                
            except (ValueError, AttributeError) as e:
                logger.warning(f"⚠️ Invalid price format for {name}: {price_str}")
                return False
            
            # Extract image URL
            image_url = (product_data.get("image link") or "").strip() or None
            
            # Get store URL
            store_url = (product_data.get("link") or "").strip() or None
            
            # Combine category and subcategory
            full_category = category
            if subcategory:
                full_category = f"{category} > {subcategory}" if category else subcategory
            
            # Save product to database
            product_id = await self.db.save_product(
                name=name,
                brand=brand,
                category=full_category,
                unit_size=unit_size,
                unit_type=unit_type,
                description=description,
                image_url=image_url,
                external_id=external_id
            )
            
            if not product_id:
                logger.error(f"❌ Failed to save product: {name}")
                return False
            
            # Link product to Dirk store
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
                promotion_text=promotion_text
            )
            
            price_text = f"€{current_price:.2f}"
            if original_price:
                price_text += f" (was €{original_price:.2f})"
            if promotion_text:
                price_text += f" - {promotion_text}"
            
            logger.info(f"✅ Imported: {name} - {price_text}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing product {product_data.get('name', 'unknown')}: {e}")
            return False
    
    async def import_products(self, max_products: Optional[int] = None, batch_size: int = 100):
        """Import all products from JSON file"""
        self.stats["start_time"] = datetime.now()
        
        logger.info(f"🚀 Starting Dirk import from {self.json_file_path}")
        
        try:
            # Load JSON data
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            self.stats["total_products"] = len(products)
            
            if max_products:
                products = products[:max_products]
                logger.info(f"📝 Limited to first {max_products} products for testing")
            
            logger.info(f"📊 Processing {len(products)} Dirk products...")
            
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
            
            logger.info(f"🎉 Dirk import completed!")
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
    json_file = "/Users/yusephswessi/Documents/GitHub/admin-product/dirk1.json"
    
    if not os.path.exists(json_file):
        logger.error(f"❌ JSON file not found: {json_file}")
        return
    
    # Create importer and run
    importer = DirkImporter(json_file)
    
    try:
        await importer.initialize()
        
        # Import all products (remove max_products to import all 5,476)
        await importer.import_products()
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return

if __name__ == "__main__":
    asyncio.run(main()) 