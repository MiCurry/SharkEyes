from django.db import models
import os
from celery import group
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from pl_plot import plot_functions
from pl_plot.plotter import Plotter, WaveWatchPlotter, WindPlotter
from pl_download.models import DataFile, DataFileManager
from django.db.models.aggregates import Max
from uuid import uuid4
from scipy.io import netcdf_file
import numpy
import shutil
import numpy as np
import datetime
from django.conf import settings

# This is how long old files (overlay items in the database, and corresponding items in UNCHOPPED folder)
HOW_LONG_TO_KEEP_FILES = settings.HOW_LONG_TO_KEEP_FILES

#This is how many days' worth of older forecasts to display
PAST_DAYS_OF_FILES_TO_DISPLAY = settings.PAST_DAYS_OF_FILES_TO_DISPLAY

class OverlayManager(models.Manager):
    @staticmethod
    def get_all_base_definition_ids():
        return OverlayDefinition.objects.values_list('id', flat=True).filter(is_base=True)

    # Team 1 says: todo this will fail for multiple zoom levels
    @staticmethod
    def get_newest_untiled_overlay_ids():
        # assuming newer overlays have higher primary keys. Seems reasonable.
        overlay_definitions = OverlayDefinition.objects.annotate(newest_overlay_id=Max('overlay__id'))
        newest_overlays = Overlay.objects.filter(id__in=[od.newest_overlay_id for od in overlay_definitions])
        return newest_overlays.filter(is_tiled=False).values_list('id', flat=True)

    @classmethod
    def get_next_few_days_of_untiled_overlay_ids(cls):
        # starts with "present" overlay, which is the closest to now, forward or backwards, and goes forward 4 days or
        # however far we have data, whichever is less
        # here assuming that the primary keys for the overlays are only monotonically increasing
        # and that the newer one is better.

        next_few_days_of_overlays = Overlay.objects.filter(
            applies_at_datetime__gte=timezone.now()-timedelta(days=PAST_DAYS_OF_FILES_TO_DISPLAY),
            applies_at_datetime__lte=timezone.now()+timedelta(days=4)
        )
        and_the_newest_for_each = next_few_days_of_overlays.values('definition', 'applies_at_datetime', 'zoom_levels')\
            .annotate(newest_id=Max('id'))
        that_are_not_tiled = and_the_newest_for_each.filter(is_tiled=False)
        ids_of_these = that_are_not_tiled.values_list('newest_id', flat=True)
        return ids_of_these

    @classmethod
    def get_next_few_days_of_tiled_overlays(cls, models=[1]):
        # return all the desired entries from database using this variable
        display = Overlay.objects.none()
        # know what dates to look for
        dates = Overlay.objects.filter(applies_at_datetime__gte=timezone.now()-timedelta(days=PAST_DAYS_OF_FILES_TO_DISPLAY),
                                       applies_at_datetime__lte=timezone.now()+timedelta(days=4),
                                       is_tiled=True
                                       ).values_list('applies_at_datetime', flat=True).distinct()

        for d in dates:
            over = Overlay.objects.filter(applies_at_datetime = d, is_tiled=True)
            for m in models:
                tile = over.filter(definition_id=m)
                gen = tile.aggregate(Max('created_datetime'))['created_datetime__max']
                if gen == None:
                    continue
                else:
                    gen = gen - timedelta(days=1)
                    add = tile.filter(created_datetime__gte=gen)
                    display = display | add
        return display

    # these are for getting and running task groups
    @classmethod
    def make_all_base_plots_for_next_few_days(cls):
        job = group(cls.get_tasks_for_base_plots_for_next_few_days())
        results = job.apply_async()
        return results

    @classmethod
    def get_tasks_for_all_base_plots(cls, time_index=0, file_id=None):
        #Add the SST and currents plot commands
        task_list = [cls.make_plot.s(od_id, time_index, file_id, immutable=True) for od_id in [1, 3]]
        #add the wind task(5)
        task_list.append(cls.make_plot.s(5, time_index, file_id, immutable=True))
        #Add the commands to plot wave Height (4) and Direction (6)
        task_list.append(cls.make_wave_watch_plot.s(4, time_index, file_id, immutable=True))
        task_list.append(cls.make_wave_watch_plot.s(6, time_index, file_id, immutable=True))
        job = task_list
        return job

