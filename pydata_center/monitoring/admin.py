from django.contrib import admin
from django.contrib.auth.models import Group
from django.db.models.query import QuerySet
from django.http import HttpRequest

from .models import (Agent, AgentLogEntry, AgentMetric, AgentPingStatus,
                     AlertingChannel, AlertRule, CommandHistory, ServerStatus)


class GroupBaseAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        return request.user.groups.filter(name='Admin').exists()

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request)


@admin.register(CommandHistory)
class CommandHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'type', 'hostname', 'status', 'timestamp', 'notify_on_success'
    )
    list_filter = ('type', 'status', 'hostname')
    search_fields = ('type', 'hostname')
    readonly_fields = (
        'hostname', 'type', 'params', 'result', 'status', 'timestamp'
    )

    fieldsets = (
        (
            'Command Definition',
            {
                'fields': ('type', 'params')
            },
        ),
        (
            'Status and Meta',
            {
                'fields': ('hostname', 'result', 'status', 'timestamp')
            }
        ),
    )


@admin.register(ServerStatus)
class ServerStatusAdmin(GroupBaseAdmin):
    list_display = ('hostname', 'server_name', 'ip', 'uptime', 'timestamp')
    list_filter = ('server_name', )
    search_fields = ('hostname', 'server_name')
    readonly_fields = ('hostname', 'ip', 'uptime', 'server_name', 'timestamp')
    ordering = ('-timestamp', )


@admin.register(AgentMetric)
class AgentMetricAdmin(admin.ModelAdmin):
    list_display = (
        'server_status', 'timestamp', 'cpu', 'ram', 'disk', 'load_avg'
    )
    search_fields = ('server_status__hostname', 'server_status__server_name')
    list_filter = ('server_status__server_name', )
    ordering = ('-timestamp', )
    readonly_fields = ('timestamp', )


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = (
        'metric',
        'operator',
        'threshold',
        'time_window_minutes',
        'frequency',
        'is_active',
        'hostname',
    )
    list_filter = ('metric', 'is_active', 'hostname')
    search_fields = ('metric', 'hostname')
    readonly_fields = ('created_at', )

    ordering = ('-created_at', )

    fieldsets = (
        (
            'Rule Definition',
            {
                'fields': (
                    'metric',
                    'operator',
                    'threshold',
                    'time_window_minutes',
                    'frequency',
                    'hostname',
                )
            },
        ),
        (
            'Status and Meta',
            {
                'fields': ('is_active', 'created_at')
            }
        ),
    )

    actions = ['activate_rules', 'deactivate_rules']

    def activate_rules(self, request: HttpRequest, queryset: QuerySet):
        nrules = queryset.update(is_active=True)
        self.message_user(request, f'{nrules} rule(s) activated.')
    activate_rules.short_description = 'Activate selected alert rules'

    def deactivate_rules(self, request: HttpRequest, queryset: QuerySet):
        nrules = queryset.update(is_active=False)
        self.message_user(request, f'{nrules} rule(s) deactivated.')
    activate_rules.short_description = 'Deactivate selected alert rules'


@admin.register(AlertingChannel)
class AlertingChannelAdmin(admin.ModelAdmin):
    list_display = ('system', 'description', 'enabled', 'created_at')
    list_filter = ('system', 'enabled')
    search_fields = ('description', 'url')
    readonly_fields = ('created_at', 'url')


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')


@admin.register(AgentLogEntry)
class AgentLogEntryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'agent_name', 'level', 'message')
    list_filter = ('level', 'agent_name', 'timestamp')
    search_fields = ('message', 'agent_name')


@admin.register(AgentPingStatus)
class AgentPingStatusAdmin(admin.ModelAdmin):
    list_display = (
        'agent_name', 'ip', 'timestamp', 'uptime', 'status'
    )
    list_filter = ('status', )
    search_fields = ('agent_name', 'ip')
    readonly_fields = ('agent_name', 'ip', 'uptime', 'status', 'timestamp')
    ordering = ('-timestamp', )
