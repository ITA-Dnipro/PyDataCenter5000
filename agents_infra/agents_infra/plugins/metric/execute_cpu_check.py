import psutil

PLUGIN_NAME = 'check_cpu_percent'
PLUGIN_CATEGORY = 'metric'


def execute(parent=None, **kwargs):
    return {'cpu_percent': psutil.cpu_percent(**kwargs)}
