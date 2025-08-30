# Django ActionCable Real-time Feature Implementation Guide

This guide walks you through implementing a complete real-time feature using Django, ActionCable protocol, and Turbo Streams - from user interaction to WebSocket response.

## Overview

We'll build a real-time feature that follows this flow:
1. **User Interaction** → Button click triggers form submission
2. **Stimulus Controller** → Handles form submission and UI feedback  
3. **Django View** → Processes request and starts background task
4. **Background Task** → Performs long-running work
5. **Django Signal** → Broadcasts completion via Turbo Stream
6. **WebSocket** → Delivers real-time update to browser
7. **DOM Update** → Turbo Stream updates UI without page refresh

## Prerequisites

Ensure you have these components already set up (refer to existing codebase):

- ✅ Django Channels configured (`fafixed/asgi.py`)
- ✅ ActionCable WebSocket consumer (`fafixed/routing.py`)
- ✅ Celery for background tasks
- ✅ ASGI server (Daphne) running
- ✅ ActionCable Stimulus controller (`static/js/controllers/actioncable_controller.js`)
- ✅ Base HTML template with Stimulus imports

## Step-by-Step Implementation

### Step 1: Create the HTML Template with Turbo Frame

Create your main template that includes the ActionCable connection and Turbo Frame.

**File: `templates/myapp/feature_list.html`**

```html
{% extends 'base.html' %}
{% load turbo_helper %}

{% block content %}
<!-- ActionCable WebSocket connection -->
<div data-controller="actioncable" 
     data-actioncable-url-value="ws://localhost:8000/cable"
     data-actioncable-subscriptions-value='[{% for item in items %}{"stream_name": "feature_updates_{{ item.id }}"}{% if not forloop.last %},{% endif %}{% endfor %}]'>
</div>

<div class="container">
    <h1>My Real-time Features</h1>
    
    {% for item in items %}
    <div class="item-row">
        <h3>{{ item.name }}</h3>
        
        <!-- This Turbo Frame will be updated via WebSocket -->
        {% include 'myapp/partials/feature_actions.html' %}
    </div>
    {% endfor %}
</div>
{% endblock %}
```

### Step 2: Create the Turbo Frame Partial

This partial contains the interactive elements that will be updated in real-time.

**File: `templates/myapp/partials/feature_actions.html`**

```html
{% load turbo_helper %}

<turbo-frame id="feature-{{ item.id }}-actions">
    <div class="actions-container">
        {% if task_id %}
            <!-- Loading state when background task is running -->
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i>
                Processing... (Task: {{ task_id|slice:":8" }})
            </div>
        {% else %}
            <!-- Interactive form -->
            <form action="{% url 'process_feature' item.id %}" 
                  method="post"
                  data-controller="feature-processor"
                  data-action="submit->feature-processor#submit"
                  data-turbo-frame="feature-{{ item.id }}-actions">
                {% csrf_token %}
                
                <input type="hidden" name="feature_type" value="example_process">
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="options" value="option1" checked>
                        Option 1
                    </label>
                    <label>
                        <input type="checkbox" name="options" value="option2">
                        Option 2  
                    </label>
                </div>
                
                <button type="submit" class="btn btn-primary">
                    Start Processing
                </button>
            </form>
            
            {% if last_result %}
            <div class="result-summary">
                Last result: {{ last_result.status }} 
                ({{ last_result.completed_at|timesince }} ago)
            </div>
            {% endif %}
        {% endif %}
    </div>
</turbo-frame>
```

### Step 3: Create Stimulus Controller for Form Handling

This controller provides immediate UI feedback when the form is submitted.

**File: `static/js/controllers/feature_processor_controller.js`**

```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  submit(event) {
    // Provide immediate feedback while form submits
    const submitButton = this.element.querySelector('button[type="submit"]')
    const originalText = submitButton.textContent
    
    submitButton.disabled = true
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...'
    
    // Optional: Reset button if form submission fails
    setTimeout(() => {
      if (submitButton.disabled) {
        submitButton.disabled = false
        submitButton.textContent = originalText
      }
    }, 10000) // 10 second timeout
  }
}
```

Register the controller in `static/js/stimulus.js`:

```javascript
import FeatureProcessorController from "./controllers/feature_processor_controller.js"

application.register("feature-processor", FeatureProcessorController)
```

### Step 4: Create Django View

The view handles the form submission and starts the background task.

**File: `myapp/views.py`**

