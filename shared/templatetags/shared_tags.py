"""
Shared template tags and filters for common functionality
"""

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from shared.utils import format_currency, truncate_text, get_status_color

register = template.Library()


@register.filter
def currency(value, currency_code="AUD"):
    """Format currency amount"""
    return format_currency(value, currency_code)


@register.filter
def truncate(value, max_length=50):
    """Truncate text with ellipsis"""
    return truncate_text(str(value), int(max_length))


@register.filter
def status_color(status):
    """Get CSS color class for status"""
    return get_status_color(status)


@register.simple_tag
def status_badge(status, text=None):
    """Render a status badge with appropriate styling"""
    if not text: text = status.title()
    color_class = get_status_color(status)
    
    return format_html(
        '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">{}</span>',
        color_class,
        text
    )


@register.simple_tag
def progress_bar(current, total, show_percentage=True):
    """Render a progress bar"""
    if not total or total == 0: percentage = 0
    else: percentage = min((current / total) * 100, 100)
    
    progress_html = f"""
    <div class="w-full bg-gray-200 rounded-full h-2">
        <div class="bg-blue-600 h-2 rounded-full" style="width: {percentage}%"></div>
    </div>
    """
    
    if show_percentage:
        progress_html += f'<span class="text-sm text-gray-600 ml-2">{percentage:.0f}%</span>'
    
    return mark_safe(progress_html)


@register.simple_tag
def turbo_frame(frame_id, src=None, loading="eager"):
    """Generate turbo-frame tag"""
    if src:
        return format_html(
            '<turbo-frame id="{}" src="{}" loading="{}">Loading...</turbo-frame>',
            frame_id, src, loading
        )
    else:
        return format_html('<turbo-frame id="{}">', frame_id)


@register.simple_tag
def turbo_frame_end():
    """Close turbo-frame tag"""
    return mark_safe('</turbo-frame>')


@register.inclusion_tag('shared/components/loading_spinner.html')
def loading_spinner(size="md", color="blue"):
    """Render a loading spinner component"""
    size_classes = {
        'sm': 'h-4 w-4',
        'md': 'h-6 w-6', 
        'lg': 'h-8 w-8'
    }
    
    return {
        'size_class': size_classes.get(size, 'h-6 w-6'),
        'color': color
    }


@register.simple_tag(takes_context=True)
def active_nav(context, url_name):
    """Return 'active' if current URL matches the given URL name"""
    request = context.get('request')
    if not request: return ""
    
    if request.resolver_match and request.resolver_match.url_name == url_name:
        return "active"
    
    return ""


@register.filter
def dict_get(dictionary, key):
    """Get value from dictionary in template"""
    if not isinstance(dictionary, dict): return None
    
    return dictionary.get(key)


@register.simple_tag
def query_string(request, **kwargs):
    """Build query string with updated parameters"""
    from shared.utils import build_query_string
    
    # Start with current GET parameters
    params = dict(request.GET)
    
    # Update with provided kwargs
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)  # Remove parameter if value is None
        else:
            params[key] = value
    
    return build_query_string(params)