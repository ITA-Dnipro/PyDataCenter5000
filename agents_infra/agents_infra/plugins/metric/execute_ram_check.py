import psutil

PLUGIN_NAME = 'check_ram_percent'
PLUGIN_CATEGORY = 'metric'


def execute(parent=None, **kwargs):
    return {'ram_percent': psutil.virtual_memory()}