#PASSING IN: the file IDs of all the DataFiles stored in the database for next few days of forecasts.
    @classmethod
    def get_tasks_for_base_plots_in_files(cls, file_ids):
        task_list = []

        for fid in file_ids:
            datafile = DataFile.objects.get(pk=fid)

            #Wavewatch and SST/currents files use a separate Plot function.
            if datafile.file.name.startswith("OuterGrid"):
                #plotter = WaveWatchPlotter(datafile.file.name)
                for t in xrange(0, 85):
                    # The unchopped file's index starts at noon: index = 0 and progresses throgh 85 forecasts, one per hour,
                    # for the next 85 hours.
                    # Only plot every 4th index to match up with the SST forecast.
                    # WaveWatch has forecasts for every hour but at this time we don't need them all.
                    if t % 4 == 0:
                        task_list.append(cls.make_wave_watch_plot.subtask(args=(4, t, fid), immutable=True))
                        task_list.append(cls.make_wave_watch_plot.subtask(args=(6, t, fid), immutable=True))
            elif datafile.file.name.startswith("WIND"):
                plotter = WindPlotter(datafile.file.name)
                number_of_times = plotter.get_number_of_model_times()
                for t in xrange(number_of_times):
                    task_list.append(cls.make_plot.subtask(args=(5, t, fid), immutable=True))
            else:
                plotter = Plotter(datafile.file.name)
                number_of_times = plotter.get_number_of_model_times()

                for t in xrange(number_of_times):
                    #SST Now has values every 2 hours, but we only want every 4
                    #This only adds the task for every other time stamp
                    if t % 2 != 0:
                        #using EXTEND because we are adding multiple items: might also be able to use APPEND
                        task_list.extend(cls.make_plot.subtask(args=(od_id, t, fid), immutable=True) for od_id in [1, 3])
        return task_list

    @classmethod
    def get_tasks_for_base_plots_for_next_few_days(cls):
        file_ids = [datafile.id for datafile in DataFileManager.get_next_few_days_files_from_db()]
        return cls.get_tasks_for_base_plots_in_files(file_ids)

    @classmethod
    def delete_old_files(cls):
        how_old_to_keep = timezone.datetime.now()-timedelta(days=HOW_LONG_TO_KEEP_FILES)

        # Overlay items from the database
        old_unchopped_files = Overlay.objects.filter(applies_at_datetime__lte=how_old_to_keep)

        # the Overlay class has a custom delete method that deletes the overlay's
        #TILES, KEYS, and OVERLAY images from the disk.
        for eachfile in old_unchopped_files:
            Overlay.delete(eachfile)

        return True

#Development function: Not used during normal operation
#--------------------------------------------------------------------------------------------------------
    @staticmethod
    def get_currents_data(forecast_index, file_id):
        datafile = DataFile.objects.get(pk=file_id)
        data_file = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR, datafile.file.name))
        currents_u = data_file.variables['u'][forecast_index][39]
        currents_v = data_file.variables['v'][forecast_index][39]

        print "currents u:", 10.0*currents_u
        print "\n\n\ncurrents v:", 10.0*currents_v