```python
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from turbo_helper import turbo_stream
from .models import FeatureItem, ProcessingTask
from .tasks import process_feature_task
import logging

logger = logging.getLogger(__name__)

@login_required
def feature_list(request):
    """Display list of features with real-time controls"""
    items = FeatureItem.objects.filter(user=request.user)
    return render(request, 'myapp/feature_list.html', {
        'items': items
    })

@login_required  
def process_feature(request, item_id):
    """Start background processing for a feature"""
    item = get_object_or_404(FeatureItem, id=item_id, user=request.user)
    
    if request.method == 'POST':
        # Get form data
        feature_type = request.POST.get('feature_type')
        options = request.POST.getlist('options')
        
        logger.info(f"Starting {feature_type} processing for item {item_id}")
        
        # Start background task
        task_result = process_feature_task.delay(
            item_id=item_id,
            feature_type=feature_type,
            options=options,
            user_id=request.user.id
        )
        
        logger.info(f"Started task {task_result.id} for item {item_id}")
        
        # Return Turbo Stream response showing loading state
        return turbo_stream.turbo_stream(
            turbo_stream.replace(
                f"feature-{item_id}-actions",
                template="myapp/partials/feature_actions.html",
                context={
                    'item': item,
                    'task_id': task_result.id,
                }
            ),
            content_type="text/vnd.turbo-stream.html"
        )
    
    # GET request - just render the partial
    return render(request, 'myapp/partials/feature_actions.html', {
        'item': item,
    })
```

### Step 5: Create Background Task

The Celery task performs the actual work and updates the database.

**File: `myapp/tasks.py`**

```python
from celery import shared_task
from django.utils import timezone
from .models import FeatureItem, ProcessingResult
import logging
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30})
def process_feature_task(self, item_id, feature_type, options, user_id):
    """
    Background task to process a feature item
    
    Args:
        item_id: ID of the FeatureItem to process
        feature_type: Type of processing to perform
        options: List of selected options
        user_id: ID of the user who initiated the task
    """
    logger.info(f"Processing feature {item_id} with type '{feature_type}' and options {options}")
    
    try:
        # Get the feature item
        feature_item = FeatureItem.objects.get(id=item_id)
        
        # Create processing record
        processing_result = ProcessingResult.objects.create(
            feature_item=feature_item,
            processing_type=feature_type,
            status='running',
            started_at=timezone.now(),
            task_id=self.request.id
        )
        
        # Simulate processing work
        logger.info(f"Performing {feature_type} processing...")
        
        results = {
            "items_processed": 0,
            "items_passed": 0, 
            "items_failed": 0,
            "errors": []
        }
        
        # Example processing logic
        for i, option in enumerate(options):
            logger.info(f"Processing option: {option}")
            
            # Simulate work
            time.sleep(2)
            
            # Simulate results
            if option == "option1":
                results["items_processed"] += 5
                results["items_passed"] += 4
                results["items_failed"] += 1
            elif option == "option2":
                results["items_processed"] += 3
                results["items_passed"] += 3
                results["items_failed"] += 0
        
        # Mark as completed
        processing_result.status = 'completed'
        processing_result.completed_at = timezone.now()
        processing_result.result_data = results
        processing_result.save()
        
        # Update the feature item's last_processed timestamp
        feature_item.last_processed_at = timezone.now()
        feature_item.save()
        
        logger.info(f"Completed processing for feature {item_id}: {results}")
        
        # The model save() will trigger Django signals which broadcast the update
        return {
            "item_id": item_id,
            "status": "completed",
            "results": results,
            "processing_result_id": processing_result.id
        }
        
    except FeatureItem.DoesNotExist:
        error_msg = f"FeatureItem {item_id} not found"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        # Mark processing as failed
        try:
            processing_result = ProcessingResult.objects.get(
                feature_item_id=item_id,
                task_id=self.request.id
            )
            processing_result.status = 'failed'
            processing_result.completed_at = timezone.now()
            processing_result.error_message = str(e)
            processing_result.save()
        except:
            pass
            
        error_msg = f"Failed to process feature {item_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise
```

### Step 6: Create Django Signal for Broadcasting

The signal automatically broadcasts updates when processing completes.

**File: `myapp/signals.py`**

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.template.loader import render_to_string
from .models import ProcessingResult
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=ProcessingResult)
def broadcast_processing_update(sender, instance, **kwargs):
    """Broadcast processing result updates via Turbo Streams"""
    
    logger.info(f"Processing result signal: {instance.id}, status: {instance.status}")
    
    # Only broadcast when processing completes or fails
    if instance.status not in ['completed', 'failed']:
        logger.info(f"Status '{instance.status}' - not broadcasting yet")
        return
    
    logger.info(f"Broadcasting processing result for feature {instance.feature_item.id}")
    
    try:
        # Render the updated template
        template_html = render_to_string(
            'myapp/partials/feature_actions.html',
            {
                'item': instance.feature_item,
                'task_id': None,  # Clear task_id to show completed state
                'last_result': instance,
            }
        )
        
        # Create turbo stream to replace the feature frame
        turbo_stream_html = f"""
        <turbo-stream action="replace" target="feature-{instance.feature_item.id}-actions">
            <template>{template_html}</template>
        </turbo-stream>
        """
        
        # Broadcast via ActionCable
        channel_layer = get_channel_layer()
        group_name = f"feature_updates_{instance.feature_item.id}"
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'turbo_stream_message',
                'message': turbo_stream_html
            }
        )
        
        logger.info(f"Broadcasted processing update to {group_name}")
        
    except Exception as e:
        logger.error(f"Failed to broadcast processing update: {e}", exc_info=True)
