from django.core.management.base import BaseCommand
from integrations.models import Issue
import json


class Command(BaseCommand):
    help = 'Debug the issue data structure'

    def add_arguments(self, parser):
        parser.add_argument('issue_prefix_id', type=str, help='Issue prefix ID to debug')

    def handle(self, *args, **options):
        issue_prefix_id = options['issue_prefix_id']
        
        try:
            issue = Issue.objects.get(prefix_id=issue_prefix_id)
            
            self.stdout.write(f"Issue: {issue}")
            self.stdout.write(f"Issue ID: {issue.id}")
            self.stdout.write(f"Issue prefix_id: {issue.prefix_id}")
            self.stdout.write(f"Issue title: {issue.title}")
            
            # Debug the affected_transactions field
            self.stdout.write("\n=== AFFECTED TRANSACTIONS DEBUG ===")
            self.stdout.write(f"Type: {type(issue.affected_transactions)}")
            
            if issue.affected_transactions:
                self.stdout.write(f"Content: {json.dumps(issue.affected_transactions, indent=2, default=str)}")
                
                # Test the conditions
                is_dict = isinstance(issue.affected_transactions, dict)
                has_transactions = 'transactions' in issue.affected_transactions if is_dict else False
                
                self.stdout.write(f"\nCondition checks:")
                self.stdout.write(f"  isinstance(dict): {is_dict}")
                self.stdout.write(f"  'transactions' in data: {has_transactions}")
                
                # Test the new logic
                self.stdout.write(f"\n=== TESTING NEW LOGIC ===")
                transaction_ids = []
                
                if isinstance(issue.affected_transactions, list):
                    self.stdout.write("Processing as list...")
                    for i, item in enumerate(issue.affected_transactions):
                        self.stdout.write(f"  Item {i}: {type(item)}")
                        if isinstance(item, dict) and 'transactions' in item:
                            extracted = [tx['id'] for tx in item['transactions']]
                            transaction_ids.extend(extracted)
                            self.stdout.write(f"    Extracted IDs: {extracted}")
                        elif isinstance(item, (int, str)):
                            transaction_ids.append(item)
                            self.stdout.write(f"    Added simple ID: {item}")
                
                self.stdout.write(f"Final transaction_ids: {transaction_ids}")
                
            else:
                self.stdout.write("affected_transactions is empty/None")
                
        except Issue.DoesNotExist:
            self.stdout.write(f"Issue with prefix_id {issue_prefix_id} not found")
        except Exception as e:
            self.stdout.write(f"Error: {e}")