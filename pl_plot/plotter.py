__author__ = 'avaleske'
from scipy.io import netcdf
import numpy
from matplotlib import pyplot
from mpl_toolkits.basemap import Basemap
from pydap.client import open_url
import os
import shutil
from uuid import uuid4
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone



class WaveWatchPlotter:
    data_file = None

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name):
        #Gives a netcdf file object with default mode of reading permissions only
        self.data_file = netcdf.netcdf_file(
            os.path.join(
                settings.MEDIA_ROOT,
                settings.WAVE_WATCH_DIR,
                file_name
            )
        )

    # the unchopped file's index starts at noon: index = 0 and progresses throgh 85 forecasts, one per hour, for the next 85 hours.
   # def get_time_from_index_of_file(self, index):
     #   self.data_file.variables
     #   ocean_time_epoch = datetime(day=1, month=1, year=2005, hour=0, minute=0, second=0, tzinfo=timezone.utc)
      #  seconds_since_epoch = timedelta(seconds=self.data_file.variables['ocean_time'][index])
      #  return ocean_time_epoch + seconds_since_epoch

#make a plot, with the Function to use specified, the storage directory specified, and the Index (ie 0--85 forecasts)
# based on the title of the file
    def make_plot(self, plot_function, forecast_index,storage_dir, generated_datetime, zoom_levels, downsample_ratio=None):

        period_flag = 0 #This is used to determine whether or not we are plotting wave period
        if storage_dir == "": # Wave period has no storage_dir so if it is blank we are plotting wave period
            period_flag = 1

        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)

        ax = fig.add_subplot(111)  # one subplot in the figure

        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05])

        longs = self.data_file.variables['longitude'][:]
        lats = self.data_file.variables['latitude'][:]

        # window cropped by picking lat and lon corners
        # We are using the Mercator projection, because that is what Google Maps wants. The inputs should
        # probably be just plain latitude and longitude, i.e. they should be in unprojected form when they are passed in.
        bmap = Basemap(projection='merc',                         #A cylindrical, conformal projection.
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=lats[0][0], urcrnrlat=lats[-1][0],
                       llcrnrlon=longs[0][0], urcrnrlon=longs[-1][-1],
                      ax=ax, epsg=4326)
        if period_flag == 0:
            plot_function(ax=ax, data_file=self.data_file, forecast_index=forecast_index, bmap=bmap, key_ax=key_ax, downsample_ratio=downsample_ratio)
        else:
            plot_function(data_file=self.data_file, forecast_index=forecast_index)
        if period_flag == 0: #Wave period does not need a plot_filename, so only do this if the model is not wave period
            plot_filename = "{0}_{1}_{2}_{3}.png".format(plot_function.__name__,forecast_index,generated_datetime, uuid4())
        key_filename = "{0}_key_{1}_{2}.png".format(plot_function.__name__,generated_datetime, uuid4())

        # TODO: set the resolution higher for the zoomed-in overlays. The code below
        # seems to set the resolution properly, but at the expense of performance: it takes
        # 5 minutes to plot the biggest images, which is two long if we don't have better
        # parallelization.
        # if zoom_levels == '9-11' :
        #     DPI = 1800
        # elif zoom_levels == '12':
        #     DPI = 2400
        # elif zoom_levels == '6-8':
        #     DPI = 1200 # Original
        #
        # else:
        #     DPI = 800

        # There needs to be a case of each of these zoom-level ranges:  [('2-8', 20), ('9-10', 15),  ('11-12', 5)]
        # which comes from the pl_plot/models file
        if zoom_levels == '11-12':
            DPI = 1800
        elif zoom_levels == '9-10':
            DPI = 1200 # Original
        else:
            DPI = 800

        # Changing the DPI sometimes seems to cause an error when Tiling using gdal2tiles. For instance I tried
        # dpi=2000 and got a strange error. Internet sources suggest that there may be some sort of off-by-one
        # error when the size of the image given to gdal is irregular in some way. Moving DPI to 1800 fixed the
        # issue.

        if period_flag == 0: #This saves a figure to the media folder. Only do this if the model is not wave period.
            fig.savefig(
                 os.path.join(settings.MEDIA_ROOT, storage_dir, plot_filename),
                 dpi=DPI, bbox_inches='tight', pad_inches=0,
                 transparent=True, frameon=False)
            pyplot.close(fig)

        #This saves the key. Every model needs this.
        key_fig.savefig(
                 os.path.join(settings.MEDIA_ROOT, settings.KEY_STORAGE_DIR, key_filename),
                 dpi=500, bbox_inches='tight', pad_inches=0,
                 transparent=True, facecolor=key_fig.get_facecolor())
        pyplot.close(key_fig)

        if period_flag == 0:
            return plot_filename, key_filename
        else:
            return key_filename #Wave period only needs key_filename