#Development function: Not used during normal operation
#--------------------------------------------------------------------------------------------------------
# Just a helper function so that you can examine the first forecast (latitude, longitude, and wave height)
# from the NetCDF file. Pass in the file id of the WaveWatch NetCDF file you want to plot.
    @staticmethod
    def get_data(forecast_index, file_id):
        datafile = DataFile.objects.get(pk=file_id)
        file = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, datafile.file.name))
        variable_names_in_file = file.variables.keys()
        print variable_names_in_file

        all_day_height = file.variables['HTSGW_surface'][:, :, :]
        all_day_direction = file.variables['DIRPW_surface'][:,:,:]
        all_day_lat = file.variables['latitude'][:, :]
        all_day_long = file.variables['longitude'][:, :]
        all_day_times = file.variables['time'][:]
        #print "times: "
        #for each in all_day_times:
            #print each

        basetime = datetime.datetime(1970,1,1,0,0,0)

        # Check the first value of the forecast
        forecast_zero = basetime + datetime.timedelta(all_day_times[0]/3600.0/24.0,0,0)
        print(forecast_zero)

        directions = all_day_direction[forecast_index, ::10, :]
        directions_mod = 90.0 - directions + 180.0
        index = directions_mod > 180
        directions_mod[index] = directions_mod[index] - 360;

        index = directions_mod < -180;
        directions_mod[index] = directions_mod[index] + 360;

        U = 10.*np.cos(np.deg2rad(directions_mod))
        V = 10.*np.sin(np.deg2rad(directions_mod))

        print "height:", all_day_height[:10, :10]

#Development function: Not used during normal operation
#--------------------------------------------------------------------------------------------------------
    @staticmethod
    def get_period_data(forecast_index, file_id):
        datafile = DataFile.objects.get(pk=file_id)
        file = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, datafile.file.name))
        variable_names_in_file = file.variables.keys()
        print variable_names_in_file

        all_day_period = file.variables['PERPW_surface'][forecast_index][:,:]
        print "Period of waves, in seconds:", all_day_period

#Helper function to view the variable names from a generic NetCDF file such as NASA's Altimetry data.
#Not used during normal operation
#--------------------------------------------------------------------------------------------------------
    @staticmethod
    def get_alt_data():
        # This assumes that you have a NetCDF file names JA2...nc in your Media directory on your local machine.
        file = netcdf_file(os.path.join(settings.MEDIA_ROOT, 'JA2_GPSOPR_2PdS178_070_20130504_194255_20130504_211615.nc'))
        variable_names_in_file = file.variables.keys()
        print "variables: ", variable_names_in_file

        # I assume this is the altimetry, but am not sure what units it is in.
        data = file.variables['alt'][:10]
        sea_surface = file.variables['mean_sea_surface'][:10]
        bathymetry = data = file.variables['bathymetry'][:10]
        print data
        print sea_surface
        print bathymetry

