#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SharkEyesCore.settings")

    import SharkEyesCore.startup as startup
    startup.run()

    if sys.argv[-1] == "plot":
        from pl_download.models import DataFileManager
        from pl_plot.models import OverlayManager
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        wave = DataFileManager.get_latest_wave_watch_files()
        sst = DataFileManager.fetch_new_files()
        if wave:
            tiles = []
            #first entry is day-1 at 12pm
            #need to offset 16 to match with sst plot
            #NOTE it increments in 1 hour changes
            tiles += OverlayManager.make_wave_watch_plot(7, 16, wave[0])
            tiles += OverlayManager.make_wave_watch_plot(4, 16, wave[0])
            tiles += OverlayManager.make_wave_watch_plot(6, 16, wave[0])
            for t in tiles:
                tile_wave_watch_overlay(t)
        if sst:
            tiles = []
            #first entry is day at 4am
            #NOTE it increments in 4 hour changes
            tiles += OverlayManager.make_plot(1, 0, sst[0])
            tiles += OverlayManager.make_plot(3, 0, sst[0])
            for t in tiles:
                tile_overlay(t)
    #Small test to see what times the WindPlotter returns
    elif sys.argv[-1] == "wtest":
        from pl_plot.plotter import WindPlotter
        from pl_plot.models import OverlayManager
        pl = WindPlotter()
        for i in range(7):
            print pl.get_time_at_oceantime_index(i)

        t = OverlayManager.make_plot(5, 2, 0)
        print t


    elif sys.argv[-1] == "plot-all":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager as om
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        from pl_plot.plotter import WaveWatchPlotter, WindPlotter, Plotter
        DataFileManager.get_latest_wave_watch_files()
        DataFileManager.fetch_new_files()
        wind = 1
        wave = 1
        sst = 1
        wave_plots = []

        if wave:
            print "\n--- Plotting WW3 - Height and Direction ---"
            wave = DataFile.objects.filter(type = "WAVE").values_list('id', flat=True)
            for ids in wave:
                for t in xrange(0, 85, 4):
                    print "Plotting and Tiling WW3 - File ID:", ids, "Time Index:", t
                    tile_wave_watch_overlay(om.make_wave_watch_plot(4, t, ids))
                    tile_wave_watch_overlay(om.make_wave_watch_plot(6, t, ids))
        if sst:
            print "\n--- Plotting ROMS - SST and Currents ---"
            sst = DataFile.objects.filter(type = "NCDF").values_list('id', flat=True).distinct
            for ids in sst:
                plotter = Plotter(files.file.name)
                number_of_times = plotter.get_number_of_model_times()
                for t in xrange(number_of_times):
                    print "Plotting and Tiling ROMS - File ID:", ids, "Time Index:", t
                    tile_overlay(om.make_plot(1, t, ids))
                    tile_overlay(om.make_plot(3, t, ids))

        if wind:
            print "\n--- Plotting NAM - WINDS ---"
            plotter = WindPlotter()
            number_of_times = plotter.get_number_of_model_times()
            for t in xrange(number_of_times):
                print "Plotting and Tiling NAMS - Time_Index:", t
                tile_overlay(om.make_plot(5, t, 0))




    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)

