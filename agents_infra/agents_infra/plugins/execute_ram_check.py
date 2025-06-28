import psutil

PLUGIN_NAME = 'ram_percent'


def execute(parent=None, **kwargs):
    return {'ram_percent': psutil.virtual_memory()}
