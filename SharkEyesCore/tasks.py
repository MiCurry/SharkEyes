from __future__ import absolute_import
from celery import shared_task, chain, group

import sys
import traceback
import logging

from pl_download.models import DataFileManager
from pl_plot.models import OverlayManager
from pl_chop.tasks import tile_overlay
from pl_chop.tasks import tile_wave_watch_overlay
from SharkEyesCore.models import FeedbackHistory
from SharkEyesCore.models import FeedbackQuestionaire

from django.conf import settings

@shared_task(name='get_and_apply_new_jobs')
def get_and_apply_new_jobs():
    """ Gets tasks from the OverlayManager and applies jobs that haven't been run,
    similar to do_pipeline, but doesn't download any new files.
    :return: Celery Result
    """
    # Get the list of plotting tasks based on the files we just downloaded.
    logging.info('get_and_apply_new_jobs')
    logging.info('GENERATING TASK LIST')
    plot_task_list = OverlayManager.get_tasks_for_base_plots_for_next_few_days()

    list_of_chains = []

    for pt in plot_task_list:
        if pt.args[0] != 4 and pt.args[0] != 6:
            # Chaining passes the result of first function to second function
            list_of_chains.append(chain(pt, tile_overlay.s()))
        else:
            # Use the Wavewatch tiler for Wavewatch files
            list_of_chains.append(chain(pt, tile_wave_watch_overlay.s()))
    logging.info('TASK LIST GENERATED')

    job = group(item for item in list_of_chains)

    print "PIPELINE: JOBS: "
    for each in job:
        print each

    logging.info('APPLY JOBS')
    result = job.apply_async() # Run the group.
    logging.info('JOBS APPLIED')
    return result


@shared_task(name='sharkeyescore.pipeline')
def do_pipeline():

    logging.info('DO_PIPELINE STARTED')


    # Cleaning up old files from the database and the disk
    print "CLEANING UP - DELETING OLD FILES"
    logging.info('CLEANING UP - DELETING OLD DATAFILE FILES')
    try:
        DataFileManager.delete_old_files()
    except Exception:
        print '-' * 60
        print "COULD NOT DELETE OLD NETCDF FILES"
        logging.error('CLEANING UP - ERROR DELETING DATAFILES')
        traceback.print_exc(file=sys.stdout)
        print '-' * 60
    logging.info('CLEANING UP - OLD DATAFILE FILES DELETED')


    logging.info('CLEANING UP - DELETING OLD OVERLAY FILES')
    try:
        OverlayManager.delete_old_files()
    except Exception:
        print '-' * 60
        print "COULD NOT DELETE OVERLAY FILES"
        logging.error('CLEANING UP - ERROR DELETING OVERLAYS OR TILES')
        traceback.print_exc(file=sys.stdout)
        print '-' * 60
    logging.info('CLEANING UP - OLD OVERLAY and TILES DELETED')


    # Check for new feedback surveys or comments, and email them to Flaxen
    print "SENDING OUT FEEDBACK"
    logging.info('SENDING OUT FEEDBACK')
    try:
        FeedbackHistory.send_feedback_forms()
    except Exception:
        print '-' * 60
        print "COULD NOT SEND FEEDBACK"
        logging.error('ERROR SENDING FEEDBACK FORMS')
        traceback.print_exc(file=sys.stdout)
        print '-' * 60
    logging.info('FEEDBACK FORMS SENT')


    logging.info('SENDING OUT SURVEY')
    try:
        FeedbackQuestionaire.send_feedback_survey()
    except Exception:
        print '-' * 60
        print "COULD NOT SEND FEEDBACK SURVEY"
        logging.error('ERROR SENDING FEEDBACK SURVEY')
        traceback.print_exc(file=sys.stdout)
        print '-' * 60
    logging.info('SURVEYS Sent')


    print "DOWNLOADING UCAR NCEP FILES"
    logging.info('DOWNLOADING UCAR NCEP WW3')
    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        wave_watch_files = DataFileManager.ww3_download()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD UCAR NCEP WW3 FILES"
        logging.error('ERROR DOWNLOADING UCAR NCEP WW3')
        traceback.print_exc(file=sys.stdout)
        print '-' * 60
    logging.info('OSU WW3 DOWNLOADED SUCCESFULLY')


    print "DOWNLOADING OSU ROMS FILES"
    logging.info('DOWNLOADING OSU ROMS')
    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        sst_files = DataFileManager.download_osu_roms()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD OSU ROMS FILES"
        logging.error('ERROR DOWNLOADING OSU ROMS')
        traceback.print_exc(file=sys.stdout)
        print '-' * 60
    logging.info('OSU ROMS DOWNLOADED SUCCESFULLY')


    if settings.EXTEND:
        print "DOWNLOADING NAVY HYCOM"
        logging.info('DOWNLOADING NAVY HYCOM')
        try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
            hycom_files = DataFileManager.navy_hycom_download()
        except Exception:
            print '-' * 60
            print "COULD NOT DOWNLOAD NAVY HYCOM FILES"
            logging.error('ERROR DOWNLOADING OSU ROMS')
            traceback.print_exc(file=sys.stdout)
            print '-' * 60
        logging.info('OSU ROMS DOWNLOADED SUCCESFULLY')


    print "DOWNLOADING WIND FILES"
    logging.info('DOWNLOADING NAM WIND')
    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        wind_files = DataFileManager.get_wind_file()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD WIND FILE"
        logging.error('ERROR DOWNLOADING NAM WINDS')
        traceback.print_exc(file=sys.stdout)
        print '-' * 60
    logging.info('NAM WINDS DOWNLOADED SUCCESFULLY')


    print "DOWNLOADING TCLINE FILES"
    try: # Try Catches to ensure do_pipeline completes even if a model server cant be reached
        tcline_files = DataFileManager.download_tcline()
    except Exception:
        print '-' * 60
        print "COULD NOT DOWNLOAD TCLINE FILE"
        traceback.print_exc(file=sys.stdout)
        print '-' * 60


    try:
        #This try catch is also for the wave watch timeout bug
        if not wave_watch_files and not sst_files and not wind_files and not hycom_files \
                and not tcline_files:
            print "No New Files Available, Quitting."
            return None
    except Exception:
        print '-' * 60
        traceback.print_exc(file=sys.stdout)
        print '-' * 60

    # Get the list of plotting tasks based on the files we just downloaded.
    logging.info('GENERATING TASK LIST')
    plot_task_list = OverlayManager.get_tasks_for_base_plots_for_next_few_days()

    list_of_chains = []

    for pt in plot_task_list:
        if pt.args[0] != 4 and pt.args[0] != 6:
            # Chaining passes the result of first function to second function
            list_of_chains.append(chain(pt, tile_overlay.s()))
        else:
            # Use the Wavewatch tiler for Wavewatch files
            list_of_chains.append(chain(pt, tile_wave_watch_overlay.s()))
    logging.info('TASK LIST GENERATED')

    job = group(item for item in list_of_chains)

    print "PIPELINE: JOBS: "
    for each in job:
        print each

    logging.info('APPLY JOBS')
    result = job.apply_async() # Run the group.
    logging.info('JOBS APPLIED')
    return result

@shared_task(name='sharkeyescore.spacer_task')
def spacer_task(args=None):
    if args is not None:
        return args
    return None
