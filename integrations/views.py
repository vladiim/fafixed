# integrations/views.py
#
# This file now contains only shared services and utilities.
# All domain-specific views have been moved to their respective apps:
# - OAuth & connection management → connections/views.py
# - Transaction management → financial_data/views.py  
# - Issue management & validation → data_quality/views.py
#
# The integrations app now serves as a shared services layer containing:
# - Service registry and external API connections (services/)
# - Cross-domain business logic managers (managers.py)
# - Shared Celery tasks (tasks.py)
# - Legacy model compatibility during transition (models.py)

from django.shortcuts import render

# Any shared utility views that span multiple domains can be added here
# Currently all functionality has been properly decomposed to domain apps

def health_check(request):
    """Health check endpoint for the integrations shared services"""
    return render(request, 'integrations/health.html', {
        'status': 'healthy',
        'message': 'Integrations shared services layer operational'
    })