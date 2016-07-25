from django.db import models
from django.core.files.storage import FileSystemStorage
from django.core.files import File
import math
import os
from django.conf import settings
from matplotlib import pyplot
from celery import group
from datetime import datetime, time, tzinfo, timedelta
from django.utils import timezone
from celery import shared_task
from pl_plot import plot_functions
from pl_plot.plotter import Plotter, WaveWatchPlotter, WindPlotter
from pl_download.models import DataFile, DataFileManager
from mpl_toolkits.basemap import Basemap
from pydap.client import open_url
from django.db.models.aggregates import Max
from uuid import uuid4
from scipy.io import netcdf_file
import numpy
import shutil
import numpy as np
import datetime
from django.conf import settings



def wind(time_index, ratio=1, len=9):
    data_file = open_url(settings.WIND_URL)
    fig = pyplot.figure()
    ax = fig.add_subplot(111)  # one subplot in the figure


    bmap = Basemap(projection='merc',                         #A cylindrical, conformal projection.
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=40.5833284543, urcrnrlat=47.4999927992,
                       llcrnrlon=-129, urcrnrlon=-123.7265625,
                       ax=ax, epsg=4326)

    var_u = 'u-component_of_wind_height_above_ground'
    var_v = 'v-component_of_wind_height_above_ground'
    landMask = 'Land_cover_0__sea_1__land_surface'

    level = 1; #Sea Surface

    tmp = numpy.loadtxt('/opt/sharkeyes/src/latlon.g218')
    lat = numpy.reshape(tmp[:, 2], [614,428])
    lon = numpy.reshape(tmp[:, 3], [614,428])

    """
    Grabbing the u + v values at time_index, level = 0, x = nan, y = nan
    nan = not a number
    """
    wind_u = data_file[var_u][time_index+104, 0, :, :]
    wind_v = data_file[var_v][time_index+104, 0, :, :]
    model_time = data_file['time']

    wind_u = numpy.reshape(wind_u, (614, 428))
    wind_v = numpy.reshape(wind_v, (614, 428))
    x, y = bmap(lon, lat)
    print "Number of Wind_u:", wind_u.shape
    print "Number of Wind_v:", wind_v.shape
    print "Lat:", lat.shape
    print "Lon:", lon.shape
    print "x:", x.shape ,"y", y.shape
    ratio = 4
    print "Ratio:", ratio

    for i in range(0, len(lon)):
        lon[i] = -lon[i]

    bmap.drawmapboundary(linewidth=1.0, ax=ax)
    bmap.drawparallels(np.arange(0, 360, 1), labels=[1,1,1,1])
    bmap.drawmeridians(np.arange(0,360,1), labels=[1,1,1,1])
    bmap.drawcoastlines()
    bmap.barbs(         x[::ratio, ::ratio],
                        y[::ratio, ::ratio],
                        wind_u[::ratio, ::ratio],
                        wind_v[::ratio, ::ratio],
                        ax=ax,
                        color='black')

    plt.show()