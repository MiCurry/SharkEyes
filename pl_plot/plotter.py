import os
import sys
import shutil
import traceback
from uuid import uuid4
from scipy.io import netcdf
import numpy
import pytz
from matplotlib import pyplot
from mpl_toolkits.basemap import Basemap
from pl_download.models import DataFile
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta

""" The plotter file contains Plotters for models that help with plot generation
 Instantiated with model DataFile, Plotters allow retuines to access and read the datafiles properties.
 
 If you're unfamilr with the NetCDF file check out: https://www.unidata.ucar.edu/software/netcdf/. Brifly described
 NetCDF fiels are self-describing, which allows us to access variables and meta-deta that describes their variables. So
 for instance we can grab the 'time' variable from a datafile. We can then see what units they are in by: time.units. 
 This is great because it allows us to see variable ranges, what units they are in etc.
 
 If you have a function that isn't a plot_function, say grab the time at which a certin time slice applies or see the 
 latitude and longitude of the datafile, the plotter is a good place to do that.
"""

class WaveWatchPlotter:
    data_file = None

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name): # Gives a netcdf file object with default mode of reading permissions only
        self.data_file = netcdf.netcdf_file(
            os.path.join(
                settings.MEDIA_ROOT,
                settings.WAVE_WATCH_DIR,
                file_name
            )
        )

    def make_plot(self, plot_function, forecast_index,storage_dir, generated_datetime, zoom_levels, downsample_ratio=None):
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
        plot_function(ax=ax, data_file=self.data_file, forecast_index=forecast_index, bmap=bmap, key_ax=key_ax, downsample_ratio=downsample_ratio)
        plot_filename = "{0}_{1}_{2}_{3}.png".format(plot_function.__name__,forecast_index,generated_datetime, uuid4())
        key_filename = "{0}_key_{1}_{2}.png".format(plot_function.__name__,generated_datetime, uuid4())

        # TODO: set the resolution higher for the zoomed-in overlays. The code below
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
        fig.savefig(
             os.path.join(settings.MEDIA_ROOT, storage_dir, plot_filename),
             dpi=DPI, bbox_inches='tight', pad_inches=0,
             transparent=True, frameon=False)
        pyplot.close(fig)

        key_fig.savefig(
                 os.path.join(settings.MEDIA_ROOT, settings.KEY_STORAGE_DIR, key_filename),
                 dpi=500, bbox_inches='tight', pad_inches=0,
                 transparent=True, facecolor=key_fig.get_facecolor())
        pyplot.close(key_fig)

        return plot_filename, key_filename

