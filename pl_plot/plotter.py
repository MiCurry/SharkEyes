import os
import sys
import shutil
import traceback
from uuid import uuid4
from scipy.io import netcdf
from netCDF4 import Dataset
import xarray as xr
import numpy
import pytz
import time
from matplotlib import pyplot
from mpl_toolkits.basemap import Basemap
from pl_download.models import DataFile
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta, time

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
    zoom_level = None

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name):  # Gives a netcdf file object with default mode of reading permissions only
        self.data_file = netcdf.netcdf_file(
            os.path.join(
                settings.MEDIA_ROOT,
                settings.WAVE_WATCH_DIR,
                file_name
            )
        )

    def get_zoom_level(self, def_id):
        if def_id in settings.WAVE_VECTOR_FIELDS:
            self.zoom_level = settings.ZOOM_LEVELS_FOR_WAVE_DIR
            return self.zoom_level
        else:
            self.zoom_level = settings.ZOOM_LEVELS_FOR_WAVE_OTHERS
            return self.zoom_level

    def get_number_of_model_times(self):
        return numpy.shape(self.data_file.variables['time'])[0]

    def get_oceantime(self, time_index):
        ''' Get the 'applies_at_datetime', the datetime that the forecast that is being request is for.

        :param time_index: The index from the start of the models index to be found.
        :return: Timezone aware datetime object with the plotted forecast date and time.
        '''
        seconds = self.data_file.variables['time'][time_index]
        epoch = datetime.strptime(self.data_file.variables['time'].units, "seconds since %Y-%m-%d %H:%M:%S.0 0:00")
        model_date = epoch + timedelta(seconds=seconds) # Values enced as secs since..
        return model_date

    def get_last_model_time(self):
        return self.get_oceantime(self.get_number_of_model_times() - 1)

    def make_plot(self, plot_function, forecast_index, storage_dir, generated_datetime, zoom_levels,
                  downsample_ratio=None):
        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)

        ax = fig.add_subplot(111)  # one subplot in the figure

        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05])

        longs = self.data_file.variables['longitude'][:]
        lats = self.data_file.variables['latitude'][:]

        # window cropped by picking lat and lon corners
        # We are using the Mercator projection, because that is what Google Maps wants. The inputs should
        # probably be just plain latitude and longitude, i.e. they should be in unprojected form when they are passed in.
        bmap = Basemap(projection='merc',  # A cylindrical, conformal projection.
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=lats[0][0], urcrnrlat=lats[-1][0],
                       llcrnrlon=longs[0][0], urcrnrlon=longs[-1][-1],
                       ax=ax, epsg=4326)
        plot_function(ax=ax, data_file=self.data_file, forecast_index=forecast_index, bmap=bmap, key_ax=key_ax,
                      downsample_ratio=downsample_ratio)
        plot_filename = "{0}_{1}_{2}_{3}.png".format(plot_function.__name__, forecast_index, generated_datetime,
                                                     uuid4())
        key_filename = "{0}_key_{1}_{2}.png".format(plot_function.__name__, generated_datetime, uuid4())

        # TODO: set the resolution higher for the zoomed-in overlays. The code below
        # There needs to be a case of each of these zoom-level ranges:  [('2-8', 20), ('9-10', 15),  ('11-12', 5)]
        # which comes from the pl_plot/models file
        if zoom_levels == '11-12':
            DPI = 1800
        elif zoom_levels == '9-10':
            DPI = 1200  # Original
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
    zoom_level = None
    domain = None

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name):
        # Gives a netcdf file object with default mode of reading permissions only
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

    def get_wind_indices(self):
        wind_file = DataFile.objects.filter(type='WIND').latest('model_date')
        wind_name = wind_file.file.name
        wind_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WIND_DIR, wind_name), 'r')
        wind_values = {'time': 0, 'reftime': 0, 'begin': 0, 'swap': 0, 'indices': 0}
        time_var = 'time'
        reftime_var = 'reftime'
        try:
            wind_data.variables["time"]
        except Exception:
            time_var = 'time1'
            reftime_var = 'reftime1'
        wind_values['time'] = time_var
        wind_values['reftime'] = reftime_var

        indices = numpy.shape(wind_data.variables[time_var])[0]
        raw_epoch_date = str(wind_file.model_date)
        epoch_date = raw_epoch_date.split('-')
        epoch_year = int(epoch_date[0])
        epoch_month = int(epoch_date[1])
        epoch_day = int(epoch_date[2])
        ocean_time_epoch = datetime(day=epoch_day, month=epoch_month, year=epoch_year, hour=0, minute=0, second=0,
                                    tzinfo=timezone.utc)

        # This finds the correct index to start with. The files should always start at midnight, but sometimes they don't.
        # This returns the earliest valid index if index 0 is not midnight
        begin = 0
        for x in range(0, 12, 1):
            hours_since_epoch = timedelta(
                hours=(wind_data.variables[time_var][x] - wind_data.variables[reftime_var][0]))
            current_hour = (ocean_time_epoch + hours_since_epoch).hour
            if current_hour == 0 or current_hour == 4 or current_hour == 8:
                begin = x
                break
        wind_values['begin'] = begin

        # This provides the index where they swap to three hour increments
        times = wind_data.variables[time_var]
        swap = 0
        for x in range(0, indices, 1):
            if times[x] - times[x - 1] == 3 and times[x - 1] - times[x - 2] == 1:
                swap = x
        wind_values['swap'] = swap

        # This determines which of the three hour incremented indices to use
        # three_hour = [0, 3, 9, 12, 15, 21]
        three_hour_indices = []
        for x in range(swap, indices, 1):
            hours_since_epoch = timedelta(
                hours=(wind_data.variables[time_var][x] - wind_data.variables[reftime_var][0]))
            current_hour = (ocean_time_epoch + hours_since_epoch).hour
            if current_hour % 4 == 0 or current_hour % 4 == 1 or current_hour % 4 == 3:
                three_hour_indices.append(x)
        wind_values['indices'] = three_hour_indices
        return wind_values

    def get_time_at_oceantime_index(self, index):
        # The Wind model uses a dynamic reference date for date calculation
        # This calculates that date and then uses it to calculate the dates for each index
        wind_file = DataFile.objects.filter(type='WIND').latest('model_date')
        plotter = WindPlotter(wind_file.file.name)
        wind_values = plotter.get_wind_indices()
        time_var = wind_values['time']
        reftime_var = wind_values['reftime']
        swap = wind_values['swap']
        three_hour_indices = wind_values['indices']
        modifier = 0
        raw_epoch_date = str(wind_file.model_date)
        epoch_date = raw_epoch_date.split('-')
        epoch_year = int(epoch_date[0])
        epoch_month = int(epoch_date[1])
        epoch_day = int(epoch_date[2])
        ocean_time_epoch = datetime(day=epoch_day, month=epoch_month, year=epoch_year, hour=0, minute=0, second=0,
                                    tzinfo=timezone.utc)

        if index >= swap and index in three_hour_indices:
            hours_since_epoch = timedelta(
                hours=(self.data_file.variables[time_var][index] - self.data_file.variables[reftime_var][0]))
            current_hour = (ocean_time_epoch + hours_since_epoch).hour
            if current_hour % 4 == 0:
                modifier = 0
            elif current_hour % 4 == 3:
                modifier = 1
            elif current_hour % 4 == 1:
                modifier = -1

        hours_since_epoch = timedelta(
            hours=(self.data_file.variables[time_var][index] - self.data_file.variables[reftime_var][0]) + modifier)
        return ocean_time_epoch + hours_since_epoch

    def get_zoom_level(self, def_id):
        self.zoom_level = settings.ZOOM_LEVELS_WIND
        return self.zoom_level

    def key_check(self):
        # The Barb Key is Static, so make sure its in the correct directory each time we make a plot
        keyFile = os.path.join(settings.MEDIA_ROOT, settings.KEY_STORAGE_DIR, "barbKey.png")
        barbStatic = "/opt/sharkeyes/src/static_files/imgs/barbKey.png"

        shutil.copyfile(barbStatic, keyFile)
        return 1

    def make_plot(self, plot_function, zoom_levels, time_index=0, downsample_ratio=None):
        fig = pyplot.figure()
        ax = fig.add_subplot(111)  # one subplot in the figure

        # window cropped by picking lat and lon corners
        bmap = Basemap(projection='merc',  # A cylindrical, conformal projection.
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=40.5833284543, urcrnrlat=47.4999927992,
                       llcrnrlon=-129, urcrnrlon=-123.7265625,
                       ax=ax, epsg=4326)

        plot_function(ax=ax, data_file=self.data_file, time_index=time_index, bmap=bmap,
                      downsample_ratio=downsample_ratio)

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
    zoom_level = None
    domain = None

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

    def get_zoom_level(self, def_id):
        if def_id == settings.OSU_ROMS_SUR_CUR:
            self.zoom_level = settings.ZOOM_LEVELS_CURRENTS
            return self.zoom_level
        else:
            self.zoom_level = settings.ZOOM_LEVELS_OTHERS
            return self.zoom_level

    def get_time_at_oceantime_index(self, index):
        # Team 1 says todo add checking of times here. there's only three furthest out file
        ocean_time_epoch = datetime(day=1, month=1, year=2005, hour=0, minute=0, second=0, tzinfo=timezone.utc)
        seconds_since_epoch = timedelta(seconds=self.data_file.variables['ocean_time'][index])
        return ocean_time_epoch + seconds_since_epoch

    def get_number_of_model_times(self):
        return numpy.shape(self.data_file.variables['ocean_time'])[0]

    def get_last_model_time(self):
        return self.get_time_at_oceantime_index(self.get_number_of_model_times() - 1)


    def make_plot(self, plot_function, zoom_levels, time_index=0, downsample_ratio=None):
        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)
        ax = fig.add_subplot(111)  # one subplot in the figure
        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05])  # this might be bad for when we have other types of plots

        # Temporary hard coded values to ensure the plotted data is the right size. Previously
        # we used the dimensions provided by the file itself, but the change in provided data has changed
        # the size of the image.

        #longs = self.data_file.variables['lon_rho'][0, :] # only needed to set up longs
        #lats = self.data_file.variables['lat_rho'][:, 0] # only needed to set up lats

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

