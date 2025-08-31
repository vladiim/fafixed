# Django Real-Time Framework

A production-ready framework for building real-time web applications using Django Channels, ActionCable protocol compatibility, Turbo Streams, and Celery background processing.

## 🚀 Features

- **ActionCable Compatible**: Drop-in WebSocket compatibility with Rails ActionCable protocol
- **Turbo Streams Integration**: Seamless real-time DOM updates without page refreshes  
- **Extensible Architecture**: Abstract base classes and mixins for rapid feature development
- **Background Processing**: Celery integration with automatic real-time status broadcasts
- **Production Ready**: Built-in error handling, reconnection logic, and monitoring
- **Zero JavaScript Required**: Stimulus controllers handle all real-time interactions

## 🏗️ Architecture Overview

The framework implements a complete real-time data flow:

```
UI Interaction → Stimulus Controller → Django View → Celery Task 
     ↑                                                    ↓
DOM Update ← ActionCable ← Turbo Stream ← Django Signal ← Model Update
```

**Key Components:**
- **WebSocket Layer**: ActionCable-compatible consumers with group management
- **Signal Broadcasting**: Automatic real-time updates via Django model signals  
- **Stimulus Controllers**: Reusable frontend components for WebSocket connections
- **Validation Engine**: Extensible rule system for business logic processing
- **Background Tasks**: Resilient Celery integration with status tracking

## 🎯 Quick Start

### 1. Core Infrastructure Setup

The framework provides these pre-configured components:

```python
# fafixed/consumers.py - ActionCable compatible WebSocket consumers
class TurboStreamCableConsumer(SyncConsumer):
    """Synchronous WebSocket consumer with ActionCable message format"""
    
# fafixed/routing.py - WebSocket routing with dual consumer support  
websocket_urlpatterns = [
    re_path(r'cable$', TurboStreamCableConsumer.as_asgi()),
]

# fafixed/asgi.py - ASGI application with Channel Layers
application = ProtocolTypeRouter({
    "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
```

### 2. Frontend Real-Time Controller

```javascript
// static/js/controllers/actioncable_controller.js
// Reusable Stimulus controller for any real-time feature

<div data-controller="actioncable" 
     data-actioncable-url-value="{{ WEBSOCKET_URL }}"
     data-actioncable-subscriptions-value='[{"stream_name": "updates_123"}]'>
</div>
```

### 3. Signal-Based Broadcasting

```python  
# Automatic real-time updates via Django signals
@receiver(post_save, sender=YourModel)
def broadcast_update(sender, instance, **kwargs):
    # 1. Render updated template with context
    # 2. Generate Turbo Stream HTML  
    # 3. Broadcast to WebSocket subscribers
    # 4. ActionCable delivers to browser
```

## 📖 Core Concepts

### Extensible Base Classes

**BaseValidationRule** - Abstract interface for business logic:
```python
class CustomValidationRule(BaseValidationRule):
    name = "custom_rule"
    description = "Custom business validation"
    
    def validate(self, integration) -> ValidationResult:
        # Your validation logic here
        return ValidationResult(...)
```

**Stream Naming Patterns** - Organized real-time channels:
```python
f"transaction_updates_{transaction_id}"  # Per-transaction updates
f"integration_updates_{integration_id}"  # Per-integration updates  
f"user_updates_{user_id}"               # Per-user updates
```

**Turbo Frame Architecture** - Targeted DOM updates:
```html
<turbo-frame id="feature-123-status">
  <!-- This frame gets updated via WebSocket -->
</turbo-frame>
```

### Background Processing Integration

```python
@shared_task(bind=True, autoretry_for=(Exception,))
def process_feature(self, item_id, options):
    # 1. Process business logic
    # 2. Update model (triggers signal)  
    # 3. Signal broadcasts via WebSocket
    # 4. Browser receives real-time update
```

## 💡 Building Your First Real-Time Feature

Follow this pattern to add real-time capabilities to any Django application:

### 1. Define Your Real-Time Component

**HTML Template Pattern:**
```html
<!-- Main template with ActionCable connection -->
<div data-controller="actioncable" 
     data-actioncable-url-value="{{ WEBSOCKET_URL }}"
     data-actioncable-subscriptions-value='[{"stream_name": "feature_updates_{{ item.id }}"}]'>
</div>

<!-- Real-time updatable content -->
<turbo-frame id="feature-{{ item.id }}-status">
  {% include 'partials/feature_status.html' %}
</turbo-frame>
```

