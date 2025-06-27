import psutil

PLUGIN_NAME = 'get_cpu_percent'


def execute(*args, **kwargs):
    return {'cpu_percent': psutil.cpu_percent(*args, **kwargs)}
