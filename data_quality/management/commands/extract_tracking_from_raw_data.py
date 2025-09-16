"""
Management command to extract tracking category data from existing raw_data fields
in TransactionLineItem records.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from financial_data.models import TransactionLineItem
from connections.services.providers.xero import extract_tracking_categories_from_line_item
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Extract tracking categories from existing raw_data in transaction line items'

    def add_arguments(self, parser):
        parser.add_argument(
            '--connection-id',
            type=str,
            help='Process line items for a specific connection ID',
        )
        parser.add_argument(
            '--transaction-id',
            type=str,
            help='Process line items for a specific transaction ID',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000,
            help='Maximum number of line items to process (default: 1000)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Process all line items, even those that already have tracking data',
        )

    def handle(self, *args, **options):
        # Configure logging
        if options['verbosity'] >= 2:
            logging.basicConfig(level=logging.DEBUG)
        elif options['verbosity'] >= 1:
            logging.basicConfig(level=logging.INFO)

        # Build queryset based on options
        queryset = self.build_queryset(options)

        if not queryset.exists():
            self.stdout.write(
                self.style.WARNING("No line items found matching the criteria")
            )
            return

        total_count = queryset.count()
        limit = options['limit']

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {total_count} line item(s) to process (limit: {limit})"
            )
        )

        # Process line items in batches
        stats = {
            'processed': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }

        line_items = queryset[:limit]

        for line_item in line_items:
            try:
                result = self.process_line_item(line_item, options['dry_run'], options['force'])
                stats[result] += 1
                stats['processed'] += 1

                if options['verbosity'] >= 2:
                    self.stdout.write(f"Line item {line_item.id}: {result}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing line item {line_item.id}: {e}")
                )
                stats['errors'] += 1
                stats['processed'] += 1
                logger.exception(f"Error processing line item {line_item.id}")

        # Print summary
        self.print_summary(stats, options['dry_run'])

    def build_queryset(self, options):
        """Build queryset based on command options"""
        queryset = TransactionLineItem.objects.select_related('transaction', 'transaction__connection')

        if options['connection_id']:
            queryset = queryset.filter(transaction__connection_id=options['connection_id'])

        if options['transaction_id']:
            queryset = queryset.filter(transaction_id=options['transaction_id'])

        # Only process items with raw_data
        queryset = queryset.exclude(raw_data__isnull=True).exclude(raw_data={})

        # Unless forced, skip items that already have tracking data
        if not options['force']:
            queryset = queryset.filter(
                tracking_category_1_id__isnull=True,
                tracking_category_1_name__isnull=True,
                tracking_category_1_option__isnull=True,
                tracking_category_2_id__isnull=True,
                tracking_category_2_name__isnull=True,
                tracking_category_2_option__isnull=True,
            ).filter(
                tracking_category_1_id='',
                tracking_category_1_name='',
                tracking_category_1_option='',
                tracking_category_2_id='',
                tracking_category_2_name='',
                tracking_category_2_option='',
            )

        return queryset.order_by('id')

    def process_line_item(self, line_item, dry_run, force):
        """Process a single line item to extract tracking data"""

        # Check if already has tracking data (unless forced)
        if not force and self.has_tracking_data(line_item):
            return 'skipped'

        # Extract tracking data from raw_data
        tracking_data = extract_tracking_categories_from_line_item(line_item.raw_data)

        # Check if any tracking data was found
        has_tracking_in_raw = any(tracking_data.values())

        if not has_tracking_in_raw:
            return 'skipped'

        if dry_run:
            self.stdout.write(
                f"DRY RUN: Would update line item {line_item.id} with tracking data: {tracking_data}"
            )
            return 'updated'

        # Update the line item with tracking data
        with transaction.atomic():
            for field, value in tracking_data.items():
                setattr(line_item, field, value or '')

            line_item.save(update_fields=list(tracking_data.keys()))

        return 'updated'

    def has_tracking_data(self, line_item):
        """Check if line item already has tracking data"""
        return any([
            line_item.tracking_category_1_id,
            line_item.tracking_category_1_name,
            line_item.tracking_category_1_option,
            line_item.tracking_category_2_id,
            line_item.tracking_category_2_name,
            line_item.tracking_category_2_option,
        ])

    def print_summary(self, stats, is_dry_run):
        """Print processing summary"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.SUCCESS("TRACKING DATA EXTRACTION SUMMARY")
        )
        self.stdout.write("="*60)

        if is_dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))

        self.stdout.write(f"Line items processed: {stats['processed']}")
        self.stdout.write(f"Line items updated: {stats['updated']}")
        self.stdout.write(f"Line items skipped: {stats['skipped']}")
        self.stdout.write(f"Errors encountered: {stats['errors']}")

        if stats['errors'] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  {stats['errors']} line item(s) failed. "
                    "Check logs for details."
                )
            )
        elif stats['updated'] > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully processed {stats['updated']} line items!"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("\n⚠️  No line items were updated.")
            )