class HycomPlotter:
    data_file = None
    zoom_level = None
    domain = settings.SEACAST_DOMAIN

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

    def get_zoom_level(self, def_id):
        if def_id == settings.HYCOM_SUR_CUR:
            self.zoom_level = settings.ZOOM_LEVELS_CURRENTS
            return self.zoom_level
        else:
            self.zoom_level = settings.ZOOM_LEVELS_OTHERS
            return self.zoom_level

    def get_time_at_oceantime_index(self, index):
        days = self.data_file.variables['MT'].data
        epoch = datetime.strptime(self.data_file.variables['MT'].units, "days since %Y-%m-%d %H:%M:%S")
        model_date = epoch + timedelta(days=days[0]) # Values enced as days since..
        return model_date

    def get_number_of_model_times(self):
        return 0

    def make_plot(self, plot_function, zoom_levels, time_index=0,  downsample_ratio=None):
        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)
        ax = fig.add_subplot(111)  # one subplot in the figure
        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05]) # this might be bad for when we have other types of plots

        longs = [-129.0, -123.726199391]
        lats = [40.5840806224, 47.499]

        # window cropped by picking lat and lon corners
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
            DPI = 800  # Original is 1200 dpi

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


class TClinePlotter:
    data_file = None
    zoom_level = settings.ZOOM_LEVELS_OTHERS

    def __init__(self, file_name):
        self.load_file(file_name)

    def load_file(self, file_name):
        try:
            self.data_file = xr.open_dataset(
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

    def get_zoom_level(self, def_id):
        return self.zoom_level

    def get_time_at_oceantime_index(self, index):
        date = str(self.data_file.ocean_time.data[0])
        date = date.split("-")
        day = date[2].split("T")
        hour = 12
        dst = 0
        isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
        if isdst_now_in("America/Los_Angeles"):
            dst = 1
        if index == 0:
            hour = 0
        elif index == 1:
            hour = 4
        elif index == 2:
            hour = 8
        elif index == 3:
            hour = 12
        elif index == 4:
            hour = 16
        elif index == 5:
            hour = 20
        ocean_time = datetime(day=int(day[0]), month=int(date[1]), year=int(date[0]), hour=hour + dst)
        return ocean_time

    def get_number_of_model_times(self):
        return 6

    def make_plot(self, plot_function, zoom_levels, time_index=0, downsample_ratio=None):
        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)
        ax = fig.add_subplot(111)  # one subplot in the figure
        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05])  # this might be bad for when we have other types of plots

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

        plot_function(ax=ax,
                      data_file=self.data_file,
                      time_index=time_index,
                      bmap=bmap,
                      key_ax=key_ax,
                      downsample_ratio=downsample_ratio)

        plot_filename = "{0}_{1}.png".format(plot_function.__name__, uuid4())
        key_filename = "{0}_key_{1}.png".format(plot_function.__name__, uuid4())

        if zoom_levels == '8-12':
            DPI = 1800
        else:
            DPI = 800  # Original is 1200 dpi

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

