from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from turbo_helper.channels.broadcasts import broadcast_render_to
from .models import TransactionValidationStatus, TransactionData


@receiver(post_save, sender=TransactionValidationStatus)
def broadcast_validation_update(sender, instance, **kwargs):
    """Broadcast validation status changes via Turbo Streams"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Signal fired for TransactionValidationStatus {instance.id}, status: {instance.status}")
    
    if instance.status in ['completed', 'failed']:
        logger.info(f"Broadcasting update for transaction {instance.transaction_id}")
        
        # Create minimal HTML without any method calls that might trigger template rendering
        transaction_id = instance.transaction_id
        
        # Determine button state based on validation status
        if instance.status == 'completed' and instance.passed:
            button_classes = "border-green-300 text-green-700 bg-green-50 hover:bg-green-100"
            icon_class = "fas fa-check-circle"
            status_text = "Validation Passed"
        else:
            button_classes = "border-red-300 text-red-700 bg-red-50 hover:bg-red-100"
            icon_class = "fas fa-exclamation-triangle"
            status_text = "Validation Failed" if instance.status == 'failed' else "Validation Complete"
        
        # Simple HTML without any Django method calls
        html = f'''
        <turbo-cable-stream-source channel="TurboStreamCableChannel" stream-name="validation_updates_{transaction_id}"></turbo-cable-stream-source>
        <turbo-frame id="transaction-{transaction_id}-actions">
            <div class="flex items-center space-x-3">
                <button class="text-brand-black hover:text-brand-green transition-colors" title="View transaction details">
                    <i class="fas fa-eye"></i>
                    <span class="sr-only">View</span>
                    View
                </button>
                
                <div class="relative" data-controller="dropdown">
                    <button type="button" class="flex items-center space-x-1 px-3 py-1 rounded-md text-xs font-medium border transition-colors {button_classes}" data-action="click->dropdown#toggle" title="Validation completed">
                        <i class="{icon_class} mr-2"></i>
                        <span>{status_text}</span>
                        <i class="fas fa-chevron-down"></i>
                    </button>
                    <div class="absolute right-0 mt-2 w-72 bg-white rounded-lg shadow-lg border border-gray-200 hidden z-10" data-dropdown-target="menu">
                        <div class="p-4">
                            <h4 class="text-sm font-medium text-gray-900 mb-3">Validation Complete</h4>
                            <div class="text-sm text-gray-600">
                                Status: {status_text}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </turbo-frame>
        '''
        
        # Create turbo stream update
        turbo_stream_html = f"""
            <turbo-stream action="replace" target="transaction-{instance.transaction_id}-actions">
                <template>{html}</template>
            </turbo-stream>
        """
        
        # Broadcast to the specific validation updates channel
        channel_layer = get_channel_layer()
        group_name = f"validation_updates_{instance.transaction_id}"
        logger.info(f"Broadcasting to group: {group_name}")
        
        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'turbo_stream_message',
                    'message': turbo_stream_html
                }
            )
            logger.info(f"Successfully broadcasted update for transaction {instance.transaction_id}")
        except Exception as e:
            logger.error(f"Failed to broadcast: {e}")


@receiver(post_save, sender=TransactionData)
def broadcast_transaction_update(sender, instance, **kwargs):
    """SPIKE: Broadcast transaction updates via django-turbo-helper"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔔 SPIKE SIGNAL: Transaction {instance.id} updated, broadcasting via turbo-helper")
    
    try:
        # SPIKE: Send a simple test message instead of complex template
        from turbo_helper.channels.broadcasts import broadcast_action_to
        
        # Create simple HTML that will clearly show if WebSocket works
        simple_html = f"""
        <div style="border: 2px solid green; padding: 20px; margin: 10px;">
            <h2>✅ Hello WebSocket!</h2>
            <p>🎉 WebSocket connection is working!</p>
            <p>Transaction {instance.id} updated at {instance.updated_at.strftime('%H:%M:%S')}</p>
            <p>Current time: <span id="timestamp">Live updating...</span></p>
        </div>
        """
        
        broadcast_action_to(
            "transaction_updates", 
            instance.id, 
            action="replace", 
            target="test-frame", 
            html=simple_html
        )
        logger.info(f"✅ SPIKE SIGNAL: Successfully broadcasted HELLO WEBSOCKET for transaction {instance.id}")
        
    except Exception as e:
        logger.error(f"❌ SPIKE SIGNAL: Failed to broadcast transaction update: {e}", exc_info=True)