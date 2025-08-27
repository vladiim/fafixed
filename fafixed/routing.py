"""
ASGI routing configuration for WebSocket support
"""
from django.urls import re_path
from .consumers import TurboStreamConsumer

websocket_urlpatterns = [
    re_path(r"^cable$", TurboStreamConsumer.as_asgi()),
]