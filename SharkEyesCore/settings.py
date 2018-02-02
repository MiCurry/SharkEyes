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
from celery.schedules import crontab
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

TEST_RUNNER = 'SharkEyesCore.test_runner.CustomTestRunner'

ALLOWED_HOSTS = [
    '.seacast.org',     # Allow domain and subdomains
    '.seacast.org.',    # Also allow FQDN and subdomains
]

# Application definition
INSTALLED_APPS = (
    'celery',
    'djcelery',
    'south',
    'pl_download',
    'pl_plot',
    'pl_chop',
    'SharkEyesCore',
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
# https://docs.djangoproject.com/en/1.8/topics/i18n/timezones/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Los_Angeles'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

#some database
CONN_MAX_AGE = None

# For celery
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 5672
BROKER_VHOST = "sharkeyes"

CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'
CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'
CELERY_IMPORTS = ('SharkEyesCore.tasks',)

CELERYBEAT_SCHEDULE = {
    'plot_pipeline': {
        'task': 'sharkeyescore.pipeline',
        'schedule': crontab(minute=0, hour='1,19'),
        'args': ()
    },
}

### Globals ###
TEMPLATE_DIRS = BASE_DIR + '/templates/'

STATIC_URL = '/static/'
STATIC_ROOT = '/opt/sharkeyes/static/'
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static_files'), )

OVERLAY_KEY_COLOR = '#00001F'

# other files
NETCDF_STORAGE_DIR = "netcdf"
UNCHOPPED_STORAGE_DIR = "unchopped"
VRT_STORAGE_DIR = "vrt_files"
TILE_STORAGE_DIR = "tiles"
KEY_STORAGE_DIR = "keys"
WAVE_WATCH_DIR = "wave_watch_datafiles"
WAVE_WATCH_STORAGE_DIR = "wave_watch_forecasts"
WIND_DIR = "wind_datafiles"
WIND_STORAGE_DIR = "wind_forecasts"
HYCOM_DIR = "hycom_datafiles"
WW3_DIR = "ww3_datafiles"

MEDIA_ROOT = "/opt/sharkeyes/media/"
MEDIA_URL = "/media/"

BASE_NETCDF_URL = "http://ingria.coas.oregonstate.edu/opendap/ORWA/" #OSU_ROMS URL
WAVE_WATCH_URL = "ftp://cil-www.oce.orst.edu/pub/outgoing/ww3data/"
FTP_WAVE_WAVE_URL = "cil-wwww.oce.orst.edu"
RTOFS_URL = "http://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/rtofs."
RTOFS_OPENDAP_URL = "http://nomads.ncep.noaa.gov:9090/dods/rtofs/"
#Not Currently used. Can be used if you need to stream wind data for some reason.
#WIND_URL = "http://thredds.ucar.edu/thredds/dodsC/grib/NCEP/NAM/CONUS_12km/conduit/Best"


SEACAST_DOMAIN = { 'longs' : [-129.0, -123.7261], 'lats': [40.5840, 47.499] }
OSU_ROMS_DOMAIN = { 'longs' : [-129.0, -123.726199391], 'lats': [40.5840806224, 47.499] }
OSU_WW3_DOMAIN = { 'longs' : [-129.0, -123.726199391], 'lats': [40.5840806224, 47.499] }
HYCOM_DOMAIN  = { 'longs' : [], 'lats': [] }
NCEP_WW3_DOMAIN = { 'longs' : [-140, -110], 'lats': [25, 55] }
NAMS_WIND_DOMAIN = { 'longs' : [], 'lats': [] }

# Model Datafile File Start names
OSU_ROMS_DF_FN = "OSU_ROMS"
OSU_WW3_DF_FN = "Outergrid"
NAMS_WIND_DF_FN = "WIND"
NCEP_WW3_DF_FN  = "NCEP_WW3"
HYCOM_DF_FN = "HYCOM"

# Model Definition ID's
OSU_ROMS_SST = 1
OSU_ROMS_SUR_SAL = 2
OSU_ROMS_SUR_CUR = 3
OSU_WW3_HI = 4
NAMS_WIND = 5
OSU_WW3_DIR = 6
OSU_ROMS_BOT_SAL = 7
OSU_ROMS_BOT_TEMP = 8
OSU_ROMS_SSH = 9
NCEP_WW3_DIR = 10
NCEP_WW3_HI = 11
HYCOM_SST = 12
HYCOM_SUR_CUR = 13
OSU_ROMS_TCLINE = 14
OSU_ROMS_PCLINE = 15
NAVY_HYCOM_SST = 16
NAVY_HYCOM_SUR_CUR = 17
NAVY_HYCOM_SUR_SAL = 18
NAVY_HYCOM_SSH = 19
NAVY_HYCOM_BOT_TEMP = 20
NAVY_HYCOM_BOT_CUR = 21
NAVY_HYCOM_BOT_SAL = 22


OSU_ROMS = [OSU_ROMS_SST, OSU_ROMS_SUR_SAL,
            OSU_ROMS_SUR_CUR, OSU_ROMS_BOT_SAL,
            OSU_ROMS_BOT_TEMP, OSU_ROMS_SSH]

OSU_WW3 = [OSU_WW3_HI, OSU_WW3_DIR]

NCEP_WW3 = [NCEP_WW3_HI, NCEP_WW3_DIR]

HYCOM = [HYCOM_SST, HYCOM_SUR_CUR]

VECTOR_FIELDS = [OSU_ROMS_SUR_CUR, HYCOM_SUR_CUR]
WAVE_VECTOR_FIELDS = [OSU_WW3_DIR, NCEP_WW3_DIR]

ZOOM_LEVELS_CURRENTS = [('2-7', 8),  ('8-12', 4)]
ZOOM_LEVELS_WIND = [('1-10', 2), ('11-12', 1)]
ZOOM_LEVELS_OTHERS = [(None, None)]

ZOOM_LEVELS_FOR_WAVE_DIR = [('2-8', 20), ('9-10', 15), ('11-12', 5)]
ZOOM_LEVELS_FOR_WAVE_OTHERS = [(None, None)]



# import local settings. PyCharm thinks it's unused, but PyCharm is silly.
# noinspection PyUnresolvedReferences
from .settings_local import *

