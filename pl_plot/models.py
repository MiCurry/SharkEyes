import os
import datetime
from uuid import uuid4
from scipy.io import netcdf_file
import shutil
from django.db import models
from django.utils import timezone
from django.db.models.aggregates import Max
from django.conf import settings
from datetime import timedelta
from celery import group
from celery import shared_task
from pl_download.models import DataFile, DataFileManager
from pl_plot.plotter import Plotter, WaveWatchPlotter, WindPlotter
from pl_plot import plot_functions

HOW_LONG_TO_KEEP_FILES = settings.HOW_LONG_TO_KEEP_FILES
PAST_DAYS_OF_FILES_TO_DISPLAY = settings.PAST_DAYS_OF_FILES_TO_DISPLAY

class OverlayManager(models.Manager):
    @staticmethod
    def get_all_base_definition_ids():
        return OverlayDefinition.objects.values_list('id', flat=True).filter(is_base=True)

    @staticmethod
    def get_newest_untiled_overlay_ids():
        """ Returns the ID of the newest untiled overlay

        This might fail for multiple zoom levels...
        """
        # Assuming newer overlays have higher primary keys. Seems reasonable.
        overlay_definitions = OverlayDefinition.objects.annotate(newest_overlay_id=Max('overlay__id'))
        newest_overlays = Overlay.objects.filter(id__in=[od.newest_overlay_id for od in overlay_definitions])
        return newest_overlays.filter(is_tiled=False).values_list('id', flat=True)

    @classmethod
    def get_next_few_days_of_untiled_overlay_ids(cls):
        """ Creates a list of the ids of unchopped images that have not been tiled.

        :return:List of overlay id's that have been untiled.
        """

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
        """ Gets the next few days of tiled overlays to be displayed on the website. """
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

    @classmethod
    def make_all_base_plots_for_next_few_days(cls):
        job = group(cls.get_tasks_for_base_plots_for_next_few_days())
        results = job.apply_async()
        return results

    @classmethod
    def get_tasks_for_base_plots_in_files(cls, file_ids):
        """ Using a list of the file_ids this function creates a list of tasks to be used by celery. Celery takes
        these tasks and will generate plots automagically!

        :param file_ids: The list of file_ids that plot tasks need to be generated for!
        :return: The task list of plots that need to be done for the future.
        """
        task_list = []

        for fid in file_ids:
            datafile = DataFile.objects.get(pk=fid)

            # Wavewatch and SST/currents files use a separate Plot function.
            if datafile.file.name.startswith(settings.OSU_WW3_DF_FN):
                for t in range(20, 85, 4):
                    # The unchopped file's index starts at noon: index = 0 and progresses throgh 85 forecasts, one per hour,
                    # for the next 85 hours.
                    # Only plot every 4th index to match up with the SST forecast.
                    # WaveWatch has forecasts for every hour but at this time we don't need them all.
                    task_list.append(cls.make_wave_watch_plot.subtask(args=(settings.OSU_WW3_HI, t, fid), immutable=True))
                    task_list.append(cls.make_wave_watch_plot.subtask(args=(settings.OSU_WW3_DIR, t, fid), immutable=True))
            elif datafile.file.name.startswith(settings.NAMS_WIND_DF_FN):
                plotter = WindPlotter(datafile.file.name)
                number_of_times = plotter.get_number_of_model_times()
                wind_values = plotter.get_wind_indices()
                begin = wind_values['begin']
                swap = wind_values['swap']
                three_hour_indices = wind_values['indices']
                for t in range(begin, swap, 4):
                    task_list.append(cls.make_plot.subtask(args=(settings.NAMS_WIND, t, fid), immutable=True))
                for t in range(swap, number_of_times, 1):
                    if t in three_hour_indices:
                        task_list.append(cls.make_plot.subtask(args=(settings.NAMS_WIND, t, fid), immutable=True))
            else:
                plotter = Plotter(datafile.file.name)
                number_of_times = plotter.get_number_of_model_times()

                for t in range(0, number_of_times, 1):
                    if t % 2 != 0:
                        #SST Now has values every 2 hours, but we only want every 4
                        #This only adds the task for every other time stamp
                        #using EXTEND because we are adding multiple items: might also be able to use APPEND
                        task_list.extend(cls.make_plot.subtask(args=(od_id, t, fid),
                                                               immutable=True) for od_id in [settings.OSU_ROMS_SST,
                                                                                             settings.OSU_ROMS_SUR_SAL,
                                                                                             settings.OSU_ROMS_SUR_CUR,
                                                                                             settings.OSU_ROMS_BOT_SAL,
                                                                                             settings.OSU_ROMS_BOT_TEMP,
                                                                                             settings.OSU_ROMS_SSH])
        return task_list

    @classmethod
    def get_tasks_for_base_plots_for_next_few_days(cls):
        """ Grabs the files ID's of NCDF datafiles that haven't been plotted yet. Use this function
        to generate a list of unchopped plots that haven't been plotted yet. """
        file_ids = [datafile.id for datafile in DataFileManager.get_next_few_days_files_from_db()]
        return cls.get_tasks_for_base_plots_in_files(file_ids)

    @classmethod
    def delete_old_files(cls):
        """  Deletes physical overlay files and their database entries that are older then HOW_LONG_TO_KEEP_FILEs """
        how_old_to_keep = timezone.datetime.now()-timedelta(days=HOW_LONG_TO_KEEP_FILES)

        # Overlay items from the database
        old_unchopped_files = Overlay.objects.filter(applies_at_datetime__lte=how_old_to_keep)

        # the Overlay class has a custom delete method that deletes the overlay's
        #TILES, KEYS, and OVERLAY images from the disk.
        for eachfile in old_unchopped_files:
            Overlay.delete(eachfile)

        return True

    @staticmethod
    @shared_task(name='pl_plot.make_wave_watch_plot')
    def make_wave_watch_plot(overlay_definition_id, time_index=0, file_id =None):
        """ Creates an unchopped (un-tiled), plain png, plot for the specified file at the
        specified time_index and the specify overlay definition as well as a database entry for
        that unchopped file and a new tile directory for that particular unchopped png image.

        id  | Name | Model Name | Type
        --- |------|------------|-----
        4 | Wave Height | OSU WW3 | Contour
        6 | Wave Direction & Period | OSU WW3 | Vector

        :param overlay_definition_id: The definition of the function to be plotted. See the table above.
        Ensure overlay_definition_id's corrospond to the correct file type.
        :param time_index: The desired time slice of the file given
        :param file_id: The file id according to the database
        :return: The id of the generated overlay
        """

        zoom_levels_for_direction = [('2-8', 20), ('9-10', 15),  ('11-12', 5)]
        zoom_levels_for_others = [(None, None)]

        overlay_ids = []

        # Grab the latest forecast file
        if file_id is None:
            datafile = DataFile.objects.latest('generated_datetime')
        else:
            datafile = DataFile.objects.get(pk=file_id)

        generated_datetime = datafile.generated_datetime.date().strftime('%m_%d_%Y')

        datafile_read_object = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, datafile.file.name))
        plotter = WaveWatchPlotter(datafile.file.name)

        # Setting the time for applies_at, based on the Time variable in the file.
        # The time variable is # of seconds since start of time epoch, so we convert to UTC
        all_day_times = datafile_read_object.variables['time'][:]
        basetime = datetime.datetime(1970,1,1,0,0,0)  # Jan 1, 1970

        # This is the first forecast: right now it is Noon (UTC) [~5 AM PST] on the day before the file was downloaded
        forecast_zero = basetime + datetime.timedelta(all_day_times[0]/3600.0/24.0,0,0)

        applies_at_datetime = timezone.make_aware(forecast_zero + timedelta(hours=time_index) , timezone.utc)
        overlay_definition = OverlayDefinition.objects.get(pk=overlay_definition_id)

        if overlay_definition_id == settings.OSU_WW3_DIR:
            zoom_levels = zoom_levels_for_direction
        else:
            zoom_levels = zoom_levels_for_others

        # Set a new tile directory name for each forecast_index
        tile_dir = "tiles_{0}_{1}".format(overlay_definition.function_name, uuid4())

        for zoom_level in zoom_levels:
            plot_filename, key_filename = plotter.make_plot(getattr(plot_functions,
                                                                    overlay_definition.function_name),
                                                            forecast_index=time_index,
                                                            storage_dir=settings.UNCHOPPED_STORAGE_DIR,
                                                            generated_datetime=generated_datetime,
                                                            downsample_ratio=zoom_level[1],
                                                            zoom_levels=zoom_level[0])

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
        """ Creates an unchopped (un-tiled), plain png, plot for the specified file at the
        specified time_index and the specify overlay definition as well as a database entry for
        that unchopped file and a new tile directory for that particular unchopped png image.

        Here is a list of the current models that this function is able to plot:

        id  | Name | Model Name | Type
        --- |------|------------|-----
         1 | Sea Surface Tempearture | OSU ROMS | Contour
         2 | Surface Salinity  | OSU ROMS | Contour
         3 | Sea Surface Currents | OSU ROMS | Vector
         5 | Sea Surface Winds | NAMS | Vector (Barbs)
         7 | Bottom Sea Tempearture | OSU ROMS | Contour
         8 | Bottom Salinity | OSU ROMS | Contour
         9 | Sea Surface Height | OSU ROMS | Contour


        :param overlay_definition_id: The definition of the function to be plotted. See the table above.
        Ensure overlay_definition_id's corrospond to the correct file type.
        :param time_index: The desired time slice of the file given
        :param file_id: The file id according to the database
        :return: The id of the generated overlay
        """
        zoom_levels_for_currents = [('2-7', 8),  ('8-12', 4)]
        zoom_levels_for_others = [(None, None)]
        zoom_levels_for_winds = [('1-10', 2), ('11-12', 1)]
        # if file_id is None:
        #     datafile = DataFile.objects.latest('model_date')

        # If plotting winds grab the latest wind file
        if overlay_definition_id == settings.NAMS_WIND:
            datafile = DataFile.objects.filter(type='WIND').latest('model_date')
        else:
            datafile = DataFile.objects.get(pk=file_id)

        # Wind has its own plotter if plotting winds use WindPlotter
        if overlay_definition_id == settings.NAMS_WIND:
            plotter = WindPlotter(datafile.file.name)
        else:
            plotter = Plotter(datafile.file.name)
            #print "time from models = ", plotter.get_time_at_oceantime_index(time_index)

        overlay_definition = OverlayDefinition.objects.get(pk=overlay_definition_id)

        if overlay_definition_id == settings.OSU_ROMS_SUR_CUR:
            zoom_levels = zoom_levels_for_currents
        elif overlay_definition_id == settings.NAMS_WIND:
            zoom_levels = zoom_levels_for_winds
        else:
            zoom_levels = zoom_levels_for_others

        tile_dir = "tiles_{0}_{1}".format(overlay_definition.function_name, uuid4())
        overlay_ids = []

        for zoom_level in zoom_levels:
            plot_filename, key_filename = plotter.make_plot(getattr(plot_functions,
                                                                    overlay_definition.function_name),
                                                            time_index=time_index,
                                                            downsample_ratio=zoom_level[1],
                                                            zoom_levels=zoom_level[0])

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

class Overlay(models.Model):
    definition = models.ForeignKey(OverlayDefinition)
    created_datetime = models.DateTimeField()
    file = models.ImageField(upload_to=settings.UNCHOPPED_STORAGE_DIR, null=True)
    tile_dir = models.CharField(max_length=240, null=True)
    key = models.ImageField(upload_to=settings.KEY_STORAGE_DIR, null=True)
    applies_at_datetime = models.DateTimeField(null=False)
    zoom_levels = models.CharField(max_length=50, null=True)
    is_tiled = models.BooleanField(default=False)


    def delete(self,*args,**kwargs):
        """ Custom delete method which will also delete the Overlay's image file from the disk and also the Key image
        and Tiles
        """
        #Delete the physical file from disk
        if os.path.isfile(self.file.path):
            os.remove(self.file.path)

        #Delete the Key image
        if os.path.isfile(self.key.path):
            #The wind barb key is static. We don't want to delete it.
            if self.key.path != '/opt/sharkeyes/media/keys/barbKey.png':
                os.remove(self.key.path)

        directory=os.path.join('/opt/sharkeyes/media/tiles/', self.tile_dir)

        # TILES folder holds directories only. There are no Tile items in the database so we don't have to delete those.
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