#Development function: Not used during normal operation
#--------------------------------------------------------------------------------------------------------
    @staticmethod
    def time_help():
         print "timezone:", timezone.get_current_timezone()
         print "zone now: ", timezone.get_current_timezone()
         print "local time now:", timezone.localtime(timezone.now())  #this prints current PST time, with DST correct
         print "timezone now:", timezone.make_aware(timezone.now() , timezone.utc)  #this is the UTC version of right-now's time
         print "", timezone.is_naive(timezone.localtime(timezone.now()))

    @staticmethod
    @shared_task(name='pl_plot.make_wave_watch_plot')
    def make_wave_watch_plot(overlay_definition_id, time_index=0, file_id =None):

        zoom_levels_for_direction = [('2-8', 20), ('9-10', 15),  ('11-12', 5)]
        zoom_levels_for_others = [(None, None)]

        overlay_ids = []

        #grab the latest forecast file
        if file_id is None:
            datafile = DataFile.objects.latest('generated_datetime')
        else:
            datafile = DataFile.objects.get(pk=file_id)

        overlay_definition = OverlayDefinition.objects.get(pk=overlay_definition_id)

        generated_datetime = datafile.generated_datetime.date().strftime('%m_%d_%Y')

        #get the the number of forecasts contained in the netCDF
        datafile_read_object = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, datafile.file.name))
        all_forecasts = datafile_read_object.variables['HTSGW_surface'][:, :, :]

        #obtain how many forecast are contained in the netcdf
        #as of right now there are 85
        lengths = numpy.shape(all_forecasts)
        number_of_forecasts = lengths[0] #netCDF gives a 3D array (number of forecasts, latitudes, longitudes)

        #returns a netcdf file object with read mode
        plotter = WaveWatchPlotter(datafile.file.name)

        # Setting the time for applies_at, based on the Time variable in the file.
        # The time variable is # of seconds since start of time epoch, so we convert to UTC
        all_day_times = datafile_read_object.variables['time'][:]
        basetime = datetime.datetime(1970,1,1,0,0,0)  # Jan 1, 1970

        # This is the first forecast: right now it is Noon (UTC) [~5 AM PST] on the day before the file was downloaded
        forecast_zero = basetime + datetime.timedelta(all_day_times[0]/3600.0/24.0,0,0)

        # Based on the time index, say that this date is UTC (make_aware)
        applies_at_datetime = timezone.make_aware(forecast_zero + timedelta(hours=time_index) , timezone.utc)

        #Set a new tile directory name for each forecast_index
        tile_dir = "tiles_{0}_{1}".format(overlay_definition.function_name, uuid4())

        #return overlaydefinition object; 4 is for wave height, 6 for wave direction, 7 for wave period
        overlay_definition = OverlayDefinition.objects.get(pk=overlay_definition_id)

        if overlay_definition_id == 6:
            zoom_levels = zoom_levels_for_direction

        else:
            zoom_levels = zoom_levels_for_others

        tile_dir = "tiles_{0}_{1}".format(overlay_definition.function_name, uuid4())

        for zoom_level in zoom_levels:
            plot_filename, key_filename = plotter.make_plot(getattr(plot_functions, overlay_definition.function_name),
                        forecast_index=time_index, storage_dir=settings.UNCHOPPED_STORAGE_DIR,
                        generated_datetime=generated_datetime, downsample_ratio=zoom_level[1], zoom_levels=zoom_level[0])

            overlay = Overlay(
                file=os.path.join(settings.UNCHOPPED_STORAGE_DIR, plot_filename),
                key=os.path.join(settings.KEY_STORAGE_DIR, key_filename),
                created_datetime=timezone.now(),  #saves UTC correctly in database
                applies_at_datetime=applies_at_datetime,
                tile_dir = tile_dir,
                zoom_levels = zoom_level[0],
                is_tiled = False,
                definition_id=overlay_definition_id,
            )
            overlay.save()
            overlay_ids.append(overlay.id)

        # This code is used to view what is contained in the netCDF file
        # file = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, datafile.file.name))
        # variable_names_in_file = file.variables.keys()
        # print variable_names_in_file
        # This prints all the wave height data
        # file.variables['HTSGW_surface'][:]
        # This prints the dimensions of the wave height data
        # value = numpy.shape(file.variables['HTSGW_surface'][:])
        return overlay_ids

    @staticmethod
    @shared_task(name='pl_plot.make_plot')
    def make_plot(overlay_definition_id, time_index=0, file_id=None):
        zoom_levels_for_currents = [('2-7', 8),  ('8-12', 4)]
        zoom_levels_for_others = [(None, None)]
        zoom_levels_for_winds = [('1-10', 2), ('11-12', 1)]
        if file_id is None:
            datafile = DataFile.objects.latest('model_date')

        #If plotting winds grab the latest wind file
        #-------------------------------------------------------------------------
        elif overlay_definition_id == 5:
            datafile = DataFile.objects.filter(type='WIND').latest('model_date')
        else:
            datafile = DataFile.objects.get(pk=file_id)

        #Wind has its own plotter if plotting winds use WindPlotter
        #-------------------------------------------------------------------------
        if overlay_definition_id == 5:
            plotter = WindPlotter(datafile.file.name)
        else:
            plotter = Plotter(datafile.file.name)

        overlay_definition = OverlayDefinition.objects.get(pk=overlay_definition_id)

        if overlay_definition_id == 3:
            zoom_levels = zoom_levels_for_currents
        elif overlay_definition_id == 5:
            zoom_levels = zoom_levels_for_winds
        else:
            zoom_levels = zoom_levels_for_others

        tile_dir = "tiles_{0}_{1}".format(overlay_definition.function_name, uuid4())
        overlay_ids = []
        for zoom_level in zoom_levels:
            # Make a plot with downsampling of 4, and with 2
            plot_filename, key_filename = plotter.make_plot(getattr(plot_functions, overlay_definition.function_name),
                                                            time_index=time_index, downsample_ratio=zoom_level[1], zoom_levels=zoom_level[0])

            overlay = Overlay(
                file=os.path.join(settings.UNCHOPPED_STORAGE_DIR, plot_filename),
                key=os.path.join(settings.KEY_STORAGE_DIR, key_filename),
                created_datetime=timezone.now(),
                definition_id=overlay_definition_id,
                applies_at_datetime=plotter.get_time_at_oceantime_index(time_index),
                zoom_levels=zoom_level[0],
                tile_dir=tile_dir,
                is_tiled=False
            )
            overlay.save()
            overlay_ids.append(overlay.id)
        return overlay_ids


