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
from pl_plot.plotter import Plotter, TClinePlotter
from pl_plot.plotter import HycomPlotter, NavyPlotter
from pl_plot.plotter import WaveWatchPlotter, NcepWW3Plotter
from pl_plot.plotter import WindPlotter
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
    def get_next_few_days_of_tiled_overlays(cls, models, is_tiled=True, is_extend=False, future_files=11, past_files=PAST_DAYS_OF_FILES_TO_DISPLAY):
        """
        TODO: Update DocString for this function


        :param models:
        :param is_tiled:
        :param is_extend:
        :param future_files:
        :param past_files:
        :return: A list of overlay objects
        """
        display = Overlay.objects.none()

        # know what dates to look for
        dates = Overlay.objects.filter(applies_at_datetime__gte=timezone.now()-timedelta(days=past_files),
                                       applies_at_datetime__lte=timezone.now()+timedelta(days=future_files),
                                       is_tiled=is_tiled,
                                       is_extend=is_extend,
                                       ).values_list('applies_at_datetime', flat=True).distinct()

        return cls.grab_tiled_overlays_from_dates(dates, models, is_tiled=is_tiled)

    @classmethod
    def get_next_few_days_of_tiled_overlays_for_extended_forecasts(cls, type, models, is_tiled=True, is_extend=True):
        """
        TODO: Update Docstring for this fucntion
        :param type:
        :param models:
        :param is_tiled:
        :param is_extend:
        :return: TODO: Find out exactly what this function returns
        """
        extend_date = None
        if type == 'NCEP':
            extend_date = DataFileManager.get_last_forecast_for_osu_ww3()
            ids = [settings.OSU_WW3_HI, settings.OSU_WW3_DIR]
        elif type == 'NCDF':
            extend_date = DataFileManager.get_last_forecast_for_roms()
            ids = [settings.OSU_ROMS_SST, settings.OSU_ROMS_SUR_CUR]
        else:
            print "Wrong type! Returning!"
            return -1

        dates = []

        for id in ids: # Grab the dates based on the extend date found above
            dates = Overlay.objects.filter(applies_at_datetime__gte=extend_date,
                                           is_tiled=True,
                                           is_extend=True,
                                           definition_id=id
                                           ).values_list('applies_at_datetime', flat=True).distinct()

        
        return cls.grab_tiled_overlays_from_dates(dates, models, is_tiled=is_tiled, is_extend=is_extend)

    @classmethod
    def grab_tiled_overlays_from_dates(cls, dates, models, is_tiled=True, is_extend=False):
        """
        TODO: UPDATE DOC STRING FOR THIS FUNCTION
        :param dates:
        :param models:
        :param is_tiled:
        :param is_extend:
        :return: TODO: Find out exactly what this function returns
        """
        display = Overlay.objects.none()
        for d in dates:
            over = Overlay.objects.filter(applies_at_datetime=d, is_tiled=is_tiled, is_extend=is_extend)
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
            # OSU WW3
            if datafile.file.name.startswith(settings.OSU_WW3_DF_FN):
                # The unchopped file's index starts at noon: index = 0 and progresses throgh 85 forecasts, one per hour,
                # for the next 85 hours.
                # Only plot every 4th index to match up with the SST forecast.
                # WaveWatch has forecasts for every hour but at this time we don't need them all.
                for t in xrange(0, 85):
                    if t % 4 == 0:
                        task_list.append(cls.make_wave_watch_plot.subtask(args=(settings.OSU_WW3_HI, t, fid), immutable=True))
                        task_list.append(cls.make_wave_watch_plot.subtask(args=(settings.OSU_WW3_DIR, t, fid), immutable=True))

            # Wind
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

            # NCEP WW3
            elif datafile.file.name.startswith(settings.NCEP_WW3_DF_FN):
                print "NCEP"
                plotter = NcepWW3Plotter(datafile.file.name)
                for t in xrange(plotter.get_number_of_model_times()):
                    task_list.append(cls.make_wave_watch_plot.subtask(args=(settings.NCEP_WW3_DIR, t, fid), immutable=True))
                    task_list.append(cls.make_wave_watch_plot.subtask(args=(settings.NCEP_WW3_HI, t, fid), immutable=True))

            # NAVY Hycom
            elif datafile.file.name.startswith(settings.NAVY_HYCOM_DF_FN):
                plotter = HycomPlotter(datafile.file.name)
                t = plotter.get_number_of_model_times()

                # TODO: Need to update this to match what each file is saved for
                if datafile.file.name.endswith("ssh.nc"): # Sea Surface Height
                    #task_list.append(cls.make_plot.subtask(args=(settings.NAVY_HYCOM_SSH, t, fid), immutable=True))
                    pass
                if datafile.file.name.endswith("temp_top.nc"): # Temperature Top
                    task_list.append(cls.make_plot.subtask(args=(settings.NAVY_HYCOM_SST, t, fid), immutable=True))
                    #task_list.append(cls.make_plot.subtask(args=(settings.NAVY_HYCOM_SUR_SAL, t, fid), immutable=True))
                if datafile.file.name.endswith("temp_bot.nc"): # Temperature Bot
                    #task_list.append(cls.make_plot.subtask(args=(settings.NAVY_HYCOM_BOT_TEMP, t, fid), immutable=True))
                    #task_list.append(cls.make_plot.subtask(args=(settings.NAVY_HYCOM_BOT_SAL, t, fid), immutable=True))
                    pass
                if datafile.file.name.endswith("cur_top.nc"): # Current Top
                    task_list.append(cls.make_plot.subtask(args=(settings.NAVY_HYCOM_SUR_CUR, t, fid), immutable=True))
                if datafile.file.name.endswith("cur_bot.nc"): # Current Bot
                    #task_list.append(cls.make_plot.subtask(args=(settings.NAVY_HYCOM_BOT_CUR, t, fid), immutable=True))
                    pass

            # OSU_ROMS
            elif datafile.file.name.startswith(settings.OSU_ROMS_DF_FN):
                plotter = Plotter(datafile.file.name)
                number_of_times = plotter.get_number_of_model_times()

                for t in xrange(number_of_times):
                    #SST Now has values every 2 hours, but we only want every 4
                    #This only adds the task for every other time stamp
                    if t % 2 != 0:
                        #using EXTEND because we are adding multiple items: might also be able to use APPEND
                        task_list.extend(cls.make_plot.subtask(args=(od_id, t, fid),
                                                               immutable=True) for od_id in [settings.OSU_ROMS_SST,
                                                                                             settings.OSU_ROMS_SUR_SAL,
                                                                                             settings.OSU_ROMS_SUR_CUR,
                                                                                             settings.OSU_ROMS_BOT_SAL,
                                                                                             settings.OSU_ROMS_BOT_TEMP,
                                                                                             settings.OSU_ROMS_SSH])
            # OSU T-Cline
            elif datafile.file.name.startswith(settings.OSU_TCLINE_DF_FN):
                plotter = TClinePlotter(datafile.file.name)
                number_of_times = plotter.get_number_of_model_times()
                for t in range(0, number_of_times, 1):
                    task_list.append(cls.make_plot.subtask(args=(settings.OSU_TCLINE, t, fid), immutable=True))
            else:
                print "OverlayManager.get_task_for_base_plots_in_files: NOT A FORECAST I RECOGNIZE"

        return task_list

    @classmethod
    def get_tasks_for_base_plots_for_next_few_days(cls):
        """ Grabs the files ID's of NCDF datafiles that haven't been plotted yet. Use this function
        to generate a list of unchopped plots that haven't been plotted yet. """

        file_ids = []
        file_ids.append(DataFileManager.get_next_few_datafiles_of_a_type('NCDF')) # OSU ROMS
        file_ids.append(DataFileManager.get_next_few_datafiles_of_a_type('T-CLINE')) # T-Cline
        file_ids.append(DataFileManager.get_next_few_datafiles_of_a_type('NCEP')) # Wave Forecast
        file_ids.append(DataFileManager.get_next_few_datafiles_of_a_type('WIND')) # Wind

        file_ids = [item for sublist in file_ids for item in sublist] # Unravel lists of lists

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
    def make_wave_watch_plot(overlay_id, time_index=0, file_id=None):
        """ Make a wave watch plot for either NCEP WW3 or OSU WW3.

        :param overlay_id: The id of the model to be plotted. See pl_plot_defintions
        :param time_index: The time index to plot in steps (ints)
        :param file_id: The id of the file to be used to generate the plot
        :return: A list of the generated Overaly ID's
        """
        overlay_ids = []
        extend_bool = False


        """ For vector fields we need to produce plots at different 'zoom levels' so when users zoom in 
        they domain is filled with more vectors. Likewise when they zoom out they should see less. """

        if overlay_id in settings.OSU_WW3:
            if file_id is None:
                datafile = DataFile.objects.filter(type='WAVE').latest('model_date')
            else:
                datafile = DataFile.objects.get(pk=file_id)
            plotter = WaveWatchPlotter(datafile.file.name)
            zoom_levels = plotter.get_zoom_level(overlay_id)
        elif overlay_id in settings.NCEP_WW3:
            if file_id is None:
                datafile = DataFile.objects.filter(type='NCEP_WW3').latest('model_date')
            else:
                datafile = DataFile.objects.get(pk=file_id)
            plotter = NcepWW3Plotter(datafile.file.name)
            zoom_levels = plotter.get_zoom_level(overlay_id)
            extend_bool = False


        generated_datetime = DataFile.objects.get(pk=file_id).generated_datetime.date().strftime('%m_%d_%Y')
        applies_at_datetime = plotter.get_oceantime(time_index)
        overlay_definition = OverlayDefinition.objects.get(pk=overlay_id)


        tile_dir = "tiles_{0}_{1}".format(overlay_definition.function_name, uuid4())

        for zoom_level in zoom_levels:
            plot_filename, key_filename = plotter.make_plot(getattr(plot_functions, overlay_definition.function_name),
                                                            forecast_index=time_index, storage_dir=settings.UNCHOPPED_STORAGE_DIR,
                                                            generated_datetime=generated_datetime, downsample_ratio=zoom_level[1],
                                                            zoom_levels=zoom_level[0])



            ''' Here we are changing the overlay_id number of forecasted models to be that of the corresponding
                base foreacast overlay_id.
                
                That way when SharkEyesCore.views creates the list of overlays, it grabs the base forecast and
                appends the extended one to the end as if the extended forecasts were part of the base forecast. '''
            # Extended Forecasts
            if settings.EXTEND:
                if overlay_id == settings.NCEP_WW3_DIR:
                    overlay_id = settings.OSU_WW3_DIR
                if overlay_id == settings.NCEP_WW3_HI:
                    overlay_id = settings.OSU_WW3_HI
            if not settings.EXTEND: # Nice for testing the views of the tiled models
                extend_bool = False

            overlay = Overlay(
                file=os.path.join(settings.UNCHOPPED_STORAGE_DIR, plot_filename),
                key=os.path.join(settings.KEY_STORAGE_DIR, key_filename),
                created_datetime=timezone.now(),  #saves UTC correctly in database
                applies_at_datetime=applies_at_datetime,
                tile_dir = tile_dir,
                zoom_levels = zoom_level[0],
                is_tiled = False,
                is_extend= extend_bool,
                definition_id=overlay_id,
            )
            overlay.save()
            overlay_ids.append(overlay.id)
        return overlay_ids

    @staticmethod
    @shared_task(name='pl_plot.make_plot')
    def make_plot(overlay__id, time_index=0, file_id=None):
        """ Creates an unchopped (un-tiled), plain png, plot for the specified file at the
        specified time_index and the specify overlay definition as well as a database entry for
        that unchopped file and a new tile directory for that particular unchopped png image.

        Here is a list of the current models that this function is able to plot:

         id |        Name             | Model Name | Type
         -- |-------------------------|------------|-----
         1  | Sea Surface Tempearture | OSU ROMS   | Contour
         2  | Surface Salinity        | OSU ROMS   | Contour
         3  | Sea Surface Currents    | OSU ROMS   | Vector
         5  | Sea Surface Winds       | NAMS       | Vector (Barbs)
         7  | Bottom Sea Tempearture  | OSU ROMS   | Contour
         8  | Bottom Salinity         | OSU ROMS   | Contour
         9  | Sea Surface Height      | OSU ROMS   | Contour
         12 | HYCOM Sea Surface Temp  | NCEP       | Contour
         13 | HYCOM Sea Surface Cur   | NCEP       | Vector


        :param overlay__id: The definition of the function to be plotted. See the table above.
        Ensure overlay_definition_id's corrospond to the correct file type.
        :param time_index: The desired time slice of the file given
        :param file_id: The file id according to the database
        :return: The id of the generated overlay
        """

        extend_bool = False
        overlay_definition = OverlayDefinition.objects.get(pk=overlay__id)

        if overlay__id in settings.OSU_ROMS:
            if file_id is None:
                datafile = DataFile.objects.filter(type='NCDF').latest('model_date')
            else:
                datafile = DataFile.objects.get(pk=file_id)
            plotter = Plotter(datafile.file.name)
            zoom_levels = plotter.get_zoom_level(overlay__id)

        elif overlay__id in settings.HYCOM:
            print "RTOFS HYCOM"
            if file_id is None:
                datafile = DataFile.objects.filter(type='HYCOM').latest('model_date')
            else:
                datafile = DataFile.objects.get(pk=file_id)
            plotter = HycomPlotter(datafile.file.name)
            zoom_levels = plotter.get_zoom_level(overlay__id)

        elif overlay__id == settings.NAMS_WIND:
            if file_id is None:
                datafile = DataFile.objects.filter(type='WIND').latest('model_date')
            else:
                datafile = DataFile.objects.get(pk=file_id)
            plotter = WindPlotter(datafile.file.name)
            zoom_levels = plotter.get_zoom_level(overlay__id)

        elif overlay__id in settings.NAVY_HYCOM:
            print "NAVY HYCOM"
            if file_id is None:
                datafile = DataFile.objects.filter(type='HYCOM').latest('model_date')
            else:
                datafile = DataFile.objects.get(pk=file_id)
            plotter = NavyPlotter(datafile.file.name)
            zoom_levels = plotter.get_zoom_level(overlay__id)
            extend_bool = True

        elif overlay__id == settings.OSU_TCLINE:
            if file_id is None:
                datafile = DataFile.objects.filter(type='T-CLINE').latest('model_date')
            else:
                datafile = DataFile.objects.get(pk=file_id)
            plotter = TClinePlotter(datafile.file.name)
            zoom_levels = plotter.get_zoom_level(overlay__id)


        tile_dir = "tiles_{0}_{1}".format(overlay_definition.function_name, uuid4())
        overlay_ids = []

        for zoom_level in zoom_levels:
            plot_filename, key_filename = plotter.make_plot(getattr(plot_functions,
                                                                    overlay_definition.function_name),
                                                            time_index=time_index,
                                                            downsample_ratio=zoom_level[1],
                                                            zoom_levels=zoom_level[0])

            ''' Here we are changing the overlay_id number of forecasted models to be that of the corresponding
                base foreacast overlay_id.
                
                That way when SharkEyesCore.views creates the list of overlays, it grabs the base forecast and
                appends the extended one to the end as if the extended forecasts were part of the base forecast. '''
            # Extended Forecasts
            if settings.EXTEND:
                if overlay__id == settings.NAVY_HYCOM_SST:
                    overlay__id = settings.OSU_ROMS_SST
                elif overlay__id == settings.NAVY_HYCOM_SUR_CUR:
                    overlay__id = settings.OSU_ROMS_SUR_CUR
            if not settings.EXTEND: # Nice for testing the views of the tiled models
                extend_bool = False

            overlay = Overlay(
                file=os.path.join(settings.UNCHOPPED_STORAGE_DIR, plot_filename),
                key=os.path.join(settings.KEY_STORAGE_DIR, key_filename),
                created_datetime=timezone.now(),
                definition_id=overlay__id,
                applies_at_datetime=plotter.get_time_at_oceantime_index(time_index),
                zoom_levels=zoom_level[0],
                tile_dir=tile_dir,
                is_tiled=False,
                is_extend=extend_bool
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
    is_extend = models.BooleanField(default=False)


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
