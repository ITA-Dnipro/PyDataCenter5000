import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            'monitoring',
            '0011_remove_alertrule_monitoring__metric_078946_idx_and_more'
        ),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentPingStatus',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('agent_name', models.CharField(max_length=100)),
                ('ip', models.GenericIPAddressField()),
                ('timestamp', models.DateTimeField()),
                (
                    'uptime',
                    models.FloatField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0)
                        ],
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        max_length=20,
                        choices=[
                            ('ok', 'OK'),
                            ('unreachable', 'Unreachable'),
                            ('error', 'Error'),
                        ],
                    ),
                ),
            ],
            options={
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(
                        fields=['agent_name', 'timestamp'],
                        name='monitoring__agent_n_71df12_idx',
                    )
                ],
            },
        ),
    ]