**Extensibility Points:**
- **Stream Naming**: Use consistent patterns like `{feature}_{scope}_{id}`
- **Multiple Subscriptions**: Array of stream subscriptions for complex features  
- **Scoped Updates**: Turbo Frame IDs enable precise DOM targeting

### 2. Create State-Aware Partials

**Dynamic Status Template:**
```html
<!-- templates/partials/feature_status.html -->
<turbo-frame id="feature-{{ item.id }}-status">
  {% if task_status.running %}
    <!-- Loading State -->
    <div class="status-running">
      <i class="spinner"></i> Processing... {{ task_status.progress }}%
    </div>
  {% elif task_status.completed %}
    <!-- Success State -->  
    <div class="status-success">
      ✓ Completed: {{ task_status.result_summary }}
      <button data-action="click->feature#restart">Run Again</button>
    </div>
  {% elif task_status.failed %}
    <!-- Error State -->
    <div class="status-error">
      ✗ Failed: {{ task_status.error_message }}
      <button data-action="click->feature#retry">Retry</button>
    </div>
  {% else %}
    <!-- Initial State -->
    <form data-controller="feature" data-action="submit->feature#process">
      <button type="submit">Start Processing</button>
    </form>
  {% endif %}
</turbo-frame>
```

**Extensibility Features:**
- **State Management**: Built-in handling for running/completed/failed states
- **Progress Updates**: Real-time progress reporting during task execution
- **Error Recovery**: Automatic retry mechanisms with user feedback
- **Custom Actions**: Extensible button actions via Stimulus controllers

### 3. Build Extensible Stimulus Controllers

**Feature Controller Pattern:**
```javascript
// static/js/controllers/feature_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { 
    itemId: Number,
    streamName: String,
    endpoints: Object 
  }
  
  async process(event) {
    event.preventDefault()
    
    try {
      // Immediate UI feedback
      this.setProcessingState()
      
      // Submit to Django view
      const response = await fetch(this.endpoints.processUrl, {
        method: 'POST',
        body: new FormData(event.target),
        headers: { 'X-CSRFToken': this.csrfToken }
      })
      
      // Handle Turbo Stream response
      if (response.headers.get('Content-Type')?.includes('turbo-stream')) {
        const html = await response.text()
        Turbo.renderStreamMessage(html)
      }
      
    } catch (error) {
      this.setErrorState(error.message)
    }
  }
  
  setProcessingState() {
    // Override in subclasses for custom loading states
    this.element.querySelector('button').disabled = true
  }
  
  setErrorState(message) {
    // Override in subclasses for custom error handling  
    console.error('Processing failed:', message)
  }
}
```

**Extensibility Benefits:**
- **Configuration-Driven**: Use `data-{controller}-{value}` for feature-specific settings
- **Method Override**: Extend base controller for custom business logic
- **Event Integration**: Built-in Turbo Stream and ActionCable compatibility
- **Error Handling**: Standardized error states with custom override points

### 4. Django Views with Real-Time Response

**Base Real-Time View Pattern:**
```python
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from turbo_helper import turbo_stream
from .tasks import process_feature_task
from .models import FeatureItem, TaskStatus

class RealTimeViewMixin:
    """Mixin for views that trigger real-time updates"""
    
    def create_turbo_stream_response(self, frame_id, template, context):
        """Generate Turbo Stream response for immediate UI feedback"""
        return turbo_stream.turbo_stream(
            turbo_stream.replace(frame_id, template=template, context=context),
            content_type="text/vnd.turbo-stream.html"
        )
    
    def start_background_task(self, task_func, **task_kwargs):
        """Start Celery task and create status tracking"""
        task_result = task_func.delay(**task_kwargs)
        
        # Create status record for UI tracking
        TaskStatus.objects.create(
            task_id=task_result.id,
            status='running',
            **task_kwargs
        )
        
        return task_result

@login_required  
def process_feature(request, item_id):
    """Generic real-time processing endpoint"""
    item = get_object_or_404(FeatureItem, id=item_id, user=request.user)
    mixin = RealTimeViewMixin()
    
    if request.method == 'POST':
        # Extract processing parameters
        feature_type = request.POST.get('feature_type', 'default')
        options = request.POST.getlist('options', [])
        
        # Start background task with status tracking
        task_result = mixin.start_background_task(
            process_feature_task,
            item_id=item_id,
            feature_type=feature_type,
            options=options,
            user_id=request.user.id
        )
        
        # Return immediate loading state via Turbo Stream
        return mixin.create_turbo_stream_response(
            frame_id=f"feature-{item_id}-status",
            template="partials/feature_status.html",
            context={
                'item': item,
                'task_status': {'running': True, 'task_id': task_result.id}
            }
        )
```

