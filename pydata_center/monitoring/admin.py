from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest

from .models import (AgentMetric, AgentPingStatus, AlertRule, CommandHistory,
                     ServerStatus)


@admin.register(CommandHistory)
class CommandHistoryAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'status', 'timestamp')
    list_filter = ('status', 'hostname')
    search_fields = ('hostname', 'command')
    readonly_fields = ('hostname', 'command', 'result', 'status', 'timestamp')


@admin.register(ServerStatus)
class ServerStatusAdmin(admin.ModelAdmin):
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


@admin.register(AgentPingStatus)
class AgentPingStatusAdmin(admin.ModelAdmin):
    list_display = (
        'agent_name', 'ip', 'timestamp', 'uptime', 'status'
    )
    list_filter = ('status', )
    search_fields = ('agent_name', 'ip')
    readonly_fields = ('agent_name', 'ip', 'uptime', 'status', 'timestamp')
    ordering = ('-timestamp', )
