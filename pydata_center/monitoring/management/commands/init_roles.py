from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from monitoring.models import CommandHistory, ServerStatus


class Command(BaseCommand):
    help = 'Initialize RBAC roles'

    def handle(self, *args, **kwargs):
        # create groups
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        operator_group, _ = Group.objects.get_or_create(name='Operator')
        viewer_group, _ = Group.objects.get_or_create(name='Viewer')

        # get ContentType
        status_ct = ContentType.objects.get_for_model(ServerStatus)
        command_ct = ContentType.objects.get_for_model(CommandHistory)

        # rights for ServerStatus
        view_status = Permission.objects.get(codename='view_serverstatus')
        add_status = Permission.objects.get(codename='add_serverstatus')
        change_status = Permission.objects.get(codename='change_serverstatus')

        # rights for CommandHistory
        view_cmd = Permission.objects.get(codename='view_commandhistory')
        add_cmd = Permission.objects.get(codename='add_commandhistory')
        change_cmd = Permission.objects.get(codename='change_commandhistory')
        delete_cmd = Permission.objects.get(codename='delete_commandhistory')

        # Admin - all rights
        admin_perms = Permission.objects.filter(
            content_type__in=[status_ct, command_ct]
        )
        admin_group.permissions.set(admin_perms)

        # Operator - partial rights
        operator_group.permissions.set([
            view_status, add_status, change_status,
            view_cmd, add_cmd, change_cmd, delete_cmd
        ])

        # Viewer - only view
        viewer_group.permissions.set([view_status, view_cmd])

        self.stdout.write(
            self.style.SUCCESS('RBAC roles initialized successfully. ')
        )
