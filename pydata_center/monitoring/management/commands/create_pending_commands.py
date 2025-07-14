from django.core.management.base import BaseCommand
from monitoring.models import CommandHistory


class Command(BaseCommand):
    """
    Bulk-create pending CommandHistory entries for load-testing or development.

    Usage:
      python manage.py create_pending_commands
      --host agent-0001 [--count 500]
      [--shell "echo hi"] [--dry-run] [--batch-size 5000]
    """
    help = (
        'Bulk-create pending commands for one or more hostnames. '
        'Supports batching, dry-run, custom type, and optional batch ID.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--host', '-H', dest='hostname', required=True,
            help='Hostname for which to generate commands'
        )
        parser.add_argument(
            '--count', '-n', dest='count', type=int, default=100,
            help='Number of pending commands to create (must be > 0)'
        )
        parser.add_argument(
            '--shell', dest='shell_cmd', default='echo hello',
            help='Shell snippet to include in each command’s params'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print a sample of commands '
                 'without inserting into the database'
        )
        parser.add_argument(
            '--type', dest='cmd_type', default='linux',
            help='Value to set on the CommandHistory.type field'
        )
        parser.add_argument(
            '--batch-size', dest='batch_size', type=int, default=5000,
            help='Batch size for bulk inserts (must be >= 1; default: 5000)'
        )

    def handle(self, *args, **options):
        """
        Main entry point for the command.
        - Validates inputs
        - Builds the list of CommandHistory instances
        - Optionally prints a dry-run sample
        - Inserts in batches for efficiency
        """
        hostname = options['hostname']
        count = options['count']
        shell_cmd = options['shell_cmd']
        dry_run = options['dry_run']
        cmd_type = options['cmd_type']
        batch_size = options['batch_size']

        # Validate inputs
        if count < 1:
            self.stderr.write(self.style.ERROR(
                f'--count must be a positive integer, got {count}'
            ))
            return

        if batch_size < 1:
            self.stderr.write(self.style.ERROR(
                f'--batch-size must be at least 1, got {batch_size}'
            ))
            return

        # Build CommandHistory instances
        bulk = [
            CommandHistory(
                hostname=hostname,
                type=cmd_type,
                params={'shell': shell_cmd},
                status='pending',
            )
            for _ in range(count)
        ]

        # Dry-run: show a sample and exit
        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Dry run: previewing first 5 commands'
            ))
            for cmd in bulk[:5]:
                self.stdout.write(f'  {cmd}')
            remaining = count - len(bulk[:5])
            if remaining > 0:
                self.stdout.write(f'  ... and {remaining} more')
            return

        # Bulk insert in batches
        for i in range(0, count, batch_size):
            batch = bulk[i:i + batch_size]
            CommandHistory.objects.bulk_create(batch, batch_size=batch_size)

        # Success message with pluralization
        noun = 'command' if count == 1 else 'commands'
        self.stdout.write(self.style.SUCCESS(
            f'Created {count} pending {noun} for host {hostname}'
        ))
