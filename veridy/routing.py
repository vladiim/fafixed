"""
ASGI routing configuration for WebSocket support
"""
from django.urls import re_path
from channels.generic.websocket import WebsocketConsumer
import json

class TurboStreamCableConsumer(WebsocketConsumer):
    """ActionCable-compatible consumer for Turbo Streams"""
    
    def connect(self):
        self.accept()
        welcome_msg = {
            "type": "welcome"
        }
        self.send(text_data=json.dumps(welcome_msg))

    def disconnect(self, close_code):
        pass

    def receive(self, text_data):
        try:
            data = json.loads(text_data)
            command = data.get('command')
            identifier = data.get('identifier', {})
            
            if command == 'subscribe':
                # Handle subscription - ActionCable format
                channel_data = json.loads(identifier) if isinstance(identifier, str) else identifier
                channel = channel_data.get('channel')
                stream_name = channel_data.get('stream_name')
                signed_stream_name = channel_data.get('signed_stream_name')
                
                # Handle signed stream names (from turbo-helper)
                if signed_stream_name and not stream_name:
                    try:
                        from turbo_helper.channels.stream_name import verify_signed_stream_key
                        is_valid, unsigned_stream_name = verify_signed_stream_key(signed_stream_name)
                        if is_valid:
                            stream_name = unsigned_stream_name
                        else:
                            return
                    except Exception as e:
                        return
                
                # Add to channel group
                if stream_name:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    group_name = stream_name
                    
                    async_to_sync(channel_layer.group_add)(
                        group_name, self.channel_name
                    )
                
                # Send confirmation
                self.send(text_data=json.dumps({
                    "identifier": identifier,
                    "type": "confirm_subscription"
                }))
                
        except Exception as e:
            import traceback
            traceback.print_exc()

    def turbo_stream_message(self, event):
        """Handle turbo stream messages from group_send"""
        message_data = {
            "identifier": json.dumps({"channel": "TurboStreamCableChannel"}),
            "message": event['message']
        }
        
        self.send(text_data=json.dumps(message_data))

websocket_urlpatterns = [
    re_path(r"^cable$", TurboStreamCableConsumer.as_asgi()),
]