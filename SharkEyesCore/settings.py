"""
Django settings for SharkEyesCore project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""
from __future__ import absolute_import

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))



ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = (
    'celery',
    'djcelery',
    'south',
    'pl_download',
    'pl_plot',
    'pl_chop',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'SharkEyesCore.urls'

WSGI_APPLICATION = 'SharkEyesCore.apache.wsgi.application'


# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Los_Angeles'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_DIRS = BASE_DIR + '/templates/'

STATIC_URL = '/static/'
STATIC_ROOT = '/opt/sharkeyes/static/'
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static_files'),)


# other files
NETCDF_STORAGE_DIR = "netcdf"
UNCHOPPED_STORAGE_DIR = "unchopped"
VRT_STORAGE_DIR = "vrt_files"
TILE_STORAGE_DIR = "tiles"
KEY_STORAGE_DIR = "keys"


MEDIA_ROOT = "/opt/sharkeyes/media/"
MEDIA_URL = "/media/"

BASE_NETCDF_URL = "http://ingria.coas.oregonstate.edu/opendap/ACTZ/"

# For celery
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 5672
BROKER_VHOST = "sharkeyes"

CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'
CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'
CELERY_IMPORTS = ('SharkEyesCore.tasks',)

# import local settings. PyCharm thinks it's unused, but PyCharm is silly.
from .settings_local import *
