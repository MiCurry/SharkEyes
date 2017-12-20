#!/usr/bin/env python
import os
import sys , traceback
import argparse
import time

import SharkEyesCore.startup as startup
from django.core.management import execute_from_command_line

from django.conf import settings

""" manage.py - Information

Baisc usages

`python manage.py download -r -w -n` # Download Roms, wind and nams

`python manage.py plot -i 23 34 45 -r` # Plot rom df with id 23, 34 and 45 

With manage.py plot you can only plot one file type at a time. So if 23, 34 
were ROMS datafiles and 45 was a wave file, you'll get an error.

`python manage.py plot-all -r` # Download and plot all of roms. Fresh
plots!

`python manage.py plot-l -d today -r -w` # Plot today's plots

Options for plot-l are `latest`, `all`, `today`.




"""

DEF_NUM_PLOTS = 5 # Default Number of Num Plots
DEF_TILE_FLAG = False # Default Tile Flag
DEF_FULL_ROMS_FLAG = False # Default Full Roms Flag

verbose = 0

def download(roms=False, wave=False,
             wind=False, hycom=False,
             ncep=False,
             num_dl=None):

    from pl_download.models import DataFileManager

    ids = []
    if roms:
        print "DL: Downloading roms files"
        roms_ids = []
        roms_ids = DataFileManager.download_osu_roms()
        print("OSU ROM dl ids:", roms_ids)
        ids.append(roms_ids)

    if wave:
        print "DL: Downloading OSU WW3 files"
        wave_ids = []
        wave_ids = DataFileManager.get_latest_wave_watch_files()
        print("OSU WW3 dl ids:", wave_ids)
        ids.append(wave_ids)

    if wind:
        print "DL: Downloading NAM WIND files"
        wind_ids = []
        wind_ids = DataFileManager.get_wind_file()
        print("NAM Wind dl ids:", wind_ids)
        ids.append(wind_ids)

    if hycom:
        print "DL: Downloading HYCOM files"
        print "DL: Number of downloads specified: ", num_dl

        hycom_ids = []
        hycom_ids = DataFileManager.hycom_download(count=num_dl)
        print("DL: HYCOM dl ids:", hycom_ids)
        ids.append(hycom_ids)

    if ncep:
        print "DL: Downloaind NCEP WW3"
        ncep_ids = []
        ncep_ids = DataFileManager.ww3_download()
        print("NCEP dl ids:", ncep_ids)
        ids.append(ncep_ids)

    return ids


def tile_set(id_start, id_end):
    from pl_chop.tasks import tile_overlay
    # Tile a range of overlays

    ids = range(id_start, id_end, 1)

    print "Tiling ids"
    for f in ids:
        tile_overlay(f)

def tile(ids):
    from pl_chop.tasks import tile_overlay

    if len(ids) == 0:
        print "TILE: Empty list of IDS quitting"
        return 0

    print "TILE: Tiling IDS: ", ids

    for f in ids:
        tile_overlay(f)

def plot(ids,
         num_plots=DEF_NUM_PLOTS, tile=DEF_TILE_FLAG, full_roms=DEF_FULL_ROMS_FLAG,
         roms=False,
         wave=False,
         wind=False,
         hycom=False,
         ncep=False):
    '''  Just generates plots. You need to pass in the df id to get a plot! Pass it in manually
    or by using one of the functions below which grabs them using the database or via downloading!
    '''

    if len(ids) == 0:
        print "PLOT: Empty List of IDS exiting"
        return

    from pl_plot.models import OverlayManager as om
    from pl_chop.tasks import tile_overlay

    if verbose > 0:

    if roms:
        roms = []

        print "PLOT: Plotting Roms with file IDS: ", ids
        if len(ids) > 1:
            for id in ids:
                for i in range(num_plots):
                    print "PLOT: OSU ROMS SST - timeslice: ", i
                    roms.append(om.make_plot(settings.OSU_ROMS_SST, i, id))
                    print "PLOT: OSU ROMS SSC - timeslice: ", i
                    roms.append(om.make_plot(settings.OSU_ROMS_SUR_CUR, i, id))

                    if full_roms:
                        print "PLOT: Plotting full roms"
                        print "PLOT: OSU ROMS SSC - timeslice: ", i
                        roms.append(om.make_plot(settings.OSU_ROMS_SUR_SAL, i, id))
                        print "PLOT: OSU ROMS BOT Sal- timeslice: ", i
                        roms.append(om.make_plot(settings.OSU_ROMS_BOT_SAL, i, id))
                        print "PLOT: OSU ROMS BOT Temp- timeslice: ", i
                        roms.append(om.make_plot(settings.OSU_ROMS_BOT_TEMP, i, id))
                        print "PLOT: OSU ROMS SSH - timeslice: ", i
                        roms.append(om.make_plot(settings.OSU_ROMS_SSH, i, id))
        else:
            for i in range(num_plots):
                roms.append(om.make_plot(settings.OSU_ROMS_SST, i, id))
                roms.append(om.make_plot(settings.OSU_ROMS_SUR_CUR, i, id))

                if full_roms:
                    roms.append(om.make_plot(settings.OSU_ROMS_SUR_SAL, i, id))
                    roms.append(om.make_plot(settings.OSU_ROMS_BOT_SAL, i, id))
                    roms.append(om.make_plot(settings.OSU_ROMS_BOT_TEMP, i, id))
                    roms.append(om.make_plot(settings.OSU_ROMS_SSH, i, id))

        if tile:
            print "PLOT: Tiling ROMS"
            tile(roms)

        return

    if wave:
        waves = []

        print ids
        print "PLOT: Plotting OSU WW3 with file IDS: ", ids

        if not ids:
            print "Empty List of IDS for OSU WW3"
            return

        for id in ids:
            for i in range(num_plots):
                waves.append(om.make_wave_watch_plot(settings.OSU_WW3_HI, i, id))
                waves.append(om.make_wave_watch_plot(settings.OSU_WW3_DIR, i, id))

        if tile:
            print "PLOT: Tiling waves"
            tile(waves)

        return

    if wind:
        winds = []

        print "PLOT: Plotting NAM Winds with file IDS: ", ids
        for id in ids:
            for i in range(num_plots):
                winds.append(om.make_plot(settings.NAMS_WIND, i, id))

        if tile:
            print "PLOT: Tiling NAM Winds"
            tile(winds)

        return

    if hycom:
        hycoms = []

        print "PLOT: Plotting HYCOM with file IDS: ", ids
        for id in ids:
            hycoms.append(om.make_plot(settings.HYCOM_SST, 0, id))
            hycoms.append(om.make_plot(settings.HYCOM_SUR_CUR, 0, id))

        if tile:
            print "PLOT: Tiling HYCOM"
            tile(hycoms)

        return

    if ncep:
        nceps = []

        print ids
        print "PLOT: Plotting NCEP WW3 with file IDS: ", ids
        for id in ids:
            for i in range(num_plots):
                nceps.append(om.make_wave_watch_plot(settings.NCEP_WW3_DIR, i, id))
                nceps.append(om.make_wave_watch_plot(settings.NCEP_WW3_HI, i, id))

        if tile:
            print "PLOT: Tiling NCEP"
            tile(ncep)

        return



