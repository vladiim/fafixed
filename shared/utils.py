"""
Common utility functions for the application
"""

from typing import Dict, Any, Optional
from django.http import HttpResponse
from django.template.loader import render_to_string


def format_currency(amount: float, currency: str = "AUD") -> str:
    """Format currency amount for display"""
    if amount is None: return "—"
    if amount < 0: return f"-{currency} {abs(amount):,.2f}"
    
    return f"{currency} {amount:,.2f}"


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if longer than max_length"""
    if not text: return ""
    if len(text) <= max_length: return text
    
    return text[:max_length-3] + "..."


def get_status_color(status: str) -> str:
    """Get CSS color class for status indicators"""
    status_colors = {
        'active': 'text-green-600',
        'inactive': 'text-gray-500',
        'pending': 'text-yellow-600',
        'error': 'text-red-600',
        'syncing': 'text-blue-600',
        'complete': 'text-green-600',
        'failed': 'text-red-600',
    }
    return status_colors.get(status.lower(), 'text-gray-500')


def safe_dict_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from nested dictionary"""
    if not isinstance(data, dict): return default
    
    return data.get(key, default)


def build_query_string(params: Dict[str, Any]) -> str:
    """Build URL query string from parameters, excluding None values"""
    if not params: return ""
    
    # Filter out None values and convert to strings
    clean_params = {
        str(k): str(v) 
        for k, v in params.items() 
        if v is not None
    }
    
    if not clean_params: return ""
    
    from urllib.parse import urlencode
    return f"?{urlencode(clean_params)}"


def render_turbo_stream(action: str, target: str, template: str, context: Optional[Dict] = None) -> HttpResponse:
    """
    Helper to render Turbo Stream responses
    
    Args:
        action: Turbo Stream action (replace, update, append, prepend, remove)
        target: CSS selector for the target element
        template: Template path to render
        context: Template context dict
    """
    if context is None: context = {}
    
    # Render the partial template
    content = render_to_string(template, context)
    
    # Wrap in Turbo Stream format
    turbo_stream = f'<turbo-stream action="{action}" target="{target}">'
    turbo_stream += f'<template>{content}</template>'
    turbo_stream += '</turbo-stream>'
    
    return HttpResponse(
        turbo_stream,
        content_type='text/vnd.turbo-stream.html'
    )