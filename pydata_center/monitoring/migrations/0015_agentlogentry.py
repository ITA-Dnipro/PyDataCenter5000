from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0014_merge_20250620_1523'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentLogEntry',
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
                ('agent_name', models.CharField(max_length=255)),
                ('timestamp', models.DateTimeField()),
                (
                    'level',
                    models.CharField(
                        max_length=10,
                        choices=[
                            ('DEBUG', 'Debug'),
                            ('INFO', 'Info'),
                            ('WARNING', 'Warning'),
                            ('ERROR', 'Error'),
                            ('CRITICAL', 'Critical'),
                        ],
                    ),
                ),
                ('message', models.TextField()),
                ('context', models.JSONField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(
                        fields=['agent_name', 'timestamp'],
                        name='monitoring__agent_n_361e57_idx',
                    )
                ],
            },
        ),
    ]
