import os

import psutil

PLUGIN_NAME = 'check_disk_usage'
PLUGIN_CATEGORY = 'metric'


def execute(parent=None, **kwargs):
    return {'disk_usage': psutil.disk_usage(os.path.abspath(os.sep))}
