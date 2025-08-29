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
    
    logger.info(f"🔔 VALIDATION SIGNAL: TransactionValidationStatus {instance.id}, status: {instance.status}")
    
    # Only broadcast when validation completes or fails
    if instance.status not in ['completed', 'failed']:
        logger.info(f"⏭️ VALIDATION SIGNAL: Status '{instance.status}' - not broadcasting yet")
        return
    
    logger.info(f"🔔 VALIDATION SIGNAL: Broadcasting validation result for transaction {instance.transaction_id}")
    
    try:
        # Render the actual template to get completed validation UI
        from django.template.loader import render_to_string
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        template_html = render_to_string(
            'integrations/partials/transaction_actions.html',
            {
                'transaction': instance.transaction,
                'task_id': None,  # No task_id = validation completed
            }
        )
        
        # Create turbo stream to replace the transaction frame
        turbo_stream_html = f"""
        <turbo-stream action="replace" target="transaction-{instance.transaction_id}-actions">
            <template>{template_html}</template>
        </turbo-stream>
        """
        
        # Broadcast validation result via ActionCable
        channel_layer = get_channel_layer()
        group_name = f"transaction_updates_{instance.transaction_id}"
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'turbo_stream_message',
                'message': turbo_stream_html
            }
        )
        
        logger.info(f"✅ VALIDATION SIGNAL: Broadcasted to {group_name}")
        
    except Exception as e:
        logger.error(f"❌ VALIDATION SIGNAL: Failed to broadcast validation update: {e}", exc_info=True)


