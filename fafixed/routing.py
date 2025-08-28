"""
ASGI routing configuration for WebSocket support
"""
from django.urls import re_path
from channels.generic.websocket import WebsocketConsumer
import json

class TurboStreamCableConsumer(WebsocketConsumer):
    """ActionCable-compatible consumer for Turbo Streams"""
    
    def connect(self):
        print("🔌 SPIKE: TurboStream WebSocket connected!")
        self.accept()
        # ActionCable welcome message
        self.send(text_data=json.dumps({
            "type": "welcome"
        }))

    def disconnect(self, close_code):
        print(f"❌ SPIKE: TurboStream WebSocket disconnected: {close_code}")

    def receive(self, text_data):
        print(f"📨 SPIKE: WebSocket received: {text_data}")
        
        try:
            data = json.loads(text_data)
            command = data.get('command')
            identifier = data.get('identifier', {})
            
            print(f"🎯 SPIKE: Command: {command}, Identifier: {identifier}")
            
            if command == 'subscribe':
                # Handle subscription - ActionCable format
                channel_data = json.loads(identifier) if isinstance(identifier, str) else identifier
                channel = channel_data.get('channel')
                stream_name = channel_data.get('stream_name')
                
                print(f"📡 SPIKE: Subscribing to channel: {channel}, stream: {stream_name}")
                
                # Add to channel group
                if stream_name:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    group_name = stream_name
                    
                    async_to_sync(channel_layer.group_add)(
                        group_name, self.channel_name
                    )
                    print(f"✅ SPIKE: Added to group: {group_name}")
                
                # Send confirmation
                self.send(text_data=json.dumps({
                    "identifier": identifier,
                    "type": "confirm_subscription"
                }))
                
                # Send a test turbo stream message immediately
                test_html = '''
                <turbo-stream action="replace" target="test-frame">
                    <template>
                        <div style="border: 2px solid green; padding: 20px; margin: 10px;">
                            <h2>✅ Hello WebSocket!</h2>
                            <p>🎉 ActionCable WebSocket connection is working!</p>
                            <p>Stream: transaction_updates_169</p>
                            <p>Current time: <span id="timestamp">''' + str(data) + '''</span></p>
                        </div>
                    </template>
                </turbo-stream>
                '''
                
                self.send(text_data=json.dumps({
                    "identifier": identifier,
                    "message": test_html
                }))
                print(f"🚀 SPIKE: Sent test turbo stream message")
                
        except Exception as e:
            print(f"❌ SPIKE: Error processing message: {e}")
            import traceback
            traceback.print_exc()

    def turbo_stream_message(self, event):
        """Handle turbo stream messages from group_send"""
        print(f"📤 SPIKE: Sending turbo stream: {event['message'][:100]}...")
        self.send(text_data=json.dumps({
            "identifier": json.dumps({"channel": "TurboStreamCableChannel"}),
            "message": event['message']
        }))

websocket_urlpatterns = [
    re_path(r"^cable$", TurboStreamCableConsumer.as_asgi()),
]