from django.db import migrations, models
from django.db.models import Max


def initialize_versions(apps, schema_editor):
    Portfolio = apps.get_model('myapp', 'Portfolio')
    Allocation = apps.get_model('myapp', 'TargetAllocation')
    alias = schema_editor.connection.alias
    versions = Allocation.objects.using(alias).values('portfolio_id').annotate(latest=Max('version_number'))
    for row in versions.iterator():
        Portfolio.objects.using(alias).filter(pk=row['portfolio_id']).update(current_allocation_version=row['latest'])


class Migration(migrations.Migration):
    dependencies = [('myapp', '0008_registration_integrity')]
    operations = [
        migrations.AddField('portfolio', 'current_allocation_version',
                            models.PositiveIntegerField(default=0, editable=False)),
        migrations.RunPython(initialize_versions, migrations.RunPython.noop),
    ]