def plot_new(num_plots=DEF_NUM_PLOTS, tile=DEF_TILE_FLAG, full_roms=DEF_FULL_ROMS_FLAG,
             roms=False, wave=False, wind=False,
             hycom=False, ncep=False):
    # num_plots = The number of plots you want for each file - save time!
    # Download and plot the newset freshest files from ze interwebz

    from pl_plot.models import OverlayManager as om
    from pl_chop.tasks import tile_overlay

    if roms:
        ids = download(roms=True)
        roms = []

        plot( ids, roms=True, num_plots=num_plots, tile=tile, full_roms=full_roms )

    if wave:
        ids = download(wave=True)
        waves = []

        plot( ids, wave=True, num_plots=num_plots, tile=tile )

    if wind:
        ids = download(wind=True)
        winds = []

        plot( ids, wind=True, num_plots=num_plots, tile=tile )

    if hycom:
        ids = download(hycom=True, num_dl=num_plots)
        hycoms = []

        plot( ids, hycom=True, num_plots=num_plots, tile=tile )

    if ncep:
        ids = download(ncep=True)
        nceps = []

        plot( ids, ncep=True, num_plots=num_plots, tile=tile )

def plot_latest(num_plots=DEF_NUM_PLOTS, tile=DEF_TILE_FLAG, full_roms=DEF_FULL_ROMS_FLAG, date='latest',
                roms=False, wave=False, wind=False,
                hycom=False, ncep=False):
    # num_plots = The number of plots you want for each file - save time!
    # Pull the latest files from the database and plot those

    """

    Using `latest` grabs all plots into the future. Similar to do_pipeline()
    """
    from pl_download.models import DataFile as df
    from pl_download.models import DataFileManager as dm
    from datetime import datetime

    if verbose > 0:
        print "Date span request: ", date


    # Today
    if date == 'today':
        today = datetime.now().date()
        print "Printing all datafiles with date of today"
    elif date == 'all':
        print "Printing all datafiles"
        pass
    elif date == 'latest':
        print "Printing datafiles that start with PAST_FILES_TO_DISPALY until whats returned from \n"
        print "get_next_few_days_files_from_db(days=x)"
        pass
    elif date is None:
        print "Printing datafiles that start with PAST_FILES_TO_DISPALY until whats returned from \n"
        print "get_next_few_days_files_from_db(days=x)"
        date = 'latest'
    else:
        print "Wrong date paramater. Please use - 'today', 'all', or 'latest'"
        return

    if roms:
        roms = []
        ids = []

        if date == "today":
            ids = df.objects.filter(type='NCDF').get(model_date=today)
        elif date == "latest":
            ids = dm.get_next_few_datafiles_of_a_type(days=1, type ='NCDF')
        elif date == "all":
            ids = df.objects.all().filter(type = "NCDF")

        for id in ids:
            print id.model_date

        ids = [id.id for id in ids] # Unwrap ids

        plot( ids, roms=True, num_plots=num_plots, tile=tile, full_roms=full_roms )

    if wave:
        waves = []
        ids = []
        if date == "today":
            ids = df.objects.filter(type='WAVE').get(model_date=today)
        elif date == "latest":
            ids = dm.get_next_few_datafiles_of_a_type(days=1, past_days=1, type ='WAVE')
        elif date == "all":
            ids = df.objects.all().filter(type = "WAVE")


        ids = [id.id for id in ids] # Unwrap ids


        plot( ids, wave=True, num_plots=num_plots, tile=tile )

    if wind:
        winds = []
        ids = []
        if date is "today":
            ids = df.objects.filter(type='WIND').get(model_date=today)
        elif date is "latest":
            ids = dm.get_next_few_datafiles_of_a_type(days=1, type ='WIND')
        elif date is "all":
            ids = df.objects.all().filter(type = "WIND")

        ids = [id.id for id in ids] # Unwrap ids

        plot(ids, wind=True, num_plots=num_plots, tile=tile )

    if hycom:
        hycoms = []
        if date == "today":
            ids = df.objects.filter(type='HYCOM').get(model_date=today)
        elif date == "latest":
            ids = dm.get_next_few_datafiles_of_a_type(days=20, type ='HYCOM')
        elif date == "all":
            ids = df.objects.all().filter(type = "HYCOM")

        ids = [id.id for id in ids] # Unwrap ids

        plot( ids, hycom=True, num_plots=num_plots, tile=tile )

    if ncep:
        nceps = []
        ids = []
        if date is "today":
            ids = df.objects.filter(type='NCEP_WW3').get(model_date=today)
        elif date is "latest":
            ids = dm.get_next_few_datafiles_of_a_type(days=20, type ='NCEP_WW3')
        elif date is "all":
            ids = df.objects.all().filter(type = "NCEP_WW3")

        ids = [id.id for id in ids] # Unwrap ids
        plot( ids, ncep=True, num_plots=num_plots, tile=tile )


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SharkEyesCore.settings")
    startup.run()

    parser = argparse.ArgumentParser(description='Easy way to produce plots of\
    seacast fields.')

    task = parser.add_argument_group('Task', 'The task you want to preform.')
    task.add_argument('task',
                        help='The manage.py command you want to run. Options are \n' \
                             "\t 'download' & 'plot'",
                        type=str)

    model = parser.add_argument_group('Models', 'Enable models by using these commands')
    model.add_argument("-r", '--roms',
                        help='Toggle on OSU ROMS in this task call',
                        action="store_true")
    model.add_argument("-w", '--wave',
                        help='Toggle on OSU WW3 in this task call',
                        action="store_true")
    model.add_argument("-n", '--nams',
                        help='Toggle on NAMS in this task call',
                        action="store_true")
    model.add_argument("-p", '--hycom',
                        help='Toggle on HYCOM in this task call',
                        action="store_true")
    model.add_argument("-c", '--ncep',
                        help='Toggle on NCEP WW3 in this task Call',
                        action="store_true")


    other = parser.add_argument_group('Other')
    other.add_argument("-T", '--tile',
                        help='Toggle on to produce tiles in plot',
                        action="store_true")
    other.add_argument("-k", '--num',
                       help='Number of plots to generate in plot',
                       type=int,
                       default=DEF_NUM_PLOTS)
    other.add_argument("-f", '--fullRoms',
                        help='Run the full number of roms. Default is True',
                        type=bool,
                        default=DEF_FULL_ROMS_FLAG)
    other.add_argument("-i", '--ids',
                       help='Toggle on to produce tiles in plot',
                       default=[],
                       action="append",
                       dest='ids')
    other.add_argument("-v", '--verbose',
                       help='Turn on vebrosity level 0 (default), 1, 2, 3, 9000',
                       default=0,
                       type=int)
    other.add_argument("-d", '--date',
                       help='today, latest, ',
                       type=str)

    args, unknown = parser.parse_known_args()

    if args.verbose >= 2:
        print args

    if args.task == "download":
        print download(roms=args.roms,
                       wave=args.wave,
                       wind=args.nams,
                       hycom=args.hycom,
                       ncep=args.ncep,
                       num_dl=args.num)
        sys.exit()

    elif args.task == "plot-all":
        plot_all(num_plots=args.num,
                 tile=args.tile,
                 roms=args.roms,
                 wave=args.wave,
                 wind=args.nams,
                 hycom=args.hycom,
                 ncep=args.ncep)
        sys.exit()

    elif args.task == "plot":
        plot(num_plots=args.num,
             tile=args.tile,
             roms=args.roms,
             wave=args.wave,
             wind=args.nams,
             hycom=args.hycom,
             ncep=args.ncep)
        sys.exit()

    elif args.task == "plot-l":
        plot_latest(num_plots=args.num,
             tile=args.tile,
             roms=args.roms,
             wave=args.wave,
             wind=args.nams,
             hycom=args.hycom,
             ncep=args.ncep,
             date=args.date)
        sys.exit()

    elif args.task == 'tile':
        tile_set()
        sys.exit()

    elif args.task == "test":
        pass
        sys.exit()

    execute_from_command_line(sys.argv)