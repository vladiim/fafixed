# Allow multiple Xero integrations per account
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0002_enhanced_oauth_system'),
    ]

    operations = [
        # Remove the existing unique constraint that prevents multiple integrations
        migrations.AlterUniqueTogether(
            name='integration',
            unique_together=set(),
        ),
        
        # Add a new unique constraint that only applies when external_account_id is not empty
        # This allows multiple pending integrations but prevents duplicate active ones
        migrations.RunSQL(
            "CREATE UNIQUE INDEX integrations_integration_unique_when_external_account_id_not_empty "
            "ON integrations_integration (account_id, provider_id, external_account_id) "
            "WHERE external_account_id != '' AND external_account_id IS NOT NULL;",
            
            reverse_sql="DROP INDEX IF EXISTS integrations_integration_unique_when_external_account_id_not_empty;"
        ),
    ]