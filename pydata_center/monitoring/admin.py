from django.contrib import admin

from .models import AgentMetric, CommandHistory, ServerStatus, Webhook


@admin.register(CommandHistory)
class CommandHistoryAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'status', 'timestamp')
    list_filter = ('status', 'hostname')
    search_fields = ('hostname', 'command')
    readonly_fields = ('hostname', 'command', 'result', 'status', 'timestamp')


@admin.register(ServerStatus)
class ServerStatusAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'server_name', 'ip', 'uptime', 'timestamp')
    search_fields = ('hostname', 'server_name')
    list_filter = ('server_name', )
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


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('service', 'url', 'enabled')
