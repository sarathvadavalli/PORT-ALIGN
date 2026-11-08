"""Reconcile the recorded state with the existing manually updated profile table.

Fresh databases still have legacy columns. Copy their account data before
removing them; already updated installations retain their phone/risk values.
"""
from django.db import migrations, models
from phonenumber_field.modelfields import PhoneNumberField


def reconcile(apps, schema_editor):
    Profile = apps.get_model('myapp', 'InvestorProfile')
    User = apps.get_model('auth', 'User')
    alias = schema_editor.connection.alias
    with schema_editor.connection.cursor() as cursor:
        columns = {col.name for col in schema_editor.connection.introspection.get_table_description(cursor, Profile._meta.db_table)}
    if {'full_name', 'email', 'created_at'} <= columns:
        for profile in Profile.objects.using(alias).all().iterator():
            user = User.objects.using(alias).get(pk=profile.user_id)
            first, _, last = profile.full_name.partition(' ')
            changed = []
            for name, value in [('first_name', first), ('last_name', last), ('email', profile.email)]:
                if not getattr(user, name):
                    setattr(user, name, value)
                    changed.append(name)
                elif value and getattr(user, name) != value:
                    raise RuntimeError('Legacy profile account data conflicts; reconcile before migrating.')
            # Retain the original account creation timestamp.
            user.date_joined = min(user.date_joined, profile.created_at)
            user.save(using=alias, update_fields=changed + ['date_joined'])
    for name in ('full_name', 'email', 'created_at'):
        if name in columns:
            schema_editor.remove_field(Profile, Profile._meta.get_field(name))
    for name, field in [('phno', PhoneNumberField(null=True, blank=True, region='IN', max_length=128)),
                        ('risk_profile', models.CharField(max_length=10, choices=[('LOW', 'Low Risk'), ('MODERATE', 'Moderate Risk'), ('HIGH', 'High Risk')], default='MODERATE'))]:
        if name not in columns:
            field.set_attributes_from_name(name)
            schema_editor.add_field(Profile, field)


class Migration(migrations.Migration):
    dependencies = [('myapp', '0006_remove_investorprofile_created_at_and_more')]
    operations = [migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RunPython(reconcile)],
        state_operations=[
            migrations.RemoveField('investorprofile', 'full_name'),
            migrations.RemoveField('investorprofile', 'email'),
            migrations.RemoveField('investorprofile', 'created_at'),
            migrations.AddField('investorprofile', 'phno', PhoneNumberField(null=True, blank=True, region='IN', max_length=128)),
            migrations.AddField('investorprofile', 'risk_profile', models.CharField(max_length=10, choices=[('LOW', 'Low Risk'), ('MODERATE', 'Moderate Risk'), ('HIGH', 'High Risk')], default='MODERATE')),
        ],
    )]