class WindPlotter:
    data_file = None

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name):
        #Gives a netcdf file object with default mode of reading permissions only
        self.data_file = netcdf.netcdf_file(
            os.path.join(
                settings.MEDIA_ROOT,
                settings.WIND_DIR,
                file_name
            )
        )

    def get_number_of_model_times(self):
        time_var = 'time'
        try:
            self.data_file.variables["time"]
        except Exception:
            time_var = 'time1'
        return numpy.shape(self.data_file.variables[time_var])[0]

    def get_time_at_oceantime_index(self, index):
        # The Wind model uses a dynamic reference date for date calculation
        # This calculates that date and then uses it to calculate the dates for each index
        dst = 0
        isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
        if isdst_now_in("America/Los_Angeles"):
            dst = -1
        wind_file = DataFile.objects.filter(type='WIND').latest('model_date')
        time_var = 'time'
        reftime_var = 'reftime'
        try:
            self.data_file.variables["time"]
        except Exception:
            time_var = 'time1'
            reftime_var = 'reftime1'
        raw_epoch_date = str(wind_file.model_date)
        epoch_date = raw_epoch_date.split('-')
        epoch_year = int(epoch_date[0])
        epoch_month = int(epoch_date[1])
        epoch_day = int(epoch_date[2])
        ocean_time_epoch = datetime(day=epoch_day, month=epoch_month, year=epoch_year, hour=0, minute=0, second=0,
                                    tzinfo=timezone.utc)
        swap_time = numpy.shape(self.data_file.variables[time_var])[0]
        print "PLOTTER SWAP_TIME = ", swap_time
        if swap_time > 70:
            mod_plus = [61,65,69]
            mod_sub = [63,67,71]
            no_mod = [64,68,72]
        elif 65 > swap_time < 70:
            mod_plus = [57,61,65]
            mod_sub = [55,59,63,67]
            no_mod = [56,60,64,68]
        elif swap_time < 60:
            mod_plus = [37,41,45,49]
            mod_sub = [39,43,47,51]
            no_mod = [40,44,48,52]
        modifier = 0
        if index in mod_plus:
            modifier = 1
        elif index in mod_sub:
            modifier = -1
        elif index in no_mod:
            modifier = 0

        hours_since_epoch = timedelta(
            hours=(self.data_file.variables[time_var][index] + dst - self.data_file.variables[reftime_var][0]) + modifier)
        print "Plotted time ", ocean_time_epoch + hours_since_epoch
        return ocean_time_epoch + hours_since_epoch

    def key_check(self):
        # The Barb Key is Static, so make sure its in the correct directory each time we make a plot
        keyFile = os.path.join(settings.MEDIA_ROOT, settings.KEY_STORAGE_DIR, "barbKey.png")
        barbStatic = "/opt/sharkeyes/src/static_files/imgs/barbKey.png"

        shutil.copyfile(barbStatic, keyFile)
        return 1

    def make_plot(self, plot_function, zoom_levels, time_index=0, downsample_ratio=None):
        fig = pyplot.figure()
        ax = fig.add_subplot(111)  # one subplot in the figure

        #window cropped by picking lat and lon corners
        bmap = Basemap(projection='merc',                         #A cylindrical, conformal projection.
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=40.5833284543, urcrnrlat=47.4999927992,
                       llcrnrlon=-129, urcrnrlon=-123.7265625,
                       ax=ax, epsg=4326)

        plot_function(ax=ax, data_file=self.data_file, time_index=time_index, bmap=bmap, downsample_ratio=downsample_ratio)

        generated_datetime = timezone.now().date()

        plot_filename = "{0}_{1}_{2}_{3}.png".format(plot_function.__name__, time_index, generated_datetime, uuid4())

        key_filename = "barbKey.png"

        fig.savefig(
             os.path.join(settings.MEDIA_ROOT, settings.UNCHOPPED_STORAGE_DIR, plot_filename),
             dpi=500, bbox_inches='tight', pad_inches=0,
             transparent=True, frameon=False)
        pyplot.close(fig)

        # Winds use a static key, but it gets deleted from the delete function, so this ensures that it
        # in the right place every time.
        self.key_check()

        return plot_filename, key_filename

class Plotter:
    data_file = None

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name):
        try:
            self.data_file = netcdf.netcdf_file(
                os.path.join(
                    settings.MEDIA_ROOT,
                    settings.NETCDF_STORAGE_DIR,
                    file_name
                )
            )
        except Exception:
            print '-' * 60
            traceback.print_exc(file=sys.stdout)
            print '-' * 60

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
        # we used the dimensions provided by the file itself, but the change in provided data has changed
        # the size of the image.

        # longs = self.data_file.variables['lon_rho'][0, :] # only needed to set up longs
        # lats = self.data_file.variables['lat_rho'][:, 0] # only needed to set up lats
        longs = [-129.0, -123.726199391]
        lats = [40.5840806224, 47.499]

        # Window cropped by picking lat and lon corners
        bmap = Basemap(projection='merc',
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=lats[0], urcrnrlat=lats[-1],
                       llcrnrlon=longs[0], urcrnrlon=longs[-1],
                       ax=ax, epsg=4326)

        plot_function(ax=ax, data_file=self.data_file, time_index=time_index, bmap=bmap, key_ax=key_ax,
                      downsample_ratio=downsample_ratio)

        plot_filename = "{0}_{1}.png".format(plot_function.__name__, uuid4())
        key_filename = "{0}_key_{1}.png".format(plot_function.__name__, uuid4())

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
