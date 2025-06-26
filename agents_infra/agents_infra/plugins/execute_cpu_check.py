import psutil


def execute(*args, **kwargs):
    return {'cpu_percent': psutil.cpu_percent(*args, **kwargs)}
