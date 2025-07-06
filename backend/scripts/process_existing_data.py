#!/usr/bin/env python3
"""
Script to process and normalize existing product data in the database.
This script applies data quality improvements to products that have already been imported.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent.parent))

from database.client import get_database
from utils.data_processing import DataProcessor, ProcessingResult
from utils.logging import setup_logging
import logging

logger = logging.getLogger(__name__)

class DataProcessingManager:
    """Manages the data processing workflow for existing database products"""
    
    def __init__(self):
        self.supabase = None
        self.processor = DataProcessor()
        
    async def initialize(self):
        """Initialize the database connection"""
        self.supabase = await get_database()
        await self.supabase.initialize()
        
    async def get_products_batch(self, offset: int = 0, batch_size: int = 100):
        """Fetch a batch of products from the database"""
        try:
            # Get products with their associated data
            response = self.supabase._client.table('products').select(
                'id, name, normalized_name, brand, unit_type, unit_size, description'
            ).range(offset, offset + batch_size - 1).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error fetching products batch at offset {offset}: {e}")
            return []
    
    async def get_product_prices(self, product_ids: list):
        """Get current prices for a list of products"""
        try:
            # Get current prices via store_products
            response = self.supabase._client.table('current_prices').select(
                'store_product_id, price, original_price, promotion_text, store_products!inner(product_id)'
            ).in_('store_products.product_id', product_ids).execute()
            
            # Group prices by product_id
            prices_by_product = {}
            for price_data in response.data or []:
                product_id = price_data['store_products']['product_id']
                if product_id not in prices_by_product:
                    prices_by_product[product_id] = []
                prices_by_product[product_id].append({
                    'price': price_data['price'],
                    'original_price': price_data['original_price'],
                    'promotion_text': price_data['promotion_text']
                })
                
            return prices_by_product
            
        except Exception as e:
            logger.error(f"Error fetching prices for products: {e}")
            return {}
    
    async def update_product(self, product_id: str, updates: dict):
        """Update a product with processed data"""
        try:
            response = self.supabase._client.table('products').update(updates).eq('id', product_id).execute()
            return response.data is not None
            
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return False
    
    async def process_products_batch(self, products: list) -> dict:
        """Process a batch of products and return statistics"""
        stats = {
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'warnings': 0,
            'changes': 0
        }
        
        if not products:
            return stats
            
        # Get product IDs for price lookup
        product_ids = [p['id'] for p in products]
        prices_by_product = await self.get_product_prices(product_ids)
        
        for product in products:
            try:
                stats['processed'] += 1
                
                # Prepare data for processing (include price data if available)
                product_data = {
                    'name': product['name'],
                    'brand': product['brand'],
                    'unit_type': product['unit_type'],
                    'unit_size': product['unit_size']
                }
                
                # Add price data if available
                product_prices = prices_by_product.get(product['id'], [])
                if product_prices:
                    # Use the first available price for validation
                    first_price = product_prices[0]
                    product_data['price'] = first_price['price']
                    product_data['original_price'] = first_price['original_price']
                
                # Process the product data
                result = self.processor.process_product_data(product_data)
                
                if result.errors:
                    stats['errors'] += 1
                    logger.error(f"Processing errors for product {product['name']}: {result.errors}")
                    continue
                    
                if result.warnings:
                    stats['warnings'] += 1
                    logger.warning(f"Processing warnings for product {product['name']}: {result.warnings}")
                
                # Check if there are any changes to apply
                updates_to_apply = {}
                
                # Check normalized_name
                if 'normalized_name' in result.processed_data:
                    new_normalized = result.processed_data['normalized_name']
                    current_normalized = product['normalized_name'] or ''
                    if new_normalized != current_normalized:
                        updates_to_apply['normalized_name'] = new_normalized
                        
                # Check brand normalization
                if 'brand' in result.processed_data and result.processed_data['brand'] != product['brand']:
                    updates_to_apply['brand'] = result.processed_data['brand']
                    
                # Check unit extraction
                if 'unit_type' in result.processed_data and not product['unit_type']:
                    updates_to_apply['unit_type'] = result.processed_data['unit_type']
                    
                if 'unit_size' in result.processed_data and not product['unit_size']:
                    updates_to_apply['unit_size'] = result.processed_data['unit_size']
                
                # Apply updates if there are any
                if updates_to_apply:
                    success = await self.update_product(product['id'], updates_to_apply)
                    if success:
                        stats['updated'] += 1
                        stats['changes'] += len(updates_to_apply)
                        logger.info(f"Updated product '{product['name']}' with: {list(updates_to_apply.keys())}")
                    else:
                        stats['errors'] += 1
                        
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Unexpected error processing product {product.get('name', 'unknown')}: {e}")
                
        return stats
    
    async def process_all_products(self, batch_size: int = 100, max_batches: int = None):
        """Process all products in the database"""
        logger.info("Starting data processing for all products...")
        
        total_stats = {
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'warnings': 0,
            'changes': 0,
            'batches': 0
        }
        
        offset = 0
        batch_num = 0
        
        while True:
            # Check max_batches limit
            if max_batches and batch_num >= max_batches:
                logger.info(f"Reached maximum batch limit ({max_batches})")
                break
                
            # Fetch batch
            products = await self.get_products_batch(offset, batch_size)
            if not products:
                logger.info("No more products to process")
                break
                
            batch_num += 1
            logger.info(f"Processing batch {batch_num}: {len(products)} products (offset: {offset})")
            
            # Process batch
            batch_stats = await self.process_products_batch(products)
            
            # Update totals
            for key in total_stats:
                if key != 'batches':
                    total_stats[key] += batch_stats.get(key, 0)
            total_stats['batches'] = batch_num
            
            # Log batch results
            logger.info(f"Batch {batch_num} results: {batch_stats}")
            
            # Move to next batch
            offset += batch_size
            
            # Break if we got fewer products than batch_size (last batch)
            if len(products) < batch_size:
                logger.info("Reached end of products")
                break
        
        # Log final results
        logger.info("=== FINAL PROCESSING RESULTS ===")
        logger.info(f"Batches processed: {total_stats['batches']}")
        logger.info(f"Products processed: {total_stats['processed']}")
        logger.info(f"Products updated: {total_stats['updated']}")
        logger.info(f"Total changes applied: {total_stats['changes']}")
        logger.info(f"Warnings: {total_stats['warnings']}")
        logger.info(f"Errors: {total_stats['errors']}")
        
        if total_stats['processed'] > 0:
            success_rate = (total_stats['updated'] / total_stats['processed']) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")
            
        return total_stats

async def test_processing():
    """Test the data processing on a small sample"""
    logger.info("Running data processing test...")
    
    manager = DataProcessingManager()
    await manager.initialize()
    
    # Test with just 10 products
    stats = await manager.process_all_products(batch_size=10, max_batches=1)
    
    logger.info("Test completed successfully")
    return stats

async def main():
    """Main function to run data processing"""
    setup_logging()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Run test mode
        await test_processing()
    else:
        # Run full processing
        manager = DataProcessingManager()
        await manager.initialize()
        await manager.process_all_products(batch_size=50)  # Process in smaller batches for safety

if __name__ == "__main__":
    asyncio.run(main()) 