class NcepWW3Plotter:
    data_file = None
    zoom_level = None
    domain = settings.SEACAST_DOMAIN

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

    def write_file(self, file_name):
        self.data_file = Dataset(
            os.path.join(
                settings.MEDIA_ROOT,
                settings.WAVE_WATCH_DIR,
                file_name
            ), 'r+'
        )

    def close_file(self):
        self.data_file.close()
        return

    def get_zoom_level(self, def_id):
        print "Plotter.get_zoom_level - def_id: {0}".format(def_id)
        if def_id in settings.WAVE_VECTOR_FIELDS:
            self.zoom_level = settings.ZOOM_LEVELS_FOR_WAVE_DIR
            return self.zoom_level
        else:
            self.zoom_level = settings.ZOOM_LEVELS_FOR_WAVE_OTHERS
            return self.zoom_level

    def get_oceantime(self, time_index):
        ''' Get the 'applies_at_datetime', the datetime that the forecast that is being request is for.

        :param overlay_id: The overlay definition id
        :param time_index: The index from the start of the models index to be found.
        :return: Timezone aware datetime object with the plotted forecast date and time.
        '''
        times = self.data_file.variables['time']
        basetime = self.data_file.variables['time'].units
        basetime = datetime.strptime(basetime, "Hour since %Y-%m-%dT00:00:00Z")
        applies_at_datetime = timezone.make_aware(basetime + timedelta(hours=times[time_index]) , timezone.utc)
        return applies_at_datetime

    def get_number_of_model_times(self):
        return numpy.shape(self.data_file.variables['reftime'])[0]

    def make_plot(self, plot_function, forecast_index, storage_dir, generated_datetime, zoom_levels,
                  downsample_ratio=None):
        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)

        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05])

        ax = fig.add_subplot(111)  # one subplot in the figure

        longs = [-129.0, -123.726199391]
        lats = [40.5840806224, 47.499]

        bmap = Basemap(projection='merc',                         #A cylindrical, conformal projection.
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=lats[0], urcrnrlat=lats[1],
                       llcrnrlon=longs[0], urcrnrlon=longs[1],
                       ax=ax, epsg=4326)

        plot_function(ax=ax, data_file=self.data_file, forecast_index=forecast_index, bmap=bmap, key_ax=key_ax, downsample_ratio=downsample_ratio)
        plot_filename = "{0}_{1}_{2}_{3}.png".format(plot_function.__name__,forecast_index,generated_datetime, uuid4())
        key_filename = "{0}_key_{1}_{2}.png".format(plot_function.__name__,generated_datetime, uuid4())

        if zoom_levels == '11-12':
            DPI = 1800
        elif zoom_levels == '9-10':
            DPI = 1200 # Original
        else:
            DPI = 800

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