**Extensibility Features:**
- **Mixin Architecture**: Reusable real-time functionality across views
- **Generic Task Starter**: Standard pattern for background task initialization  
- **Status Tracking**: Built-in task status management for UI updates
- **Template Flexibility**: Configurable Turbo Stream responses

### 5. Extensible Background Tasks

**Base Task Pattern:**
```python
from celery import shared_task
from abc import ABC, abstractmethod
from .models import TaskStatus, ProcessingResult

class BaseRealTimeTask(ABC):
    """Abstract base class for real-time processing tasks"""
    
    @abstractmethod
    def process_item(self, item, options):
        """Override this method with your business logic"""
        pass
    
    def update_progress(self, task_id, progress, message=""):
        """Send progress updates during processing"""
        TaskStatus.objects.filter(task_id=task_id).update(
            progress=progress,
            status_message=message
        )
        # Signal will broadcast progress update to UI

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3})
def process_feature_task(self, item_id, feature_type, options, user_id):
    """Extensible task processor with built-in error handling and progress tracking"""
    
    # Get the appropriate processor class
    processor_class = get_processor_for_type(feature_type)
    processor = processor_class()
    
    try:
        # Initialize status tracking
        TaskStatus.objects.filter(task_id=self.request.id).update(
            status='running',
            progress=0,
            started_at=timezone.now()
        )
        
        # Process with progress updates
        item = get_feature_item(item_id, user_id)
        
        for step, total_steps in processor.get_processing_steps(item, options):
            result = processor.process_step(step, item, options)
            
            # Update progress in real-time
            progress = (step + 1) / total_steps * 100
            processor.update_progress(self.request.id, progress, f"Step {step+1} completed")
        
        # Mark as completed (triggers signal -> broadcasts final update)
        final_result = processor.finalize_result(item, options)
        TaskStatus.objects.filter(task_id=self.request.id).update(
            status='completed',
            progress=100,
            result_data=final_result,
            completed_at=timezone.now()
        )
        
        return final_result
        
    except Exception as e:
        # Automatic error handling with real-time notification
        TaskStatus.objects.filter(task_id=self.request.id).update(
            status='failed',
            error_message=str(e),
            completed_at=timezone.now()
        )
        raise  # Celery handles retry logic

def get_processor_for_type(feature_type):
    """Factory pattern for extensible task processors"""
    processors = {
        'validation': ValidationProcessor,
        'import': ImportProcessor,
        'export': ExportProcessor,
        # Add your custom processors here
    }
    return processors.get(feature_type, DefaultProcessor)
```

**Extensibility Features:**
- **Abstract Base Class**: Standard interface for all background processors
- **Progress Tracking**: Built-in real-time progress updates during task execution
- **Factory Pattern**: Easy registration of new task types
- **Error Recovery**: Automatic retry with status broadcasting
- **Result Standardization**: Consistent output format for UI consumption

### 6. Signal-Based Broadcasting System

