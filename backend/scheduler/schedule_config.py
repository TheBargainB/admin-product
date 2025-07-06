"""
Schedule Configuration
Default scheduling configurations and validation for store scrapers.
"""

from datetime import datetime
from typing import Dict, List, Optional
import pytz
from croniter import croniter

class ScheduleConfig:
    """Configuration for store scheduling system."""
    
    # Default timezone for Dutch stores
    DEFAULT_TIMEZONE = "Europe/Amsterdam"
    
    # Default schedule patterns
    DEFAULT_SCHEDULES = {
        'albert_heijn': '0 23 * * 1',    # Monday 11 PM
        'jumbo': '0 22 * * 0',           # Sunday 10 PM
        'dirk': '0 6 * * 2',             # Tuesday 6 AM
        'etos': '0 20 * * 3',            # Wednesday 8 PM
        'hoogvliet': '0 21 * * 1',       # Monday 9 PM
    }
    
    # Schedule types
    SCHEDULE_TYPES = {
        'weekly_price_update': 'Weekly price and product updates',
        'daily_price_check': 'Daily price monitoring (light)',
        'full_catalog_sync': 'Complete product catalog synchronization',
        'promotional_scan': 'Special promotions and deals scan'
    }
    
    # Common cron patterns for easy selection
    COMMON_PATTERNS = {
        'Monday 11 PM': '0 23 * * 1',
        'Tuesday 6 AM': '0 6 * * 2',
        'Wednesday 8 PM': '0 20 * * 3', 
        'Thursday 10 PM': '0 22 * * 4',
        'Friday 7 AM': '0 7 * * 5',
        'Saturday 9 PM': '0 21 * * 6',
        'Sunday 10 PM': '0 22 * * 0',
        'Daily 6 AM': '0 6 * * *',
        'Daily 11 PM': '0 23 * * *',
        'Twice Weekly (Mon/Thu 11 PM)': '0 23 * * 1,4'
    }
    
    @staticmethod
    def validate_cron_expression(cron_expr: str) -> bool:
        """Validate if a cron expression is valid."""
        try:
            croniter(cron_expr)
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def get_next_run_time(cron_expr: str, timezone: str = DEFAULT_TIMEZONE) -> Optional[datetime]:
        """Get the next run time for a cron expression."""
        try:
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            cron = croniter(cron_expr, now)
            return cron.get_next(datetime)
        except Exception:
            return None
    
    @staticmethod
    def get_schedule_description(cron_expr: str) -> str:
        """Get a human-readable description of a cron expression."""
        # Simple mapping for common patterns
        descriptions = {
            '0 23 * * 1': 'Every Monday at 11:00 PM',
            '0 22 * * 0': 'Every Sunday at 10:00 PM',
            '0 6 * * 2': 'Every Tuesday at 6:00 AM',
            '0 20 * * 3': 'Every Wednesday at 8:00 PM',
            '0 21 * * 1': 'Every Monday at 9:00 PM',
            '0 6 * * *': 'Every day at 6:00 AM',
            '0 23 * * *': 'Every day at 11:00 PM',
            '0 23 * * 1,4': 'Every Monday and Thursday at 11:00 PM'
        }
        
        return descriptions.get(cron_expr, f'Custom schedule: {cron_expr}')
    
    @classmethod
    def get_default_schedule(cls, store_slug: str) -> str:
        """Get default cron expression for a store."""
        return cls.DEFAULT_SCHEDULES.get(store_slug, '0 23 * * 1')  # Default to Monday 11 PM
    
    @classmethod
    def is_business_hours(cls, dt: datetime, timezone: str = DEFAULT_TIMEZONE) -> bool:
        """Check if a datetime falls within business hours (to avoid scraping during peak times)."""
        tz = pytz.timezone(timezone)
        local_dt = dt.astimezone(tz)
        
        # Avoid scraping during typical business hours (8 AM - 10 PM)
        return 8 <= local_dt.hour <= 22
    
    @classmethod
    def suggest_optimal_time(cls, store_slug: str) -> str:
        """Suggest optimal scraping time based on store type."""
        # Avoid business hours and spread load across different times
        suggestions = {
            'albert_heijn': '0 23 * * 1',    # Monday 11 PM - after price updates
            'jumbo': '0 22 * * 0',           # Sunday 10 PM - early prep  
            'dirk': '0 6 * * 2',             # Tuesday 6 AM - early morning
            'etos': '0 20 * * 3',            # Wednesday 8 PM - mid-week
            'hoogvliet': '0 21 * * 1',       # Monday 9 PM - before Albert Heijn
        }
        
        return suggestions.get(store_slug, '0 2 * * 1')  # Default: Monday 2 AM (off-peak) 