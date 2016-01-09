from __future__ import absolute_import
from celery import shared_task, chain, subtask, group
import time
from pl_download.models import DataFileManager
from pl_plot.models import OverlayManager
from pl_chop.tasks import tile_overlay
from pl_chop.tasks import tile_wave_watch_overlay
from SharkEyesCore.models import FeedbackHistory
from SharkEyesCore.models import FeedbackQuestionaire

#------------------------------------------
# SharkEyesCore\tasks.py
#
#
#

#----------------------------------------
# do_pipeline()
#
#
@shared_task(name='sharkeyescore.pipeline')
def do_pipeline():
    # Cleaning up old files from the database and the disk
    DataFileManager.delete_old_files()
    OverlayManager.delete_old_files()

    # Check for new feedback surveys or comments, and email them to Flaxen
    FeedbackHistory.send_feedback_forms()
    FeedbackQuestionaire.send_feedback_survey()

    # Downloading the latest datafiles for our models. See the appropriate functions
    # (pl_download/models.py.DataFileManager.get_latest_wave_watch_files() and
    #  pl_download/models.py.DataFileManager.fetch_new_files()) respectavily
    wave_watch_files = DataFileManager.get_latest_wave_watch_files()
    other_files = DataFileManager.fetch_new_files()   # not calling as a task so it runs inline

    # If no new files were returned, don't plot or tile anything.
    if not wave_watch_files and not other_files:
        return None

    # get the list of plotting tasks based on the files we just downloaded.
    plot_task_list = OverlayManager.get_tasks_for_base_plots_for_next_few_days()


    list_of_chains = [] #What is this?

    for pt in plot_task_list:
        if pt.args[0] != 4 and pt.args[0] != 6: # TODO wave period:  and pt.args[0] != 7:
            # chaining passes the result of first function to second function
            list_of_chains.append(chain(pt, tile_overlay.s()))

        else:
            #Use the Wavewatch tiler for Wavewatch files
            list_of_chains.append(chain(pt, tile_wave_watch_overlay.s()))

    job = group(item for item in list_of_chains)
    print "jobs:"
    for each in job:
        print each
     #and run the group.
    result = job.apply_async()
    return result



@shared_task(name='sharkeyescore.spacer_task')
def spacer_task(args=None):
    if args is not None:
        return args
    return None
