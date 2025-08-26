import os
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def static_cached(path):
    """
    Get static file URL with cache busting parameter based on file modification time
    """
    static_url = static(path)
    
    # Get the full file path
    static_path = os.path.join(settings.STATIC_ROOT, path)
    
    # Get modification time if file exists
    if os.path.exists(static_path):
        mtime = int(os.path.getmtime(static_path))
        return f"{static_url}?v={mtime}"
    
    return static_url