class OverlayDefinition(models.Model):
    OVERLAY_TYPES = (
        ('V', 'Vector'),
        ('FC', 'Filled Contour'),
    )
    type = models.CharField(max_length=4, choices=OVERLAY_TYPES)
    display_name_long = models.CharField(max_length=240, unique=True)
    display_name_short = models.CharField(max_length=64)
    function_name = models.CharField(max_length=64, unique=True)
    is_base = models.BooleanField(default=False)
    forecast = models.IntegerField(default=0)


# this acts as a dictionary for the definition, so we can provide additional parameters.
class Parameters(models.Model):
    definition = models.ForeignKey(OverlayDefinition)
    key = models.CharField(max_length=240)
    value = models.CharField(max_length=240)


class Overlay(models.Model):
    definition = models.ForeignKey(OverlayDefinition)
    created_datetime = models.DateTimeField()
    file = models.ImageField(upload_to=settings.UNCHOPPED_STORAGE_DIR, null=True)
    tile_dir = models.CharField(max_length=240, null=True)
    key = models.ImageField(upload_to=settings.KEY_STORAGE_DIR, null=True)
    applies_at_datetime = models.DateTimeField(null=False)
    zoom_levels = models.CharField(max_length=50, null=True)
    is_tiled = models.BooleanField(default=False)

    #Custom delete method which will also delete the Overlay's image file from the disk and also the Key image and Tiles
    def delete(self,*args,**kwargs):

        #Delete the physical file from disk
        if os.path.isfile(self.file.path):
            os.remove(self.file.path)

        #Delete the Key image
        if os.path.isfile(self.key.path):
            os.remove(self.key.path)

        directory=os.path.join('/opt/sharkeyes/media/tiles/', self.tile_dir)

        #TILES folder holds directories only. There are no Tile items in the database so we don't have to delete those.
        # Reference here:  http://stackoverflow.com/questions/2237909/delete-old-directories-in-python
        for r,d,f in os.walk(directory):
            for direc in d:
                try:
                    #delete the items recursively
                    shutil.rmtree(os.path.join(r, direc))

                except Exception,e:
                    print e
                    pass
        #then remove the tile directory itself
        try:
            shutil.rmtree(directory)

        except Exception,e:
            print e
            pass

        #Delete the actual model instance from the database
        super(Overlay, self).delete(*args,**kwargs)

# Function defined to allow dynamic path creation
# A new folder is created per forecast creation day that includes all the forecasts
def get_upload_path(instance,filename):
    return os.path.join(
        settings.WAVE_WATCH_STORAGE_DIR + "/" + "Wave_Height_Forecast_" + instance.created_datetime)

