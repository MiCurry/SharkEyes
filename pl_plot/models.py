from django.db import models
from django.core.files.storage import FileSystemStorage
from django.core.files import File
import os
from django.conf import settings
from celery import group
from datetime import datetime, time, tzinfo, timedelta
from django.utils import timezone
from celery import shared_task
from pl_plot import plot_functions
from pl_plot.plotter import Plotter
from pl_download.models import DataFile, DataFileManager
from django.db.models.aggregates import Max


class OverlayManager(models.Manager):
    @staticmethod
    def get_all_base_definition_ids():
        return OverlayDefinition.objects.values_list('id', flat=True).filter(is_base=True)

    @staticmethod
    def get_newest_untiled_overlay_ids():
        # assuming newer overlays have higher primary keys. Seems reasonable.
        overlay_definitions = OverlayDefinition.objects.annotate(newest_overlay_id=Max('overlay__id'))
        newest_overlays = Overlay.objects.filter(id__in=[od.newest_overlay_id for od in overlay_definitions])
        return newest_overlays.filter(tile_dir__isnull=True).values_list('id', flat=True)

    @classmethod
    def get_next_few_days_of_untiled_overlay_ids(cls):
        # starts with "current" overlay, which is the closest to now, forward or backwards, and goes forward 4 days or
        # however far we have data, whichever is less
        # here assuming that the primary keys for the overlays are only monotonically increasing
        # and that the newer one is better.

        next_few_days_of_overlays = Overlay.objects.filter(
            applies_at_datetime__gte=timezone.now()-timedelta(hours=2),
            applies_at_datetime__lte=timezone.now()+timedelta(days=4)
        )
        that_are_not_tiled = next_few_days_of_overlays.filter(tile_dir__isnull=True)
        and_the_newest_for_each = that_are_not_tiled.values('definition', 'applies_at_datetime').annotate(newest_id=Max('id'))
        ids_of_these = and_the_newest_for_each.values_list('newest_id', flat=True)
        return ids_of_these

    @classmethod
    def get_next_few_days_of_tiled_overlays(cls):
        # starts with "current" overlay, which is the closest to now, forward or backwards, and goes forward 4 days or
        # however far we have data, whichever is less
        # here assuming that the primary keys for the overlays are only monotonically increasing
        # and that the newer one is better.

        next_few_days_of_overlays = Overlay.objects.filter(
            applies_at_datetime__gte=timezone.now()-timedelta(hours=2),
            applies_at_datetime__lte=timezone.now()+timedelta(days=4)
        )
        that_are_tiled = next_few_days_of_overlays.filter(tile_dir__isnull=False)
        and_the_newest_for_each = that_are_tiled.values('definition', 'applies_at_datetime').annotate(newest_id=Max('id'))
        ids_of_these = and_the_newest_for_each.values_list('newest_id', flat=True)
        # (Yay lazy evaluation...)

        overlays_to_display = Overlay.objects.filter(id__in=ids_of_these).order_by('definition', 'applies_at_datetime')
        return overlays_to_display

    @classmethod
    def make_all_base_plots(cls, time_index=0, file_id=None):
        task_list = [cls.make_plot.s(od_id, time_index, file_id) for od_id in cls.get_all_base_definition_ids()]
        job = group(task_list)
        results = job.apply_async()  # this might just be returning results from the first task in each chain
        return results

    @classmethod
    def make_all_base_plots_in_file(cls, file_id):
        datafile = DataFile.objects.get(pk=file_id)
        plotter = Plotter(datafile.file.name)
        number_of_times = plotter.get_number_of_model_times() # yeah, loading the plotter just for this isn't ideal...
        group_results_list = []
        for t in xrange(number_of_times):
            group_result = cls.make_all_base_plots(time_index=t, file_id=file_id)
            group_results_list.append(group_result)
        return group_results_list

    @classmethod
    def make_all_base_plots_in_files(cls, file_ids):
        group_results_list = []
        for file_id in file_ids:
            group_results = cls.make_all_base_plots_in_file(file_id)
            group_results_list.extend(group_results)
        return group_results_list

    @classmethod
    def make_all_base_plots_for_next_few_days(cls):
        file_ids = [datafile.id for datafile in DataFileManager.get_next_few_days_files_from_db()]
        return cls.make_all_base_plots_in_files(file_ids)

    @staticmethod
    @shared_task(name='pl_plot.make_plot')
    def make_plot(overlay_definition_id, time_index=0, file_id=None):
        if file_id is None:
            datafile = DataFile.objects.latest('model_date')
        else:
            datafile = DataFile.objects.get(pk=file_id)
        plotter = Plotter(datafile.file.name)
        overlay_definition = OverlayDefinition.objects.get(pk=overlay_definition_id)
        plot_filename, key_filename = plotter.make_plot(getattr(plot_functions, overlay_definition.function_name), time_index)

        overlay = Overlay(
            file=os.path.join(settings.UNCHOPPED_STORAGE_DIR, plot_filename),
            key=os.path.join(settings.KEY_STORAGE_DIR, key_filename),
            created_datetime=timezone.now(),
            definition_id=overlay_definition_id,
            applies_at_datetime=plotter.get_time_at_oceantime_index(time_index)
        )
        overlay.save()
        return overlay.id


class OverlayDefinition(models.Model):
    OVERLAY_TYPES = (
        ('V', 'Vector'),
        ('FC', 'Filled Contour'),
    )
    type = models.CharField(max_length=4, choices=OVERLAY_TYPES)
        #it might turn out that these don't have to be unique
    display_name_long = models.CharField(max_length=240, unique=True)
    display_name_short = models.CharField(max_length=64)
    function_name = models.CharField(max_length=64, unique=True)
    is_base = models.BooleanField(default=False)


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