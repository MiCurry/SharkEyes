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

###

File Structure:
===============
* info(object)
* def list_function(table='datafiles', roms=False, wave=False, wind=False,
                    hycom=False, ncep=False, tcline=False,navy=False):
* tile_set(id_start, id_end)
* tile(ids)
* download(roms=False, wave=False, wind=False, hycom=False, ncep=False,
           tcline=False, navy=False, num_dl=None):
* plot(ids=[], num_plots=DEF_NUM_PLOTS, tile_flag=DEF_TILE_FLAG,
       full_roms=DEF_FULL_ROMS_FLAG, roms=False, wave=False, wind=False,
       hycom=False, ncep=False, tcline=False, navy=False):
"""

DEF_NUM_PLOTS = 5 # Default Number of Num Plots
DEF_TILE_FLAG = False # Default Tile Flag
DEF_FULL_ROMS_FLAG = False # Default Full Roms Flag

verbose = 0

def info(object):
    from pl_download.models import DataFile
    from pl_plot.models import Overlay

    if type(object) == DataFile:
        print "--- ", object.type, " DATAFILE --- ", object.file.name, " --- ", "DF-ID: ", object.id, " --- "
        print "   MODEL DATE: ", object.model_date, " DL DATETIME: ", object.download_datetime
        print ""
    if type(object) == Overlay:
        print "--- Overlay Defintion: ", object.definition, " --- OVERLAY ID", object.id
        print " FILE: ", object.file.name
        print " CREATED DATETIME: ", object.created_datetime, " APPLIES AT: ", object.applies_at_datetime
        print " IS TILED: ", object.is_tiled, " IS EXTEND: ", object.is_extend
        print " ZOOM LEVEL: ", object.zoom_levels
        print ""

def list_function(table='datafiles',
                  roms=False, wave=False, wind=False, hycom=False, ncep=False, tcline=False,
                  navy=False):
    from pl_plot.models import Overlay
    from pl_download.models import DataFile

    if table == 'datafiles' or table == 'all':
        if roms:
            df_type = 'NCDF'
            entries = DataFile.objects.filter(type=df_type)
            for entry in entries:
                info(entry)
        if wave:
            df_type = 'WAVE'
            entries = DataFile.objects.filter(type=df_type)
            for entry in entries:
                info(entry)
        if wind:
            df_type = 'WIND'
            entries = DataFile.objects.filter(type=df_type)
            for entry in entries:
                info(entry)
        if hycom:
            df_type = 'HYCOM'
            entries = DataFile.objects.filter(type=df_type)
            for entry in entries:
                info(entry)
        if ncep:
            df_type = 'NCEP'
            entries = DataFile.objects.filter(type=df_type)
            for entry in entries:
                info(entry)
        if tcline:
            df_type = 'tcline'
            entries = DataFile.objects.filter(type=df_type)
            for entry in entries:
                info(entry)
        if navy:
            df_type = 'NAVY'
            entries = DataFile.objects.filter(type=df_type)
            for entry in entries:
                info(entry)
    elif table == 'overlays' or table == 'all': # List overlays
        from django.db.models import Q
        if roms:
            overlays = Overlay.objects.filter(Q(definition_id=settings.OSU_ROMS_SST)
                                            | Q(definition_id=settings.OSU_ROMS_BOT_TEMP)
                                            | Q(definition_id=settings.OSU_ROMS_SUR_CUR)
                                            | Q(definition_id=settings.OSU_ROMS_SUR_SAL)
                                            | Q(definition_id=settings.OSU_ROMS_BOT_SAL)
                                            | Q(definition_id=settings.OSU_ROMS_SSH))
            for overlay in overlays:
                info(overlay)
        if wave:
            overlays = Overlay.objects.filter(Q(definition_id=settings.NCEP_WW3_DIR)
                                            | Q(definition_id=settings.NCEP_WW3_HI))
            for overlay in overlays:
                info(overlay)
        if wind:
            overlays = Overlay.objects.filter(Q(definition_id=settings.NAMS_WIND))
            for overlay in overlays:
                info(overlay)
        if hycom:
            overlays = Overlay.objects.filter(Q(definition_id=settings.HYCOM_SST)
                                            | Q(definition_id=settings.HYCOM_SUR_CUR))
            for overlay in overlays:
                info(overlay)
        if ncep:
            overlays = Overlay.objects.filter(Q(definition_id=settings.NCEP_WW3_DIR)
                                            | Q(definition_id=settings.NCEP_WW3_HI))
            for overlay in overlays:
                info(overlay)
        if tcline:
            overlays = Overlay.objects.filter(Q(definition_id=settings.OSU_ROMS_TCLINE)
                                            | Q(definition_id=settings.OSU_ROMS_PCLINE))
            for overlay in overlays:
                info(overlay)
        if navy:
            overlays = Overlay.objects.filter(Q(definition_id=settings.NAVY_HYCOM_SST)
                                              | Q(definition_id=settings.NAVY_HYCOM_BOT_TEMP)
                                              | Q(definition_id=settings.NAVY_HYCOM_SUR_CUR)
                                              | Q(definition_id=settings.NAVY_HYCOM_BOT_CUR)
                                              | Q(definition_id=settings.NAVY_HYCOM_TOP_SAL)
                                              | Q(definition_id=settings.NAVY_HYCOM_BOT_SAL)
                                              | Q(definition_id=settings.NAVY_HYCOM_SSH))
            for overlay in overlays:
                info(overlay)

def tile_set(id_start, id_end):
    # Never Needs to be Updated
    from pl_chop.tasks import tile_overlay
    # Tile a range of overlays

    ids = range(id_start, id_end, 1)

    print "Tiling ids"
    for f in ids:
        tile_overlay(f)

def tile(ids):
    """ Never Needs to be Updated"""
    from pl_chop.tasks import tile_overlay

    if len(ids) == 0:
        print "TILE: Empty list of IDS quitting"
        return 0

    print "TILE: Tiling IDS: ", ids

    for f in ids:
        tile_overlay(f)

def download(roms=False, wave=False, wind=False, hycom=False, ncep=False, tcline=False,  navy=False,
             num_dl=None):

    from pl_download.models import DataFileManager

    ids = []
    if roms:
        print "DL: Downloading roms files"
        roms_ids = []
        roms_ids = DataFileManager.download_osu_roms()
        print("OSU ROM dl ids:", roms_ids)
        ids.append(roms_ids) # Update to a dictonary

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
        hycom_ids = DataFileManager.rtofs_download(count=num_dl)
        print("DL: HYCOM dl ids:", hycom_ids)
        ids.append(hycom_ids)

    if ncep:
        print "DL: Downloaind NCEP WW3"
        ncep_ids = []
        ncep_ids = DataFileManager.ww3_download()
        print("NCEP dl ids:", ncep_ids)
        ids.append(ncep_ids)

    if tcline:
        print "DL: Downloading OSU t-cline"
        tcline_ids = []
        tcline_ids = None
        print("NCEP dl ids:", tcline_ids)
        ids.append(tcline_ids)

    if navy:
        print "DL: Downloading Navy Hycom"
        navy_ids = []
        navy_ids = DataFileManager.navy_hycom_download()
        print ("NAVY HYCOM ids: ", navy_ids)
        ids.append(navy_ids)

    return ids

def plot(ids=[],
         num_plots=DEF_NUM_PLOTS, tile_flag=DEF_TILE_FLAG, full_roms=DEF_FULL_ROMS_FLAG,
         roms=False, wave=False, wind=False, hycom=False, ncep=False, tcline=False, navy=False):
    '''  Just generates plots. You need to pass in the df id to get a plot! Pass it in manually
    or by using one of the functions below which grabs them using the database or via downloading!
    '''
    print "IDS", ids

    if not ids:
        print "PLOT: NO IDS SUBMITTED TO BE PLOTTED - exiting"
        return

    if len(ids) == 0:
        print "PLOT: Empty List of IDS exiting"
        return

    from pl_plot.models import OverlayManager as om
    from pl_chop.tasks import tile_overlay

    if roms: # OSU ROMS
        roms = []

        print "PLOT: Plotting Roms with file IDS: ", ids
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

        if tile_flag:
            print "PLOT: Tiling ROMS"
            tile(roms)

        return

    if wave: # OSU WAVE WATCH III - NO LONGER AVIABLE
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

        if tile_flag:
            print "PLOT: Tiling waves"
            tile(waves)

        return

    if wind: # NORTH AMERICAN MESOSCALE - SURFACE WINDS
        winds = []

        print "PLOT: Plotting NAM Winds with file IDS: ", ids
        for id in ids:
            for i in range(num_plots):
                winds.append(om.make_plot(settings.NAMS_WIND, i, id))

        if tile_flag:
            print "PLOT: Tiling NAM Winds"
            tile(winds)

        return

    if hycom: # NOAA HYCOM - Not currently implemented on the seacast.org
        hycoms = []

        print "PLOT: Plotting HYCOM with file IDS: ", ids
        for id in ids:
            hycoms.append(om.make_plot(settings.HYCOM_SST, 0, id))
            hycoms.append(om.make_plot(settings.HYCOM_SUR_CUR, 0, id))

        if tile_flag:
            print "PLOT: Tiling HYCOM"
            tile(hycoms)

        return

    if ncep: # NCEP WAVE WATCH III
        nceps = []

        print ids
        print "PLOT: Plotting NCEP WW3 with file IDS: ", ids
        for id in ids:
            for i in range(num_plots):
                nceps.append(om.make_wave_watch_plot(settings.NCEP_WW3_DIR, i, id))
                nceps.append(om.make_wave_watch_plot(settings.NCEP_WW3_HI, i, id))

        if tile_flag:
            print "PLOT: Tiling NCEP"
            tile(nceps)

        return

    if tcline: # OSU ROMS THERMOCLINE
        tcline_ids = []

        print ids
        print "PLOT: Plotting TCLINE with file IDS: ", ids
        for id in ids:
            for i in range(num_plots):
                tcline_ids.append(om.make_plot(settings.OSU_ROMS_TCLINE, i, id))

        if tile_flag:
            print "PLOT: Tiling tcline"
            tile(tcline_ids)

        return

    if navy: # NAVY HYCOM
        navy_ids = []

        print ids
        print "PLOT: Plotting NCEP WW3 with file IDS: ", ids
        for id in ids:
            navy_ids.append(om.make_plot(settings.NAVY_HYCOM_SST, 0, id))
            navy_ids.append(om.make_plot(settings.NAVY_HYCOM_SUR_CUR, 0, id))
            navy_ids.append(om.make_plot(settings.NAVY_HYCOM_SUR_SAL, 0, id))


        if tile_flag:
            print "PLOT: Tiling NCEP"
            tile(navy_ids)

        return


def test():
    print "No test function implemented! Write your test function today!"
    pass

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
    model.add_argument("-a", '--all',
                       help='Toggle on all the models',
                       action='store_true')
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
    model.add_argument("-l", '--cline',
                       help='Toggle on OSU T/P-CLINE downloads in this task Call',
                       action="store_true")
    model.add_argument("-y", '--navy',
                       help='Toggle on NAVY HYCOM in this task Call',
                       action="store_true")


    other = parser.add_argument_group('Other')
    other.add_argument("-T", '--tile',
                        help='Toggle on to produce tiles in plot',
                        action="store_true")
    other.add_argument("-K", '--num',
                       help='Number of plots to generate in plot',
                       type=int,
                       default=DEF_NUM_PLOTS)
    other.add_argument("-F", '--fullRoms',
                        help='Run the full number of roms. Default is True',
                        type=bool,
                        default=DEF_FULL_ROMS_FLAG)
    other.add_argument("-I", '--ids',
                       help='Toggle on to produce tiles in plot',
                       nargs="+",
                       dest='ids')
    other.add_argument("-V", '--verbose',
                       help='Turn on vebrosity level 0 (default), 1, 2, 3, 9000',
                       default=0,
                       type=int)
    other.add_argument("-D", '--date',
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
                       num_dl=args.num,
                       tcline=args.cline,
                       navy=args.navy)
        sys.exit()

    elif args.task == "plot":
        plot(args.ids,
             num_plots=args.num,
             tile_flag=args.tile,
             roms=args.roms,
             wave=args.wave,
             wind=args.nams,
             hycom=args.hycom,
             ncep=args.ncep,
             tcline=args.cline)
        sys.exit()

    elif args.task == 'tile':
        tile(ids=args.ids)
        sys.exit()

    elif args.task == "datafiles":
        list_function(table='datafiles',
                      roms=args.roms,
                      wave=args.wave,
                      wind=args.nams,
                      hycom=args.hycom,
                      ncep=args.ncep,
                      tcline=args.ncep,
                      navy=args.navy,
                      )
        sys.exit()

    elif args.task == "overlays":
        list_function(table='overlays',
                      roms=args.roms,
                      wave=args.wave,
                      wind=args.nams,
                      hycom=args.hycom,
                      ncep=args.ncep,
                      tcline=args.ncep,
                      navy=args.navy,
                      )
        sys.exit()

    elif args.task == "test":
        test()
        sys.exit()

    execute_from_command_line(sys.argv)
