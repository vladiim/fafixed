from django.core.management.base import BaseCommand
from integrations.tasks import sync_all_integrations, cleanup_expired_oauth_states, refresh_expiring_tokens


class Command(BaseCommand):
    help = 'Test Celery background tasks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            choices=['sync', 'cleanup', 'refresh', 'all'],
            default='all',
            help='Which task to test'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run tasks asynchronously (requires Celery worker)'
        )
    
    def handle(self, *args, **options):
        task_type = options.get('task')
        run_async = options.get('async', False)
        
        if run_async:
            self.stdout.write('Running tasks asynchronously (requires Celery worker)...')
        else:
            self.stdout.write('Running tasks synchronously...')
        
        if task_type in ['sync', 'all']:
            self.stdout.write('\n--- Testing Sync Task ---')
            if run_async:
                result = sync_all_integrations.delay(sync_type='daily')
                self.stdout.write(f'Sync task started with ID: {result.id}')
            else:
                result = sync_all_integrations(sync_type='daily')
                self.stdout.write(f'Sync result: {result}')
        
        if task_type in ['cleanup', 'all']:
            self.stdout.write('\n--- Testing Cleanup Task ---')
            if run_async:
                result = cleanup_expired_oauth_states.delay()
                self.stdout.write(f'Cleanup task started with ID: {result.id}')
            else:
                result = cleanup_expired_oauth_states()
                self.stdout.write(f'Cleanup result: {result}')
        
        if task_type in ['refresh', 'all']:
            self.stdout.write('\n--- Testing Token Refresh Task ---')
            if run_async:
                result = refresh_expiring_tokens.delay()
                self.stdout.write(f'Token refresh task started with ID: {result.id}')
            else:
                result = refresh_expiring_tokens()
                self.stdout.write(f'Token refresh result: {result}')
        
        self.stdout.write(self.style.SUCCESS('\nTask testing completed!'))