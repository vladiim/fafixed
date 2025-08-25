from django.core.management.base import BaseCommand
from django.utils import timezone
from integrations.models import Integration
from integrations.managers import IntegrationManager
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync transaction data from Xero for active integrations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--integration-id',
            type=int,
            help='Specific integration ID to sync'
        )
        parser.add_argument(
            '--account-id',
            type=int,
            help='Sync all integrations for a specific account'
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Perform full sync (2 years) instead of incremental'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test run without actually syncing'
        )
    
    def handle(self, *args, **options):
        integration_id = options.get('integration_id')
        account_id = options.get('account_id')
        full_sync = options.get('full', False)
        dry_run = options.get('dry_run', False)
        
        sync_type = 'full' if full_sync else 'incremental'
        
        # Get integrations to sync
        if integration_id:
            integrations = Integration.objects.filter(id=integration_id, status='active')
        elif account_id:
            integrations = Integration.objects.filter(account_id=account_id, status='active')
        else:
            # Sync all active Xero integrations
            integrations = Integration.objects.filter(
                provider__name='xero',
                status='active'
            )
        
        if not integrations.exists():
            self.stdout.write(self.style.WARNING('No active integrations found to sync'))
            return
        
        self.stdout.write(f'Found {integrations.count()} integration(s) to sync')
        
        for integration in integrations:
            try:
                self.stdout.write(f'\nSyncing integration {integration.id} ({integration.organization_name})...')
                
                if dry_run:
                    self.stdout.write(self.style.SUCCESS('  [DRY RUN] Would sync transactions'))
                    continue
                
                # Perform the sync
                sync_record = IntegrationManager.sync_integration(integration, sync_type)
                
                if sync_record.status == 'completed':
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Synced {sync_record.records_success} transactions successfully'
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'  ✗ Sync failed: {sync_record.error_message}'
                    ))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error syncing integration {integration.id}: {str(e)}'))
                logger.error(f'Failed to sync integration {integration.id}', exc_info=True)
        
        self.stdout.write(self.style.SUCCESS('\nSync process completed'))