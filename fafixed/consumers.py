"""
WebSocket consumers for real-time communication
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class TurboStreamConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for Turbo Stream updates
    Handles ActionCable-style subscriptions for validation updates
    """
    
    async def connect(self):
        # Accept the WebSocket connection
        await self.accept()
        print(f"WebSocket connection accepted: {self.channel_name}")
    
    async def disconnect(self, close_code):
        # Leave all groups when disconnecting
        for group_name in getattr(self, '_groups', []):
            await self.channel_layer.group_discard(group_name, self.channel_name)
        print(f"WebSocket disconnected: {self.channel_name}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        print(f"WebSocket received: {text_data}")
        
        try:
            data = json.loads(text_data)
            command = data.get('command')
            print(f"Parsed command: {command}")
            
            if command == 'subscribe':
                # ActionCable sends identifier as JSON string, need to parse it
                identifier_str = data.get('identifier', '{}')
                identifier = json.loads(identifier_str) if isinstance(identifier_str, str) else identifier_str
                
                channel = identifier.get('channel')
                stream_name = identifier.get('stream_name')
                
                print(f"Subscribe request - Channel: {channel}, Stream: {stream_name}")
                
                if channel == 'TurboStreamCableChannel' and stream_name:
                    # Join the group for this stream
                    group_name = stream_name
                    await self.channel_layer.group_add(group_name, self.channel_name)
                    
                    # Track groups for cleanup
                    if not hasattr(self, '_groups'):
                        self._groups = []
                    self._groups.append(group_name)
                    
                    print(f"Successfully subscribed to stream: {stream_name}")
                    
                    # Send confirmation in ActionCable format
                    await self.send(text_data=json.dumps({
                        'type': 'confirm_subscription',
                        'identifier': identifier_str
                    }))
                else:
                    print(f"Invalid subscription request - Channel: {channel}, Stream: {stream_name}")
            
            elif command == 'unsubscribe':
                identifier_str = data.get('identifier', '{}')
                identifier = json.loads(identifier_str) if isinstance(identifier_str, str) else identifier_str
                stream_name = identifier.get('stream_name')
                
                if stream_name:
                    # Leave the group
                    await self.channel_layer.group_discard(stream_name, self.channel_name)
                    print(f"Unsubscribed from stream: {stream_name}")
            
            else:
                print(f"Unknown command: {command}")
        
        except json.JSONDecodeError as e:
            print(f"Invalid JSON received: {text_data}, Error: {e}")
        except Exception as e:
            print(f"Error handling message: {e}, Data: {text_data}")
    
    async def turbo_stream_message(self, event):
        """Send turbo stream message to WebSocket"""
        message = event['message']
        
        # Send the turbo stream HTML directly
        await self.send(text_data=json.dumps({
            'type': 'turbo_stream',
            'message': message
        }))