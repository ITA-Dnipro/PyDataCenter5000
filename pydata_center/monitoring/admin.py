from django.contrib import admin

from .models import AgentMetric, AlertRule, CommandHistory, ServerStatus


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
    )
    list_filter = ('metric', 'is_active')
    search_fields = ('metric', )
    readonly_fields = ('created_at', )
