from django.urls import path
from . import views

urlpatterns = [
    path('xero/connect/', views.xero_connect, name='xero_connect'),
    path('xero/callback/', views.xero_callback, name='xero_callback'),
    path('import/', views.import_accounts, name='import_accounts'),
]