class WindPlotter:
    data_file = None

    def load_file(self, file_name):
        #This should have some form of error handling as it can fail
        self.data_file = open_url(settings.WIND_URL)

    def get_number_of_model_times(self):
        return 12

    def get_time_at_oceantime_index(self,index):
        time = timezone.now()
        time = time.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        if(index == 0):
            time = time.replace(hour = 12)
        else:
            time = time + timedelta(hours = (index * 3))
        print "Time:", time
        return time

    def key_check(self):
        # The Barb Key is Static, so make sure its in the correctly directory each time we make a plot
        keyFile = os.path.join(settings.MEDIA_ROOT, settings.KEY_STORAGE_DIR, "barbKey.png")
        barbStatic = os.path.join(settings.STATICFILES_DIRS, "imgs", "barbKey.png")

        if(os.path.isfile(keyFile) == 1):
            return 1
        else:
            shutil.copyfile(barbStatic, keyFile)
            return 1

    def make_plot(self, plot_function, zoom_levels, time_index=0, downsample_ratio=None):

        fig = pyplot.figure()
        key_ax = pyplot.figure()

        ax = fig.add_subplot(111)  # one subplot in the figure

        #window cropped by picking lat and lon corners
        bmap = Basemap(projection='merc',                         #A cylindrical, conformal projection.
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=40.5833284543, urcrnrlat=47.4999927992,
                       llcrnrlon=-129, urcrnrlon=-123.7265625,
                       ax=ax, epsg=4326)

        plot_function(ax=ax, data_file=self.data_file, time_index=time_index, bmap=bmap, downsample_ratio=downsample_ratio)

        generated_datetime = timezone.now().date() #The wind png is always generated at the time of the call

        plot_filename = "{0}_{1}_{2}_{3}.png".format(plot_function.__name__, time_index, generated_datetime, uuid4())

        key_filename = "barbKey.png"


        fig.savefig(
             os.path.join(settings.MEDIA_ROOT, settings.UNCHOPPED_STORAGE_DIR, plot_filename),
             dpi=1200, bbox_inches='tight', pad_inches=0,
             transparent=True, frameon=False)
        pyplot.close(fig)

        # Winds use a static key, but it gets deleted from the delete function, so this ensures that it
        # in the right place everytime.
        self.key_check()

        return plot_filename, key_filename

class Plotter:
    data_file = None

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name):
        self.data_file = netcdf.netcdf_file(
            os.path.join(
                settings.MEDIA_ROOT,
                settings.NETCDF_STORAGE_DIR,
                file_name
            )
        )

    def get_time_at_oceantime_index(self, index):
        #Team 1 says todo add checking of times here. there's only three furthest out file
        ocean_time_epoch = datetime(day=1, month=1, year=2005, hour=0, minute=0, second=0, tzinfo=timezone.utc)
        seconds_since_epoch = timedelta(seconds=self.data_file.variables['ocean_time'][index])
        return ocean_time_epoch + seconds_since_epoch

    def get_number_of_model_times(self):
        return numpy.shape(self.data_file.variables['ocean_time'])[0]

    def make_plot(self, plot_function, zoom_levels, time_index=0,  downsample_ratio=None):

        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)
        ax = fig.add_subplot(111)  # one subplot in the figure
        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05]) # this might be bad for when we have other types of plots

        # Temporary hard coded values to ensure the plotted data is the right size. Previously
        # we used the dimensions provided by the file itself, but the change in provided data has changed the size of the
        # image.
        #longs = self.data_file.variables['lon_rho'][0, :] # only needed to set up longs
        longs = [-129.0, -123.726199391]
        #lats = self.data_file.variables['lat_rho'][:, 0] # only needed to set up lats
        lats = [40.5840806224, 47.499]

        '''print "Latitude Longitude plot area"
        print "\tlats[0]: " + str(lats[0]) + " longs[0]: " + str(longs[0])
        print "\tlats[-1]: " + str(lats[-1])+ " longs[-1]: " + str(longs[-1])'''

        # window cropped by picking lat and lon corners
        bmap = Basemap(projection='merc',
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=lats[0], urcrnrlat=lats[-1],
                       llcrnrlon=longs[0], urcrnrlon=longs[-1],
                       ax=ax, epsg=4326)

        plot_function(ax=ax, data_file=self.data_file, time_index=time_index, bmap=bmap, key_ax=key_ax,
                      downsample_ratio=downsample_ratio) #todo this param is a hack for expo

        plot_filename = "{0}_{1}.png".format(plot_function.__name__, uuid4())
        key_filename = "{0}_key_{1}.png".format(plot_function.__name__, uuid4())

         # TODO: set the resolution higher for the zoomed-in overlays. But we don't need
        # the original 1200 dpi for the zoomed-out images (where zoom level is 3-5, for instance)
        # There needs to be a case for each of these sets of zoom levels:  zoom_levels_for_currents = [('2-7', 8),  ('8-12', 2)]
        if zoom_levels == '8-12':
            DPI = 1800
        else:
            DPI = 800 # Original is 1200 dpi

        fig.savefig(
            os.path.join(settings.MEDIA_ROOT, settings.UNCHOPPED_STORAGE_DIR, plot_filename),
            dpi=DPI, bbox_inches='tight', pad_inches=0,
            transparent=True, frameon=False)
        pyplot.close(fig)

        key_fig.savefig(
            os.path.join(settings.MEDIA_ROOT, settings.KEY_STORAGE_DIR, key_filename),
            dpi=500, bbox_inches='tight', pad_inches=0,
            transparent=True, facecolor=key_fig.get_facecolor())
        pyplot.close(key_fig)

        return plot_filename, key_filename
