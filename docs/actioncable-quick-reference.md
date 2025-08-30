# ActionCable Quick Reference Guide

This is a quick reference for developers working with the ActionCable real-time system in this Django project.

## Architecture Overview

```
User Click → Stimulus → Django View → Celery Task → Django Signal → WebSocket → DOM Update
```

## Key Files and Their Roles

### Frontend
- `templates/*/partials/*.html` - Turbo Frame templates that get updated
- `static/js/controllers/actioncable_controller.js` - WebSocket connection management
- `static/js/controllers/*_controller.js` - Form handling and UI feedback
- `templates/base.html` - Imports Stimulus and Turbo libraries

### Backend
- `fafixed/routing.py` - ActionCable WebSocket consumer
- `fafixed/asgi.py` - ASGI configuration for WebSocket support
- `*/views.py` - Form processing and task dispatch
- `*/tasks.py` - Background Celery tasks
- `*/signals.py` - Django signals for broadcasting
- `*/models.py` - Data models with lifecycle hooks

### Infrastructure
- `bin/dev` - Development server script (uses Daphne for WebSocket)
- Redis - Message broker for Celery and Channels
- Daphne - ASGI server for WebSocket support

## Quick Implementation Checklist

### ✅ HTML Template
```html
<!-- ActionCable connection -->
<div data-controller="actioncable" 
     data-actioncable-url-value="ws://localhost:8000/cable"
     data-actioncable-subscriptions-value='[{"stream_name": "updates_{{ item.id }}"}]'>
</div>

<!-- Turbo Frame for updates -->
<turbo-frame id="item-{{ item.id }}-actions">
  <!-- Content that will be replaced -->
</turbo-frame>
```

### ✅ Stimulus Controller
```javascript
export default class extends Controller {
  submit(event) {
    // Immediate UI feedback
    const button = this.element.querySelector('button[type="submit"]')
    button.disabled = true
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...'
  }
}
```

### ✅ Django View
```python
@login_required
def process_item(request, item_id):
    task_result = my_background_task.delay(item_id)
    
    return turbo_stream.turbo_stream(
        turbo_stream.replace(
            f"item-{item_id}-actions",
            template="partials/item_actions.html",
            context={'item': item, 'task_id': task_result.id}
        ),
        content_type="text/vnd.turbo-stream.html"
    )
```

### ✅ Background Task
```python
@shared_task(bind=True)
def my_background_task(self, item_id):
    # Do work...
    
    # Update model (triggers signal)
    result = ProcessingResult.objects.create(
        item_id=item_id,
        status='completed',
        result_data=data
    )
    
    return {"status": "completed", "item_id": item_id}
```

### ✅ Django Signal
```python
@receiver(post_save, sender=ProcessingResult)
def broadcast_update(sender, instance, **kwargs):
    if instance.status in ['completed', 'failed']:
        turbo_stream_html = f"""
        <turbo-stream action="replace" target="item-{instance.item.id}-actions">
            <template>{render_to_string('partials/item_actions.html', context)}</template>
        </turbo-stream>
        """
        
        async_to_sync(get_channel_layer().group_send)(
            f"updates_{instance.item.id}",
            {'type': 'turbo_stream_message', 'message': turbo_stream_html}
        )
```

## ActionCable Protocol Messages

### Connection Welcome
```json
{"type": "welcome"}
```

### Subscription Request
```json
{
  "command": "subscribe",
  "identifier": "{\"channel\":\"TurboStreamCableChannel\",\"stream_name\":\"updates_123\"}"
}
```

### Subscription Confirmation
```json
{
  "identifier": "{\"channel\":\"TurboStreamCableChannel\"}",
  "type": "confirm_subscription"
}
```

### Turbo Stream Message
```json
{
  "identifier": "{\"channel\":\"TurboStreamCableChannel\"}",
  "message": "<turbo-stream action=\"replace\" target=\"item-123\">...</turbo-stream>"
}
```

## Common Patterns

### Loading States
```html
{% if task_id %}
  <div class="loading">
    <i class="fas fa-spinner fa-spin"></i>
    Processing... ({{ task_id|slice:":8" }})
  </div>
{% else %}
  <!-- Normal form -->
{% endif %}
```

### Error Handling
```python
# In task
try:
    # Do work
    status = 'completed'
except Exception as e:
    status = 'failed'
    error_message = str(e)
    
# Signal will broadcast either state
```

### Multiple Subscriptions
```html
data-actioncable-subscriptions-value='[
  {"stream_name": "user_updates_{{ user.id }}"},
  {"stream_name": "global_updates"}
]'
```

## Debugging Commands

### Check WebSocket Connection
```javascript
// In browser console
websocket = new WebSocket('ws://localhost:8000/cable')
websocket.onopen = () => console.log('Connected')
websocket.onmessage = (e) => console.log('Message:', e.data)
```

### Monitor Background Tasks
```bash
# Check Celery worker status
celery -A fafixed inspect active

# Monitor task events  
celery -A fafixed events
```

### Check Channel Groups
```python
# In Django shell
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()
# Send test message
async_to_sync(channel_layer.group_send)(
    "updates_123", 
    {"type": "turbo_stream_message", "message": "<p>Test</p>"}
)
```

## Troubleshooting

| Problem | Check |
|---------|-------|
| WebSocket won't connect | Daphne running? ASGI config correct? |
| No real-time updates | Signal registered? Channel groups match? |
| Task not starting | Celery worker running? Task imported? |
| DOM not updating | Turbo Frame ID matches? Valid HTML? |

## Performance Tips

- **Batch Updates**: Group multiple changes into single broadcast
- **Throttle Signals**: Avoid excessive broadcasting from frequent model saves  
- **Connection Limits**: Monitor WebSocket connection count
- **Redis Optimization**: Use Redis for Channels layer in production
- **Selective Broadcasting**: Only broadcast to subscribed users

## Security Considerations

- **Stream Authentication**: Verify user can access stream data
- **Input Validation**: Sanitize data before broadcasting
- **Rate Limiting**: Prevent WebSocket abuse
- **CSRF Protection**: Ensure forms have CSRF tokens
- **Signed Streams**: Use turbo-helper signed stream names in production