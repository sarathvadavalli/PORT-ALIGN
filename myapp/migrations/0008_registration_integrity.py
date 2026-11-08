from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Lower


EMAIL_CONSTRAINT = models.UniqueConstraint(fields=['email'], name='uq_auth_user_email')


def initialize(apps, schema_editor):
    alias = schema_editor.connection.alias
    User = apps.get_model('auth', 'User')
    if User.objects.using(alias).annotate(normalized=Lower('email')).values('normalized').annotate(n=Count('pk')).filter(n__gt=1).exists():
        raise RuntimeError('Duplicate account emails must be reconciled before migrating; no accounts were removed.')
    Profile = apps.get_model('myapp', 'InvestorProfile')
    highest = 0
    for identifier in Profile.objects.using(alias).values_list('investor_id', flat=True):
        if identifier.startswith('INV-') and identifier[4:].isdigit():
            highest = max(highest, int(identifier[4:]))
    apps.get_model('myapp', 'InvestorSequence').objects.using(alias).create(pk=1, last_value=highest)
    schema_editor.add_constraint(User, EMAIL_CONSTRAINT)


def reverse(apps, schema_editor):
    schema_editor.remove_constraint(apps.get_model('auth', 'User'), EMAIL_CONSTRAINT)


class Migration(migrations.Migration):
    dependencies = [('myapp', '0007_reconcile_profile_schema'), ('auth', '0012_alter_user_first_name_max_length')]
    operations = [
        migrations.CreateModel(name='InvestorSequence', fields=[
            ('id', models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False, serialize=False)),
            ('last_value', models.PositiveIntegerField(default=0)),
        ]),
        migrations.RunPython(initialize, reverse, atomic=False),
    ]