```

Don't forget to register the signal in your app's `apps.py`:

```python
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    
    def ready(self):
        import myapp.signals  # Import signals
```

### Step 7: Create Models

Define the data models that support your feature.

**File: `myapp/models.py`**

```python
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class FeatureItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_processed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.user.email})"

class ProcessingResult(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    feature_item = models.ForeignKey(FeatureItem, on_delete=models.CASCADE, related_name='processing_results')
    processing_type = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    task_id = models.CharField(max_length=100, null=True, blank=True)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    result_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.feature_item.name} - {self.processing_type} ({self.status})"
```

### Step 8: Add URL Configuration

Wire up your views with URL patterns.

**File: `myapp/urls.py`**

```python
from django.urls import path
from . import views

urlpatterns = [
    path('features/', views.feature_list, name='feature_list'),
    path('features/<int:item_id>/process/', views.process_feature, name='process_feature'),
]
```

Include in your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... other patterns
    path('myapp/', include('myapp.urls')),
]
```

## Testing Your Implementation

### 1. Start the Development Server
```bash
./bin/dev  # This starts Daphne with WebSocket support
```

### 2. Test the Flow
1. **Navigate** to `/myapp/features/`
2. **Click** "Start Processing" on any feature
3. **Observe** immediate UI feedback (loading spinner)
4. **Watch** for real-time update when task completes (~4-6 seconds)
5. **Verify** no page refresh occurred

### 3. Debug with Browser DevTools
- **Network Tab**: Check for WebSocket connection to `ws://localhost:8000/cable`
- **Console**: Look for ActionCable subscription confirmations
- **Elements**: Watch DOM changes when Turbo Streams arrive

### 4. Check Server Logs
```bash
# Look for these log patterns:
# ✅ WebSocket connection established
# ✅ ActionCable subscription confirmed  
# ✅ Background task started
# ✅ Signal fired and broadcasted
# ✅ Turbo Stream delivered
```

## Advanced Patterns

### Broadcasting to Multiple Users
```python
# In your signal handler, broadcast to multiple streams:
user_group = f"user_updates_{instance.feature_item.user.id}"
global_group = f"global_feature_updates"

for group_name in [item_group, user_group, global_group]:
    async_to_sync(channel_layer.group_send)(group_name, message)
```

### Progress Updates During Task Execution
```python
# In your task, send periodic updates:
from .signals import broadcast_progress_update

@shared_task(bind=True)
def long_running_task(self, item_id):
    for i in range(10):
        # Do work
        progress = (i + 1) / 10 * 100
        
        # Broadcast progress
        broadcast_progress_update(item_id, progress, self.request.id)
        time.sleep(1)
```

### Error Handling and Retry Logic
```python
# Add retry logic to your tasks:
@shared_task(bind=True, autoretry_for=(ConnectionError,), 
             retry_kwargs={'max_retries': 3, 'countdown': 60})
def robust_task(self, item_id):
    try:
        # Task logic
        pass
    except Exception as exc:
        logger.error(f"Task failed: {exc}")
        # Broadcast error state
        broadcast_error_update(item_id, str(exc))
        raise
```

## Troubleshooting

### Common Issues

1. **WebSocket Not Connecting**
   - Verify Daphne server is running (not Django dev server)
   - Check ASGI configuration in `fafixed/asgi.py`
   - Ensure WebSocket URL matches your server

2. **Turbo Streams Not Working**
   - Verify ActionCable consumer implements proper protocol
   - Check Turbo Frame IDs match exactly
   - Ensure `turbo_stream_message` handler exists in consumer

3. **Background Tasks Not Starting**
   - Verify Celery worker is running
   - Check task import paths and registration
   - Review task arguments and serialization

4. **Signals Not Broadcasting**
   - Ensure signals are imported in `apps.py`  
   - Check Django Channels layer configuration
   - Verify group names match subscription streams

### Debug Commands
```bash
# Check WebSocket connections
netstat -an | grep 8000

# Monitor Celery tasks
celery -A fafixed events

# Test ActionCable protocol
websocat ws://localhost:8000/cable
```

## Production Considerations

### Security
- Add authentication to WebSocket consumer
- Validate user permissions for stream subscriptions  
- Sanitize data before broadcasting

### Performance
- Use Redis for Channels layer in production
- Implement connection throttling
- Add monitoring for WebSocket connections

### Scaling
- Use Redis Cluster for large deployments
- Consider WebSocket connection limits
- Implement graceful degradation for WebSocket failures

---

## Summary

You now have a complete real-time feature that:
- ✅ Provides immediate UI feedback on user interaction
- ✅ Processes work in the background without blocking
- ✅ Updates the UI in real-time via WebSocket
- ✅ Follows Rails ActionCable patterns in Django
- ✅ Uses Turbo Streams for partial DOM updates
- ✅ Handles errors and edge cases gracefully

This pattern can be adapted for any real-time feature: file uploads, data processing, notifications, collaborative editing, live dashboards, and more.