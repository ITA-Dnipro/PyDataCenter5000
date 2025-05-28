from django.contrib import admin
from .models import ServerStatus, CommandHistory

admin.site.register(ServerStatus)

@admin.register(CommandHistory)
class CommandHistoryAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'status', 'timestamp')
    list_filter = ('status', 'hostname')
    search_fields = ('hostname', 'command')
    readonly_fields = ('hostname', 'command', 'result', 'status', 'timestamp')