**Generic Broadcasting Pattern:**
```python
from django.db.models.signals import post_save
from django.dispatch import receiver  
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.template.loader import render_to_string

class RealTimeBroadcaster:
    """Reusable broadcaster for any model changes"""
    
    @staticmethod
    def broadcast_turbo_stream(stream_name, action, target, template, context):
        """Generic Turbo Stream broadcaster"""
        try:
            # Render template with context
            template_html = render_to_string(template, context)
            
            # Generate Turbo Stream HTML
            turbo_stream_html = f"""
            <turbo-stream action="{action}" target="{target}">
                <template>{template_html}</template>
            </turbo-stream>
            """
            
            # Broadcast via WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                stream_name,
                {'type': 'turbo_stream_message', 'message': turbo_stream_html}
            )
            
            return True
        except Exception as e:
            logger.error(f"Broadcasting failed: {e}", exc_info=True)
            return False

@receiver(post_save, sender=TaskStatus)
def broadcast_status_update(sender, instance, **kwargs):
    """Automatic real-time status broadcasting"""
    
    # Determine what to broadcast based on status
    broadcast_config = {
        'running': {
            'template': 'partials/progress_status.html',
            'include_progress': True
        },
        'completed': {
            'template': 'partials/completed_status.html', 
            'include_results': True
        },
        'failed': {
            'template': 'partials/error_status.html',
            'include_error': True
        }
    }
    
    config = broadcast_config.get(instance.status)
    if not config:
        return
        
    # Broadcast to relevant streams
    stream_patterns = [
        f"feature_updates_{instance.item_id}",
        f"user_updates_{instance.user_id}",  # Optional: notify user across features
    ]
    
    context = {
        'item': instance.item,
        'task_status': instance,
        **{k: v for k, v in config.items() if k.startswith('include_')}
    }
    
    broadcaster = RealTimeBroadcaster()
    for stream_name in stream_patterns:
        broadcaster.broadcast_turbo_stream(
            stream_name=stream_name,
            action="replace", 
            target=f"feature-{instance.item_id}-status",
            template=config['template'],
            context=context
        )
```

**Extensibility Benefits:**
- **Generic Broadcaster**: Reusable for any model changes requiring real-time updates
- **Multi-Stream Support**: Broadcast to multiple WebSocket groups simultaneously  
- **Template Configuration**: Different templates for different status states
- **Context Injection**: Flexible context data for template rendering
- **Error Resilience**: Automatic error handling with logging

## 🔧 Production Configuration

### Required Settings

**Django Settings:**
```python
# settings.py
INSTALLED_APPS = [
    'daphne',  # ASGI server
    'channels',
    'your_app',
]

ASGI_APPLICATION = 'your_project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}

# WebSocket URL Configuration (NEW)
# Automatically switches between ws:// and wss:// based on environment
if DEBUG:
    WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', 'ws://localhost:8000/cable')
else:
    # In production, use wss:// and the actual domain
    WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', f'wss://{ALLOWED_HOSTS[0]}/cable')

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
```

**Context Processor Setup:**
```python
# core/context_processors.py
from django.conf import settings

def websocket_config(request):
    """Make WebSocket URL available in all templates"""
    return {
        'WEBSOCKET_URL': settings.WEBSOCKET_URL,
    }

# settings.py - Add to context processors
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            # ... other processors
            'core.context_processors.websocket_config',
        ],
    },
}]
```

**Environment Variables:**
```bash
# .env for development
WEBSOCKET_URL=ws://localhost:8000/cable

# .env for production
WEBSOCKET_URL=wss://your-domain.com/cable
```

**Process Management:**
```bash
# Start Django with WebSocket support
daphne -p 8000 your_project.asgi:application

# Start Celery workers
celery -A your_project worker --loglevel=info

# Start Celery monitoring (optional)
celery -A your_project flower
```

## 🚀 Advanced Patterns

### Multi-User Broadcasting
```python
# Broadcast to multiple subscriber groups
stream_patterns = [
    f"item_updates_{item_id}",           # Item-specific updates
    f"user_updates_{user_id}",           # User-specific notifications  
    f"team_updates_{team_id}",           # Team-wide notifications
    f"global_updates",                   # System-wide announcements
]

for pattern in stream_patterns:
    broadcaster.broadcast_turbo_stream(pattern, action, target, template, context)
```

### Real-Time Progress Tracking
```python
class ProgressTracker:
    """Real-time progress updates during task execution"""
    
    def __init__(self, task_id, total_steps):
        self.task_id = task_id
        self.total_steps = total_steps
        self.current_step = 0
    
    def update_step(self, message=""):
        self.current_step += 1
        progress = (self.current_step / self.total_steps) * 100
        
        # Broadcast progress update immediately
        TaskStatus.objects.filter(task_id=self.task_id).update(
            progress=progress,
            status_message=message
        )
        # Signal automatically broadcasts to UI

@shared_task(bind=True)
def long_running_task(self, item_id, steps):
    tracker = ProgressTracker(self.request.id, len(steps))
    
    for step in steps:
        result = process_step(step)
        tracker.update_step(f"Completed: {step}")
```

