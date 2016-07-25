from __future__ import absolute_import
import os
from celery import Celery
from django.conf import settings

# SharkEyesCore/celery.py
# This file starts the Celery application

# Setting the default Django settings module for celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SharkEyesCore.settings')

# Starting/naming the celery application
app = Celery('SharkEyesCore')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Not sure what this does
@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))