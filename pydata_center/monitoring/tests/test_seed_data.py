import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from monitoring.models import AgentMetric, ServerStatus


class Command(BaseCommand):
    """
    Django management command to seed the database with test data.
    """
    def add_arguments(self, parser):
        """
        Define command-line arguments for this command.
        """
        parser.add_argument(
            '--servers', type=int, default=3,
            help='Number of test servers to create or update'
        )
        parser.add_argument(
            '--points', type=int, default=20,
            help='Number of metric points to generate per server'
        )
        parser.add_argument(
            '--interval', type=int, default=60,
            help='Seconds between metric points'
        )

    def handle(self, *args, **options):
        """
        Entry point for the command execution.
        """
        num_servers = options['servers']
        points = options['points']
        interval = options['interval']

        now = timezone.now()
        start = now - timedelta(seconds=points * interval)

        servers = []
        for i in range(num_servers):
            hostname = f'dev-server-{i}'
            server_name = f'dev{i}'
            srv, created = ServerStatus.objects.get_or_create(
                hostname=hostname,
                defaults={
                    'ip': f'10.0.0.{i+1}',
                    'uptime': 0.0,
                    'timestamp': start,
                    'os': 'Linux',
                    'server_name': server_name,
                    'healthy': True,
                }
            )
            servers.append(srv)

        for point_index in range(points):
            timestamp = start + timedelta(seconds=point_index * interval)
            for srv in servers:
                cpu_value = max(0.0, min(100.0, random.gauss(50, 15)))
                ram_value = max(0.0, random.gauss(30, 5))
                disk_value = max(0.0, random.gauss(40, 10))
                load_value = max(0.0, random.gauss(1.0, 0.3))
                nginx_failures = random.randint(0, 1)
                uptime_value = max(0.0, srv.uptime + random.random())

                AgentMetric.objects.create(
                    server_status=srv,
                    timestamp=timestamp,
                    cpu=cpu_value,
                    ram=ram_value,
                    disk=disk_value,
                    load_avg=load_value,
                    nginx_down_count=nginx_failures,
                    uptime=uptime_value,
                )
                srv.timestamp = timestamp
                srv.save(update_fields=['timestamp'])

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {num_servers} servers with {points} points each.'
        ))
