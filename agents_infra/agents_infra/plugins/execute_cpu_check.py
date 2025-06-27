import psutil

PLUGIN_NAME = 'get_cpu_percent'


def execute(parent=None, **kwargs):
    return {'cpu_percent': psutil.cpu_percent(**kwargs)}
