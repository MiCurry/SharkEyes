from __future__ import absolute_import
from celery import shared_task, chain, group
from pl_download.models import DataFileManager
from pl_plot.models import OverlayManager
from pl_chop.tasks import tile_overlay
from pl_chop.tasks import tile_wave_watch_overlay
from SharkEyesCore.models import FeedbackHistory
from SharkEyesCore.models import FeedbackQuestionaire
import sys , traceback

@shared_task(name='sharkeyescore.pipeline')
def do_pipeline():

    # Cleaning up old files from the database and the disk
    print "CLEANING UP - DELETING OLD FILES"
    try:
        DataFileManager.delete_old_files()
    except Exception:
        print '-' * 60
        print "COULD NOT DELETE OLD NETCDF FILES"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    try:
        OverlayManager.delete_old_files()
    except Exception:
        print '-' * 60
        print "COULD NOT DELETE OVERLAY FILES"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    # Check for new feedback surveys or comments, and email them to Flaxen
    print "SENDING OUT FEEDBACK"
    try:
        FeedbackHistory.send_feedback_forms()
    except Exception:
        print '-' * 60
        print "COULD NOT SEND FEEDBACK"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    try:
        FeedbackQuestionaire.send_feedback_survey()
    except Exception:
        print '-' * 60
        print "COULD NOT SEND FEEDBACK SURVEY"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    # Downloading the latest datafiles for our models. See the appropriate functions
    #   pl_download/models.py.DataFileManager.get_latest_wave_watch_files() and
    #   pl_download/models.py.DataFileManager.fetch_new_files() respectively
    print "DOWNLOADING OSU WW3 FILES"
    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        wave_watch_files = DataFileManager.get_latest_wave_watch_files()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD OSU WW3 FILES"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    print "DOWNLOADING OSU ROMS FILES"
    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        sst_files = DataFileManager.download_osu_roms()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD OSU ROMS FILES"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    print "DOWNLOADING WIND FILES"
    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        wind_files = DataFileManager.get_wind_file()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD WIND FILE"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        hycom_files = DataFileManager.hycom_download()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD HYCOM FILE"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        ncep_files = DataFileManager.ww3_download()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD NCEP WW3 FILE"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60


    # If no new files were returned, don't plot or tile anything.
    try:
        #This try catch is also for the wave watch timeout bug
        if not wave_watch_files and not sst_files and not wind_files \
                and not ncep_files and not hycom_files:
            print "No New Files Available, Quitting."
            return None
    except Exception:
        print '-' * 60
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    # Get the list of plotting tasks based on the files we just downloaded.
    plot_task_list = OverlayManager.get_tasks_for_base_plots_for_next_few_days()

    list_of_chains = []

    for pt in plot_task_list:
        if pt.args[0] != 4 and pt.args[0] != 6:
            # Chaining passes the result of first function to second function
            list_of_chains.append(chain(pt, tile_overlay.s()))
        else:
            # Use the Wavewatch tiler for Wavewatch files
            list_of_chains.append(chain(pt, tile_wave_watch_overlay.s()))

    job = group(item for item in list_of_chains)

    print "PIPELINE: JOBS: "
    for each in job:
        print each

    result = job.apply_async() # Run the group.
    return result

@shared_task(name='sharkeyescore.spacer_task')
def spacer_task(args=None):
    if args is not None:
        return args
    return None
