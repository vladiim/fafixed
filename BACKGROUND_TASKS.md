# Background Task System

This document describes the background task system for automated Xero data synchronization using Celery.

## Overview

The system implements three main background tasks:
- **Daily Sync**: Pulls yesterday's transactions from all active Xero integrations
- **Token Refresh**: Automatically refreshes expiring OAuth tokens  
- **Cleanup**: Removes expired OAuth state tokens

## Prerequisites

1. **Redis Server**: Used as message broker and result backend
   ```bash
   # Install Redis (macOS)
   brew install redis
   
   # Start Redis
   brew services start redis
   
   # Or run manually
   redis-server
   ```

2. **Dependencies**: Already included in pyproject.toml
   - celery>=5.5.3
   - redis>=5.0.0

## Configuration

Environment variables (add to .env):
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Running Background Tasks

### 1. Start Celery Worker
In one terminal window:
```bash
uv run celery -A fafixed worker --loglevel=info --queues=sync,cleanup,auth
```

### 2. Start Celery Beat Scheduler (for periodic tasks)
In another terminal window:
```bash
uv run celery -A fafixed beat --loglevel=info
```

### 3. Optional: Monitor Tasks (Flower)
```bash
pip install flower
uv run celery -A fafixed flower
```
Then visit http://localhost:5555

## Task Schedule

- **Daily Sync**: Runs every 24 hours (86400 seconds) at midnight
- **Token Refresh**: Runs every 30 minutes (1800 seconds) 
- **OAuth Cleanup**: Runs daily to remove expired state tokens

## Manual Task Execution

### Test Tasks
```bash
# Test all tasks synchronously
uv run python manage.py test_celery

# Test specific task
uv run python manage.py test_celery --task=sync

# Test with actual Celery worker
uv run python manage.py test_celery --async
```

### Sync Commands
```bash
# Manual sync (synchronous)
uv run python manage.py sync_xero

# Manual sync for specific integration
uv run python manage.py sync_xero --integration-id=1

# Full sync (2 years of data)
uv run python manage.py sync_xero --full
```

### Cleanup Commands
```bash
# Clean up old OAuth states
uv run python manage.py cleanup_oauth_states

# Dry run to see what would be deleted
uv run python manage.py cleanup_oauth_states --dry-run
```

## Task Types

### sync_all_integrations
- **Purpose**: Syncs all active Xero integrations
- **Schedule**: Daily at midnight
- **Parameters**: `sync_type` ('daily', 'incremental', 'full')
- **Queue**: sync

### sync_single_integration  
- **Purpose**: Syncs a specific integration
- **Trigger**: Manual via web interface or command
- **Parameters**: `integration_id`, `sync_type`
- **Queue**: sync

### refresh_expiring_tokens
- **Purpose**: Refreshes OAuth tokens expiring within 60 minutes
- **Schedule**: Every 30 minutes
- **Queue**: auth

### cleanup_expired_oauth_states
- **Purpose**: Removes OAuth state tokens older than 24 hours
- **Schedule**: Daily
- **Queue**: cleanup

## Error Handling

- **Automatic Retry**: Tasks auto-retry on failure (max 3 attempts)
- **Exponential Backoff**: Delays increase between retries
- **Error Logging**: All failures logged with full context
- **Partial Failures**: Individual transaction errors don't stop the entire sync

## Monitoring

Check task status:
```bash
# View recent sync records
uv run python manage.py shell
>>> from integrations.models import IntegrationSync
>>> IntegrationSync.objects.order_by('-created_at')[:5]

# View active integrations
>>> from integrations.models import Integration  
>>> Integration.objects.filter(status='active').count()
```

## Production Deployment

For production, consider:
1. **Redis Persistence**: Configure Redis with persistence enabled
2. **Multiple Workers**: Run multiple Celery workers for reliability
3. **Process Management**: Use supervisor or systemd for process management
4. **Monitoring**: Set up alerts for failed tasks
5. **Scaling**: Use separate queues and workers for different task types

## Troubleshooting

### Common Issues

1. **"No active integrations found"**
   - Normal when no Xero integrations are connected
   - Complete OAuth flow to create active integrations

2. **Connection refused to Redis**
   - Ensure Redis server is running
   - Check CELERY_BROKER_URL configuration

3. **Tasks not executing**
   - Verify Celery beat scheduler is running
   - Check worker is consuming from correct queues

4. **Token refresh failures**
   - Check Xero API credentials
   - Verify OAuth scopes include offline_access