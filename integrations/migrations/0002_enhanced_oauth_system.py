# Enhanced OAuth Integration System
from django.db import migrations, models
import django.db.models.deletion
import encrypted_model_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('integrations', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # Step 1: Create new models
        migrations.CreateModel(
            name='IntegrationProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('display_name', models.CharField(max_length=100)),
                ('provider_type', models.CharField(choices=[('xero', 'Xero')], max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('auth_url_template', models.URLField()),
                ('token_url', models.URLField()),
                ('revoke_url', models.URLField(blank=True, null=True)),
                ('scopes_default', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        
        migrations.CreateModel(
            name='IntegrationCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_token', encrypted_model_fields.fields.EncryptedTextField()),
                ('refresh_token', encrypted_model_fields.fields.EncryptedTextField(blank=True, null=True)),
                ('token_type', models.CharField(default='Bearer', max_length=20)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('scopes', models.JSONField(default=list)),
                ('additional_credentials', encrypted_model_fields.fields.EncryptedTextField(default='{}')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_refreshed_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        
        migrations.CreateModel(
            name='IntegrationSync',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sync_type', models.CharField(choices=[('full', 'Full Sync'), ('incremental', 'Incremental Sync'), ('webhook', 'Webhook Triggered')], max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('records_processed', models.PositiveIntegerField(default=0)),
                ('records_success', models.PositiveIntegerField(default=0)),
                ('records_failed', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('error_details', models.JSONField(blank=True, default=dict)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-started_at'],
            },
        ),
        
        # Step 2: Remove old fields from Integration
        migrations.RemoveField(
            model_name='integration',
            name='user',
        ),
        migrations.RemoveField(
            model_name='integration',
            name='integration_type',
        ),
        migrations.RemoveField(
            model_name='integration',
            name='account_name',
        ),
        migrations.RemoveField(
            model_name='integration',
            name='is_active',
        ),
        
        # Step 3: Rename account_id to external_account_id and change its properties
        migrations.RenameField(
            model_name='integration',
            old_name='account_id',
            new_name='external_account_id',
        ),
        migrations.AlterField(
            model_name='integration',
            name='external_account_id',
            field=models.CharField(max_length=255),
        ),
        
        # Step 4: Modify connected_at to allow null values
        migrations.AlterField(
            model_name='integration',
            name='connected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        
        # Step 5: Add new fields to Integration
        migrations.AddField(
            model_name='integration',
            name='account',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='integrations', to='core.account'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='integration',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_integrations', to='auth.user'),
        ),
        migrations.AddField(
            model_name='integration',
            name='provider',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='integrations.integrationprovider'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='integration',
            name='external_account_name',
            field=models.CharField(max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='integration',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending Authorization'), ('active', 'Active'), ('expired', 'Token Expired'), ('revoked', 'Access Revoked'), ('error', 'Error State')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='integration',
            name='last_sync_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='integration',
            name='last_error',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='integration',
            name='config',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='integration',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='integration',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
            preserve_default=False,
        ),
        
        # Step 6: Add relationships to credential and sync models
        migrations.AddField(
            model_name='integrationcredential',
            name='integration',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credentials', to='integrations.integration'),
        ),
        migrations.AddField(
            model_name='integrationsync',
            name='integration',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='syncs', to='integrations.integration'),
        ),
        
        # Step 7: Update meta options and constraints
        migrations.AlterModelOptions(
            name='integration',
            options={'ordering': ['-created_at']},
        ),
        
        # Step 8: Remove the old unique constraint and add the new one
        migrations.AlterUniqueTogether(
            name='integration',
            unique_together=set(),  # Remove existing constraint
        ),
        migrations.AlterUniqueTogether(
            name='integration',
            unique_together={('account', 'provider', 'external_account_id')},
        ),
    ]