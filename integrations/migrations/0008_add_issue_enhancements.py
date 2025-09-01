# Generated manually for Issue model enhancements

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


def generate_issue_prefix_ids(apps, schema_editor):
    """Generate prefix_id for existing Issue records"""
    Issue = apps.get_model('integrations', 'Issue')
    for issue in Issue.objects.all():
        # Generate a unique prefix_id for existing issues
        issue.prefix_id = f"iss_{uuid.uuid4().hex[:8]}"
        issue.save(update_fields=['prefix_id'])


def reverse_generate_issue_prefix_ids(apps, schema_editor):
    """Reverse operation - remove prefix_ids"""
    pass  # No need to reverse this


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('integrations', '0007_add_validation_models'),
    ]

    operations = [
        # Add prefix_id field with temporary null=True
        migrations.AddField(
            model_name='issue',
            name='prefix_id',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        
        # Add other new fields
        migrations.AddField(
            model_name='issue',
            name='issue_key',
            field=models.CharField(blank=True, db_index=True, help_text='Key for grouping similar issues within account+chart scope', max_length=64),
        ),
        migrations.AddField(
            model_name='issue',
            name='latest_occurrence',
            field=models.JSONField(blank=True, default=dict, help_text='Most recent occurrence details'),
        ),
        migrations.AddField(
            model_name='issue',
            name='occurrence_ids',
            field=models.JSONField(blank=True, default=list, help_text='List of individual occurrence IDs'),
        ),
        migrations.AddField(
            model_name='issue',
            name='resolution_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='issue',
            name='resolved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='issue',
            name='resolved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        
        # Populate prefix_ids for existing records
        migrations.RunPython(generate_issue_prefix_ids, reverse_generate_issue_prefix_ids),
        
        # Make prefix_id non-nullable and unique after populating
        migrations.AlterField(
            model_name='issue',
            name='prefix_id',
            field=models.CharField(max_length=50, unique=True),
        ),
        
        # Add database indexes
        migrations.AddIndex(
            model_name='issue',
            index=models.Index(fields=['integration', 'status', 'category'], name='integrations_integration_status_category_idx'),
        ),
        migrations.AddIndex(
            model_name='issue',
            index=models.Index(fields=['issue_key'], name='integrations_issue_key_idx'),
        ),
        migrations.AddIndex(
            model_name='issue',
            index=models.Index(fields=['integration', 'category', 'status'], name='integrations_integration_category_status_idx'),
        ),
    ]