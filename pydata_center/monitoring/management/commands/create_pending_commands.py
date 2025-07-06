from django.core.management.base import BaseCommand
from monitoring.models import CommandHistory


class Command(BaseCommand):
    help = (
        'Bulk-create pending commands for one or more hostnames. '
        'Usage: ./manage.py create_pending_commands '
        '--host agent-0001 --count 500'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--host', '-H', dest='hostname', required=True,
            help='Hostname for which to generate commands'
        )
        parser.add_argument(
            '--count', '-n', dest='count', type=int, default=100,
            help='Number of pending commands to create'
        )
        parser.add_argument(
            '--shell', dest='shell_cmd', default='echo hello',
            help='Shell snippet to include in each command\'s params'
        )

    def handle(self, *args, **options):
        hostname = options['hostname']
        count = options['count']
        shell_cmd = options['shell_cmd']

        bulk = []
        for i in range(count):
            bulk.append(
                CommandHistory(
                    hostname=hostname,
                    type='linux',
                    params={'shell': shell_cmd},
                    status='pending',
                )
            )
        CommandHistory.objects.bulk_create(bulk)
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {count} pending commands for host {hostname}'
            )
        )
