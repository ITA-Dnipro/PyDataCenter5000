import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from monitoring.models import AgentMetric, ServerStatus


class Command(BaseCommand):
    help = 'Seed the database with test ServerStatus and AgentMetric data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--servers', type=int, default=3,
            help='Number of test servers to create'
        )
        parser.add_argument(
            '--points', type=int, default=20,
            help='Number of metric points per server'
        )
        parser.add_argument(
            '--interval', type=int, default=60,
            help='Seconds between metric points'
        )

    def handle(self, *args, **options):
        num_servers = options['servers']
        points = options['points']
        interval = options['interval']

        now = timezone.now()
        start = now - timedelta(seconds=points * interval)

        servers = []
        for i in range(num_servers):
            srv, created = ServerStatus.objects.get_or_create(
                hostname=f'dev-server-{i}',
                defaults={
                    'ip': f'10.0.0.{i+1}',
                    'uptime': 0.0,
                    'timestamp': start,
                    'os': 'Linux',
                    'server_name': f'dev{i}',
                    'healthy': True,
                }
            )
            servers.append(srv)

        for j in range(points):
            t = start + timedelta(seconds=j * interval)
            for srv in servers:
                cpu = max(0.0, min(100.0, random.gauss(50, 15)))
                ram = max(0.0, random.gauss(30, 5))
                disk = max(0.0, random.gauss(40, 10))
                load = max(0.0, random.gauss(1.0, 0.3))
                nginx = random.randint(0, 1)
                up = max(0.0, srv.uptime + random.random())

                AgentMetric.objects.create(
                    server_status=srv,
                    timestamp=t,
                    cpu=cpu,
                    ram=ram,
                    disk=disk,
                    load_avg=load,
                    nginx_down_count=nginx,
                    uptime=up,
                )
                srv.timestamp = t
                srv.save(update_fields=['timestamp'])

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {num_servers} servers with {points} points each.'
        ))
