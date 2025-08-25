from django.core.management.base import BaseCommand
from integrations.models import OAuthState


class Command(BaseCommand):
    help = 'Clean up expired OAuth state tokens'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Delete states older than this many hours (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
    
    def handle(self, *args, **options):
        hours = options.get('hours', 24)
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            from datetime import timedelta
            from django.utils import timezone
            cutoff_time = timezone.now() - timedelta(hours=hours)
            expired_states = OAuthState.objects.filter(created_at__lt=cutoff_time)
            count = expired_states.count()
            
            self.stdout.write(f'[DRY RUN] Would delete {count} expired OAuth states older than {hours} hours')
        else:
            count = OAuthState.cleanup_expired_states(hours=hours)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully cleaned up {count} expired OAuth states')
            )