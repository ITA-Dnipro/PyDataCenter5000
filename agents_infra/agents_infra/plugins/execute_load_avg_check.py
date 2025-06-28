import os

PLUGIN_NAME = 'load_avg'
PLUGIN_CATEGORY = 'metric'


def execute(parent=None, **kwargs):
    """Get system's average load over the past 1, 5, and 15 minutes."""
    return {'load_avg': os.getloadavg()}