class NavyPlotter:
    data_file = None
    zoom_level = None
    domain = settings.SEACAST_DOMAIN

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

    def get_zoom_level(self, def_id):
        if def_id in settings.NAVY_HYCOM_CUR:
            self.zoom_level = settings.ZOOM_LEVELS_CURRENTS
            return self.zoom_level
        else:
            self.zoom_level = settings.ZOOM_LEVELS_OTHERS
            return self.zoom_level

    def get_time_at_oceantime_index(self, index=None):
        basetime = self.data_file.variables['time'].units
        basetime = datetime.strptime(basetime, "hours since %Y-%m-%d 00:00:00")
        return basetime + timedelta(hours=self.data_file.variables['time'][0])


    def get_number_of_model_times(self):
        return 0

    def make_plot(self, plot_function, zoom_levels, time_index=0,  downsample_ratio=None):
        fig = pyplot.figure()
        key_fig = pyplot.figure(facecolor=settings.OVERLAY_KEY_COLOR)
        ax = fig.add_subplot(111)  # one subplot in the figure
        key_ax = key_fig.add_axes([0.1, 0.2, 0.6, 0.05]) # this might be bad for when we have other types of plots

        longs = [-129.0, -123.726199391]
        lats = [40.5840806224, 47.499]

        # window cropped by picking lat and lon corners
        bmap = Basemap(projection='merc',
                       resolution='h', area_thresh=1.0,
                       llcrnrlat=lats[0], urcrnrlat=lats[-1],
                       llcrnrlon=longs[0], urcrnrlon=longs[-1],
                       ax=ax, epsg=4326)

        plot_function(ax=ax, data_file=self.data_file, bmap=bmap, key_ax=key_ax, downsample_ratio=downsample_ratio)

        plot_filename = "{0}_{1}.png".format(plot_function.__name__, uuid4())
        key_filename = "{0}_key_{1}.png".format(plot_function.__name__, uuid4())


        if zoom_levels == '8-12':
            DPI = 1800
        else:
            DPI = 800 # Original is 1200 dpi

        fig.savefig(
            os.path.join(settings.MEDIA_ROOT, settings.UNCHOPPED_STORAGE_DIR, plot_filename),
            dpi=DPI, bbox_inches='tight', pad_inches=0,
            transparent=False, frameon=False)
        pyplot.close(fig)

        key_fig.savefig(
            os.path.join(settings.MEDIA_ROOT, settings.KEY_STORAGE_DIR, key_filename),
            dpi=500, bbox_inches='tight', pad_inches=0,
            transparent=True, facecolor=key_fig.get_facecolor())
        pyplot.close(key_fig)

        return plot_filename, key_filename
