import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    """Result of data processing with original and processed data"""
    success: bool
    original_data: Dict[str, Any]
    processed_data: Dict[str, Any]
    changes: List[str]
    warnings: List[str]
    errors: List[str]

class ProductNormalizer:
    """Handles product name and brand normalization"""
    
    def __init__(self):
        # Common brand variations that should be standardized
        self.brand_mappings = {
            'ah': 'AH',
            'ah biologisch': 'AH Biologisch',
            'ah basic': 'AH Basic',
            'ah excellent': 'AH Excellent',
            'jumbo': 'Jumbo',
            'dr. oetker': 'Dr. Oetker',
            'dr oetker': 'Dr. Oetker',
            'coca cola': 'Coca-Cola',
            'coca-cola': 'Coca-Cola',
        }
        
        # Unit patterns to extract from product names
        self.unit_patterns = [
            r'(\d+(?:\.\d+)?)\s*(ml|l|liter|milliliter)',
            r'(\d+(?:\.\d+)?)\s*(g|kg|gram|kilogram)',
            r'(\d+(?:\.\d+)?)\s*(stuks?|pieces?|st)',
            r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(ml|l|g|kg)',
            r'(\d+(?:\.\d+)?)-?pack',
        ]
        
        # Words to remove for normalization
        self.noise_words = [
            'airfryer', 'oven', 'microwave', 'bio', 'biologisch', 
            'naturel', 'original', 'classic', 'traditional'
        ]

    def normalize_brand(self, brand: Optional[str]) -> Optional[str]:
        """Normalize brand name"""
        if not brand:
            return None
            
        brand_lower = brand.lower().strip()
        
        # Check for exact mappings
        if brand_lower in self.brand_mappings:
            return self.brand_mappings[brand_lower]
            
        # Capitalize first letter of each word for standard brands
        return ' '.join(word.capitalize() for word in brand.split())

    def extract_units_from_name(self, name: str) -> Tuple[Optional[str], Optional[float]]:
        """Extract unit type and size from product name"""
        if not name:
            return None, None
            
        name_lower = name.lower()
        
        for pattern in self.unit_patterns:
            match = re.search(pattern, name_lower)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    try:
                        size = float(groups[0])
                        unit = groups[1].lower()
                        
                        # Standardize unit names
                        unit_standardization = {
                            'ml': 'ml', 'milliliter': 'ml', 'liter': 'l',
                            'g': 'g', 'gram': 'g', 'kg': 'kg', 'kilogram': 'kg',
                            'stuks': 'stuks', 'stuk': 'stuks', 'pieces': 'stuks', 'piece': 'stuks', 'st': 'stuks'
                        }
                        
                        standardized_unit = unit_standardization.get(unit, unit)
                        return standardized_unit, size
                        
                    except (ValueError, IndexError):
                        continue
                        
        return None, None

    def normalize_product_name(self, name: str) -> str:
        """Normalize product name by removing noise and standardizing format"""
        if not name:
            return ""
            
        # Convert to lowercase for processing
        normalized = name.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove units from name (they should be in separate fields)
        for pattern in self.unit_patterns:
            normalized = re.sub(pattern, '', normalized)
            
        # Remove noise words
        words = normalized.split()
        cleaned_words = []
        for word in words:
            if word not in self.noise_words:
                cleaned_words.append(word)
                
        normalized = ' '.join(cleaned_words).strip()
        
        # Remove extra punctuation
        normalized = re.sub(r'[^\w\s&-]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()

class PriceValidator:
    """Handles price validation and outlier detection"""
    
    def __init__(self):
        # Price ranges by category (in euros)
        self.price_ranges = {
            'default': {'min': 0.01, 'max': 500.00},
            'produce': {'min': 0.50, 'max': 20.00},  # Fruits, vegetables
            'dairy': {'min': 0.50, 'max': 15.00},    # Milk, cheese, yogurt
            'meat': {'min': 1.00, 'max': 50.00},     # Meat, fish
            'beverages': {'min': 0.50, 'max': 30.00}, # Drinks
            'snacks': {'min': 0.50, 'max': 10.00},   # Chips, candy
            'household': {'min': 1.00, 'max': 50.00} # Cleaning products
        }

    def validate_price(self, price: Any, original_price: Any = None, category: str = 'default') -> ProcessingResult:
        """Validate price data and check for outliers"""
        changes = []
        warnings = []
        errors = []
        
        try:
            # Convert to Decimal for precise calculations
            if isinstance(price, str):
                price_decimal = Decimal(price)
            elif isinstance(price, (int, float)):
                price_decimal = Decimal(str(price))
            else:
                errors.append(f"Invalid price type: {type(price)}")
                return ProcessingResult(
                    success=False,
                    original_data={'price': price, 'original_price': original_price},
                    processed_data={},
                    changes=changes,
                    warnings=warnings,
                    errors=errors
                )
                
            processed_data = {'price': float(price_decimal)}
            
            # Validate price range
            price_range = self.price_ranges.get(category, self.price_ranges['default'])
            
            if price_decimal < Decimal(str(price_range['min'])):
                warnings.append(f"Price {price_decimal} is below minimum expected ({price_range['min']})")
                
            if price_decimal > Decimal(str(price_range['max'])):
                warnings.append(f"Price {price_decimal} is above maximum expected ({price_range['max']})")
                
            # Validate original price if provided
            if original_price:
                try:
                    if isinstance(original_price, str):
                        original_price_decimal = Decimal(original_price)
                    else:
                        original_price_decimal = Decimal(str(original_price))
                        
                    processed_data['original_price'] = float(original_price_decimal)
                    
                    # Check if discount makes sense
                    if original_price_decimal <= price_decimal:
                        warnings.append("Original price should be higher than current price for valid discount")
                        
                    # Calculate discount percentage
                    discount_pct = ((original_price_decimal - price_decimal) / original_price_decimal) * 100
                    processed_data['discount_percentage'] = float(discount_pct)
                    
                    if discount_pct > 90:
                        warnings.append(f"Discount percentage ({discount_pct:.1f}%) seems unusually high")
                        
                except (InvalidOperation, ValueError) as e:
                    errors.append(f"Invalid original price: {e}")
                    
            return ProcessingResult(
                success=len(errors) == 0,
                original_data={'price': price, 'original_price': original_price},
                processed_data=processed_data,
                changes=changes,
                warnings=warnings,
                errors=errors
            )
            
        except (InvalidOperation, ValueError) as e:
            errors.append(f"Price validation error: {e}")
            return ProcessingResult(
                success=False,
                original_data={'price': price, 'original_price': original_price},
                processed_data={},
                changes=changes,
                warnings=warnings,
                errors=errors
            )

class DataProcessor:
    """Main data processing class that combines all processing steps"""
    
    def __init__(self):
        self.product_normalizer = ProductNormalizer()
        self.price_validator = PriceValidator()
        
    def process_product_data(self, product_data: Dict[str, Any]) -> ProcessingResult:
        """Process complete product data including name, brand, units, and prices"""
        all_changes = []
        all_warnings = []
        all_errors = []
        processed_data = {}
        
        # Process product name
        if 'name' in product_data:
            original_name = product_data['name']
            normalized_name = self.product_normalizer.normalize_product_name(original_name)
            processed_data['normalized_name'] = normalized_name
            
            if normalized_name != original_name.lower():
                all_changes.append(f"Normalized product name: '{original_name}' -> '{normalized_name}'")
                
        # Process brand
        if 'brand' in product_data:
            original_brand = product_data['brand']
            normalized_brand = self.product_normalizer.normalize_brand(original_brand)
            processed_data['brand'] = normalized_brand
            
            if normalized_brand != original_brand:
                all_changes.append(f"Normalized brand: '{original_brand}' -> '{normalized_brand}'")
                
        # Extract units from product name if not already present
        if 'name' in product_data and (not product_data.get('unit_type') or not product_data.get('unit_size')):
            unit_type, unit_size = self.product_normalizer.extract_units_from_name(product_data['name'])
            
            if unit_type and unit_size:
                processed_data['unit_type'] = unit_type
                processed_data['unit_size'] = unit_size
                all_changes.append(f"Extracted units from name: {unit_size} {unit_type}")
            elif not product_data.get('unit_type'):
                all_warnings.append("No unit information available for product")
                
        # Validate prices
        if 'price' in product_data:
            price_result = self.price_validator.validate_price(
                product_data['price'],
                product_data.get('original_price')
            )
            
            processed_data.update(price_result.processed_data)
            all_changes.extend(price_result.changes)
            all_warnings.extend(price_result.warnings)
            all_errors.extend(price_result.errors)
            
        return ProcessingResult(
            success=len(all_errors) == 0,
            original_data=product_data,
            processed_data=processed_data,
            changes=all_changes,
            warnings=all_warnings,
            errors=all_errors
        )

    def process_batch(self, products_data: List[Dict[str, Any]]) -> List[ProcessingResult]:
        """Process a batch of product data"""
        results = []
        
        for product_data in products_data:
            try:
                result = self.process_product_data(product_data)
                results.append(result)
                
                # Log significant issues
                if result.errors:
                    logger.error(f"Processing errors for product {product_data.get('name', 'unknown')}: {result.errors}")
                elif result.warnings:
                    logger.warning(f"Processing warnings for product {product_data.get('name', 'unknown')}: {result.warnings}")
                    
            except Exception as e:
                logger.error(f"Unexpected error processing product {product_data.get('name', 'unknown')}: {e}")
                results.append(ProcessingResult(
                    success=False,
                    original_data=product_data,
                    processed_data={},
                    changes=[],
                    warnings=[],
                    errors=[f"Unexpected processing error: {e}"]
                ))
                
        return results

# Utility functions for integration with existing codebase
def normalize_product_for_database(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to normalize product data for database insertion"""
    processor = DataProcessor()
    result = processor.process_product_data(product_data)
    
    if result.success:
        # Merge original data with processed updates
        normalized_data = {**product_data, **result.processed_data}
        return normalized_data
    else:
        logger.error(f"Failed to normalize product data: {result.errors}")
        return product_data  # Return original if processing failed

def validate_price_data(price: Any, original_price: Any = None) -> bool:
    """Quick validation function for price data"""
    validator = PriceValidator()
    result = validator.validate_price(price, original_price)
    return result.success and len(result.warnings) == 0 