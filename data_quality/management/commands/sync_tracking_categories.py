"""
Management command to sync tracking categories from Xero for all or specific connections.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from connections.models import Connection
from data_quality.services.xero_sync import XeroTrackingSyncService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync tracking categories from Xero for connections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--connection-id',
            type=str,
            help='Sync tracking categories for a specific connection ID',
        )
        parser.add_argument(
            '--account-id',
            type=int,
            help='Sync tracking categories for all connections under this account ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync tracking categories for all active connections',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes',
        )

    def handle(self, *args, **options):
        # Configure logging
        if options['verbosity'] >= 2:
            logging.basicConfig(level=logging.DEBUG)
        elif options['verbosity'] >= 1:
            logging.basicConfig(level=logging.INFO)

        # Determine which connections to sync
        connections = self.get_connections(options)

        if not connections:
            raise CommandError("No connections found matching the criteria")

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {connections.count()} connection(s) to sync tracking categories for"
            )
        )

        # Sync tracking categories for each connection
        total_stats = {
            'connections_processed': 0,
            'connections_successful': 0,
            'connections_failed': 0,
            'total_categories_synced': 0,
            'total_options_synced': 0,
        }

        for connection in connections:
            try:
                self.stdout.write(f"\nSyncing tracking categories for: {connection.organization_name}")

                if options['dry_run']:
                    self.stdout.write(
                        self.style.WARNING(f"DRY RUN: Would sync tracking categories for {connection}")
                    )
                    total_stats['connections_processed'] += 1
                    continue

                # Perform sync
                with transaction.atomic():
                    sync_service = XeroTrackingSyncService(connection)
                    result = sync_service.sync_tracking_categories()

                if result['success']:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Successfully synced {result['categories_synced']} categories "
                            f"and {result['options_synced']} options"
                        )
                    )
                    total_stats['connections_successful'] += 1
                    total_stats['total_categories_synced'] += result['categories_synced']
                    total_stats['total_options_synced'] += result['options_synced']
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Failed to sync tracking categories")
                    )
                    total_stats['connections_failed'] += 1

                total_stats['connections_processed'] += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error syncing {connection}: {e}")
                )
                total_stats['connections_failed'] += 1
                total_stats['connections_processed'] += 1
                logger.exception(f"Error syncing tracking categories for connection {connection.id}")

        # Print summary
        self.print_summary(total_stats, options['dry_run'])

    def get_connections(self, options):
        """Get connections based on command options"""
        if options['connection_id']:
            try:
                connection = Connection.objects.get(id=options['connection_id'], status='active')
                return Connection.objects.filter(id=connection.id)
            except Connection.DoesNotExist:
                raise CommandError(f"Connection with ID {options['connection_id']} not found or not active")

        elif options['account_id']:
            connections = Connection.objects.filter(
                account_id=options['account_id'],
                status='active',
                provider__provider_type='xero'
            )
            if not connections.exists():
                raise CommandError(f"No active Xero connections found for account ID {options['account_id']}")
            return connections

        elif options['all']:
            return Connection.objects.filter(
                status='active',
                provider__provider_type='xero'
            )

        else:
            raise CommandError(
                "You must specify one of: --connection-id, --account-id, or --all"
            )

    def print_summary(self, stats, is_dry_run):
        """Print sync summary"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.SUCCESS("TRACKING CATEGORIES SYNC SUMMARY")
        )
        self.stdout.write("="*60)

        if is_dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))

        self.stdout.write(f"Connections processed: {stats['connections_processed']}")
        self.stdout.write(f"Successful syncs: {stats['connections_successful']}")
        self.stdout.write(f"Failed syncs: {stats['connections_failed']}")

        if not is_dry_run:
            self.stdout.write(f"Total categories synced: {stats['total_categories_synced']}")
            self.stdout.write(f"Total options synced: {stats['total_options_synced']}")

        if stats['connections_failed'] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  {stats['connections_failed']} connection(s) failed. "
                    "Check logs for details."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ All connections synced successfully!")
            )