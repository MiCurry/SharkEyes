#!/usr/bin/env python
import os
import sys , traceback

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
        wind = 1
        if wave:
            tiles = []
            #first entry is day-1 at 12pm
            #need to offset 16 to match with sst plot
            #NOTE it increments in 1 hour changes
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

        if wind:
            winds = []
            tiles += OverlayManager.make_plot(5, 0, 0)
            tiles += OverlayManager.make_plot(5, 1, 0)
            tiles += OverlayManager.make_plot(5, 2, 0)
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
        wind = 1
        wave = 0
        sst = 0

        if wave:
            DataFileManager.get_latest_wave_watch_files()
            print "\n--- Plotting WW3 - Height and Direction ---"
            wave = DataFile.objects.filter(type = "WAVE").values_list('id', flat=True)
            for id in wave:
                for t in xrange(0, 85, 4):
                    try:
                        print "Plotting and Tiling WW3 - File ID:", id, "Time Index:", t
                        tile_wave_watch_overlay(om.make_wave_watch_plot(4, t, id))
                        tile_wave_watch_overlay(om.make_wave_watch_plot(6, t, id))
                        print "plot/tile success"
                    except Exception:
                        print '-' * 60
                        traceback.print_exc(file=sys.stdout)
                        print '-' * 60
                    print
        if sst:
            DataFileManager.fetch_new_files()
            print "\n--- Plotting ROMS - SST and Currents ---"
            sst_files = DataFile.objects.all().filter(type = "NCDF")
            for file in sst_files:
                plotter = Plotter(file.file.name)
                number_of_times = plotter.get_number_of_model_times()
                id = file.id
                for t in xrange(number_of_times):
                    try:
                        print "Plotting ROMS - File ID:", id, "Time Index:", t
                        tile_overlay(om.make_plot(1, t, id))
                        tile_overlay(om.make_plot(3, t, id))
                        print "plot/tile success"
                    except Exception:
                        print '-' * 60
                        traceback.print_exc(file=sys.stdout)
                        print '-' * 60
                    print
        if wind:
            print "\n Plotting A NAM - WINDS"
            plotter = WindPlotter()
            number_of_times = plotter.get_number_of_model_times()
            for t in xrange(number_of_times):
                try:
                    print "Plotting and Tiling NAMS - Time_Index:", t
                    tile_overlay(om.make_plot(5, t, 0))
                    print "plot/tile success"
                except Exception:
                    print '-' * 60
                    traceback.print_exc(file=sys.stdout)
                    print '-' * 60
                print

    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
