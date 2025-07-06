"""
WebSocket package for real-time communications
"""

from .connection_manager import get_connection_manager, ConnectionManager

__all__ = ["get_connection_manager", "ConnectionManager"] 