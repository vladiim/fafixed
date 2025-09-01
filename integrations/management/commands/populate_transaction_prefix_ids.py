from django.core.management.base import BaseCommand
from django.db import models
from integrations.models import TransactionData
import secrets
import string


class Command(BaseCommand):
    help = 'Populate prefix_ids for TransactionData records that are missing them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if prefix_ids already exist',
        )

    def generate_prefix_id(self, prefix='txn', length=8):
        """Generate a unique prefix_id"""
        chars = string.ascii_lowercase + string.digits
        random_string = ''.join(secrets.choice(chars) for _ in range(length))
        return f"{prefix}_{random_string}"

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        self.stdout.write('=== TransactionData Prefix ID Population ===')
        
        # Find all transactions without prefix_id
        if force:
            transactions_without_prefix = TransactionData.objects.all()
            self.stdout.write(self.style.WARNING(f'FORCE MODE: Processing all {transactions_without_prefix.count()} transactions'))
        else:
            transactions_without_prefix = TransactionData.objects.filter(
                models.Q(prefix_id__isnull=True) | models.Q(prefix_id='')
            )
            
        count = transactions_without_prefix.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ All transactions already have prefix_ids'))
            return
            
        self.stdout.write(f'Found {count} transactions without prefix_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: No changes will be made'))
            # Show first 5 transactions that would be updated
            for i, transaction in enumerate(transactions_without_prefix[:5]):
                self.stdout.write(f'  Would update transaction ID {transaction.id}: {transaction.description[:50]}...')
            if count > 5:
                self.stdout.write(f'  ... and {count - 5} more')
            return
            
        # Actually update the transactions
        updated_count = 0
        failed_count = 0
        
        for transaction in transactions_without_prefix:
            try:
                # Generate unique prefix_id
                attempts = 0
                while attempts < 100:  # Safety limit
                    prefix_id = self.generate_prefix_id()
                    if not TransactionData.objects.filter(prefix_id=prefix_id).exists():
                        transaction.prefix_id = prefix_id
                        transaction.save(update_fields=['prefix_id'])
                        updated_count += 1
                        if updated_count % 50 == 0:  # Progress indicator
                            self.stdout.write(f'Updated {updated_count} transactions...')
                        break
                    attempts += 1
                
                if attempts >= 100:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to generate unique prefix_id for transaction {transaction.id}')
                    )
                    failed_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error updating transaction {transaction.id}: {str(e)}')
                )
                failed_count += 1
        
        # Summary
        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Successfully updated {updated_count} transactions with prefix_ids')
            )
        
        if failed_count > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to update {failed_count} transactions')
            )
            
        # Verify final state
        remaining = TransactionData.objects.filter(
            models.Q(prefix_id__isnull=True) | models.Q(prefix_id='')
        ).count()
        
        if remaining == 0:
            self.stdout.write(self.style.SUCCESS('✅ All transactions now have prefix_ids'))
        else:
            self.stdout.write(self.style.ERROR(f'⚠️  {remaining} transactions still missing prefix_ids'))