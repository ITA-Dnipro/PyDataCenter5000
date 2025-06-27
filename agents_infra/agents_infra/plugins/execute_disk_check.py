import os

import psutil

PLUGIN_NAME = 'get_disk_usage'


def execute(parent=None, **kwargs):
    return {'disk_usage': psutil.disk_usage(os.path.abspath(os.sep))}