### Custom Validation Rules
```python
class CustomBusinessRule(BaseValidationRule):
    name = "custom_business_logic"
    description = "Validates custom business requirements"
    
    def validate(self, integration) -> ValidationResult:
        # Your custom validation logic
        issues = []
        
        if not self.meets_business_criteria(integration):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.HIGH,
                message="Business criteria not met",
                suggested_fix="Review integration configuration"
            ))
        
        return ValidationResult(
            rule_name=self.name,
            passed=len(issues) == 0,
            issues=issues
        )

# Register your custom rule
VALIDATION_RULES = [
    DuplicateDetectionRule,
    CustomBusinessRule,  # Your custom rule
    # Add more rules here
]
```

## 🔍 Monitoring & Debugging

### Built-in Debugging Tools

**ActionCable Connection Monitor:**
```javascript
// Add to your ActionCable controller
debug() {
  console.log('WebSocket State:', this.cable.connection.state)
  console.log('Active Subscriptions:', this.subscriptions.length)
  this.subscriptions.forEach(sub => {
    console.log(`Stream: ${sub.stream_name}, State: ${sub.state}`)
  })
}
```

**Task Status Dashboard:**
```python
# Add monitoring endpoint
def task_status_dashboard(request):
    """Real-time task monitoring dashboard"""
    active_tasks = TaskStatus.objects.filter(status='running')
    recent_completions = TaskStatus.objects.filter(
        status__in=['completed', 'failed'],
        completed_at__gte=timezone.now() - timedelta(hours=1)
    )
    
    return render(request, 'admin/task_dashboard.html', {
        'active_tasks': active_tasks,
        'recent_completions': recent_completions,
    })
```

### Production Monitoring

**Health Checks:**
```python
# Add to your health check endpoint
def websocket_health_check():
    """Verify WebSocket infrastructure is working"""
    try:
        channel_layer = get_channel_layer()
        # Test basic channel layer functionality
        async_to_sync(channel_layer.group_send)(
            'health_check',
            {'type': 'test_message', 'message': 'ping'}
        )
        return True
    except Exception:
        return False
```

## 📚 API Reference

### Core Classes

**BaseRealTimeTask** - Abstract base for background processors
- `process_item(item, options)` - Override with business logic
- `update_progress(task_id, progress, message)` - Send real-time progress updates
- `get_processing_steps(item, options)` - Define processing workflow

**RealTimeBroadcaster** - Signal-based broadcasting system  
- `broadcast_turbo_stream(stream, action, target, template, context)` - Send real-time updates
- Automatic error handling and retry logic
- Multi-stream broadcasting support

**RealTimeViewMixin** - View helpers for real-time endpoints
- `create_turbo_stream_response(frame_id, template, context)` - Generate Turbo Stream responses  
- `start_background_task(task_func, **kwargs)` - Launch Celery tasks with status tracking

### Stream Naming Conventions

```python
# Recommended stream naming patterns
f"item_updates_{item_id}"           # Item-specific real-time updates
f"user_updates_{user_id}"           # User notification streams  
f"team_updates_{team_id}"           # Team collaboration streams
f"feature_updates_{feature}_{id}"   # Feature-specific streams
f"global_updates"                   # System-wide notifications
```

## 🎉 What You've Built

**A Production-Ready Real-Time Framework With:**

✅ **ActionCable Compatibility** - Drop-in Rails ActionCable protocol support  
✅ **Zero-JavaScript Architecture** - Stimulus handles all real-time interactions  
✅ **Extensible Base Classes** - Abstract interfaces for rapid feature development  
✅ **Background Processing** - Resilient Celery integration with real-time status  
✅ **Signal Broadcasting** - Automatic real-time updates via Django model signals  
✅ **Production Ready** - Built-in monitoring, error handling, and scaling patterns  

**Perfect For Building:**
- Live dashboards and monitoring systems
- Real-time collaboration features  
- Background data processing with progress tracking
- File upload/processing workflows
- Notification and messaging systems
- Live validation and form feedback
- Multi-user interactive applications

## 🔗 Next Steps

1. **Extend Validation Rules** - Add custom business logic using `BaseValidationRule`
2. **Build Custom Processors** - Create domain-specific task processors  
3. **Add Team Features** - Use multi-user broadcasting patterns
4. **Scale for Production** - Implement Redis clustering and monitoring
5. **Monitor Performance** - Add metrics for WebSocket connections and task processing

**Happy Building!** 🚀

---

*This framework powers real-time features in production Django applications. Contribute improvements and share your extensions with the community.*