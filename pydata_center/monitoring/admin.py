from django.contrib import admin

from .models import CommandHistory, ServerStatus


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
