"""
URL configuration for fafixed project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from integrations import views as integration_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    
    # New domain-specific URL patterns
    path('connections/', include('connections.urls')),
    path('financial/', include('financial_data.urls')),
    path('quality/', include('data_quality.urls')),
    
    # Legacy integrations URLs (for backward compatibility during transition)
    path('integrations/', include('integrations.urls')),
    
    # Direct Xero callback URL to match developer console configuration
    path('xero/callback/', integration_views.xero_callback, name='xero_callback_direct'),
]
