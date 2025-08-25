from django.core.management.base import BaseCommand
from integrations.models import IntegrationProvider


class Command(BaseCommand):
    help = 'Set up integration providers (Xero, etc.)'
    
    def handle(self, *args, **options):
        # Create Xero provider
        xero_provider, created = IntegrationProvider.objects.get_or_create(
            name='xero',
            defaults={
                'display_name': 'Xero',
                'provider_type': 'xero',
                'is_active': True,
                'auth_url_template': 'https://login.xero.com/identity/connect/authorize',
                'token_url': 'https://identity.xero.com/connect/token',
                'revoke_url': 'https://identity.xero.com/connect/revocation',
                'scopes_default': ['accounting.transactions', 'accounting.contacts', 'accounting.settings', 'offline_access']
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Xero provider: {xero_provider}'))
        else:
            self.stdout.write(self.style.WARNING(f'Xero provider already exists: {xero_provider}'))
            
        # Update existing provider if needed
        if not created:
            updated = False
            if not xero_provider.is_active:
                xero_provider.is_active = True
                updated = True
            if 'offline_access' not in xero_provider.scopes_default:
                xero_provider.scopes_default.append('offline_access')
                updated = True
            
            if updated:
                xero_provider.save()
                self.stdout.write(self.style.SUCCESS('Updated Xero provider configuration'))
        
        self.stdout.write(self.style.SUCCESS('Provider setup completed!'))