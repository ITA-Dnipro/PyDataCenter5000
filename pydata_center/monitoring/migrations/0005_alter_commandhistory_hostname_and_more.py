import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0004_commandhistory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commandhistory',
            name='hostname',
            field=models.CharField(
                db_index=True,
                max_length=100
            ),
        ),
        migrations.AlterField(
            model_name='commandhistory',
            name='result',
            field=models.TextField(
                blank=True,
                null=True
            ),
        ),
        migrations.AlterField(
            model_name='commandhistory',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('done', 'Done'),
                    ('failed', 'Failed')
                ],
                db_index=True,
                default='pending',
                max_length=10
            ),
        ),
        migrations.CreateModel(
            name='AgentMetric',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID'
                    )
                ),
                (
                    'cpu',
                    models.FloatField(
                        blank=True,
                        null=True
                    )
                ),
                (
                    'ram',
                    models.FloatField(
                        blank=True,
                        null=True
                    )
                ),
                (
                    'disk',
                    models.FloatField(
                        blank=True,
                        null=True
                    )
                ),
                (
                    'load_avg',
                    models.FloatField(
                        blank=True,
                        null=True
                    )
                ),
                (
                    'timestamp',
                    models.DateTimeField(
                        auto_now_add=True
                    )
                ),
                (
                    'server_status',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='server_status',
                        to='monitoring.serverstatus'
                    )
                ),
            ],
            options={
                'indexes': [
                    models.Index(
                        fields=['server_status', 'timestamp'],
                        name='monitoring__server__0620a3_idx'
                    ),
                ],
            },
        ),
    ]
