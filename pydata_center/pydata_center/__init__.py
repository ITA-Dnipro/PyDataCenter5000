from __future__ import absolute_import, unicode_literals
# celery setup at django start
from .celery import app as celery_app

__all__ = ['celery_app']