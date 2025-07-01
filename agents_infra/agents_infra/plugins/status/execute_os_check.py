import platform

PLUGIN_NAME = 'check_os'
PLUGIN_CATEGORY = 'status'


def execute(parent=None, *args, **kwargs):
    return {'os': platform.system().lower() or 'unknown'}
