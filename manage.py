#!/usr/bin/env python
import os
import sys , traceback
import time

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SharkEyesCore.settings")

    import SharkEyesCore.startup as startup
    startup.run()

    if sys.argv[-1] == "download":
        from pl_download.models import DataFileManager, DataFile
        wave = 1
        sst = 0
        wind = 0
        if wave:
            DataFileManager.get_latest_wave_watch_files()
        if sst:
            DataFileManager.fetch_new_files()
        if wind:
            DataFileManager.get_wind_file()

    elif sys.argv[-1] == "plot":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        wave = 0
        sst = 1
        wind = 0
        if wave:
            wave = DataFileManager.get_latest_wave_watch_files()
            wave = DataFile.objects.filter(type='WAVE').latest('model_date')
            tiles = []
            begin = time.time()
            #first entry is day-1 at 12pm
            #need to offset 16 to match with sst plot
            #NOTE it increments in 1 hour changes
            tiles += OverlayManager.make_wave_watch_plot(4, 16, wave[0])
            tiles += OverlayManager.make_wave_watch_plot(6, 16, wave[0])
            for t in tiles:
                tile_wave_watch_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for Waves = " + str(round(totalTime, 2)) + " minutes"
        if sst:
            #sst = DataFileManager.fetch_new_files()
            tiles = []
            #first entry is day at 4am
            #NOTE it increments in 4 hour changes
            begin = time.time()
            #tiles += OverlayManager.make_plot(1, 0, sst[0])
            tiles += OverlayManager.make_plot(2, 0, sst[0])
            #tiles += OverlayManager.make_plot(3, 0, sst[0])
            tiles += OverlayManager.make_plot(7, 0, sst[0])
            tiles += OverlayManager.make_plot(8, 0, sst[0])
            tiles += OverlayManager.make_plot(9, 0, sst[0])
            for t in tiles:
                tile_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for SST = " + str(round(totalTime, 2)) + " minutes"

        if wind:
            winds = DataFileManager.get_wind_file()
            winds = DataFile.objects.filter(type='WIND').latest('model_date')
            tiles = []
            begin = time.time()
            tiles += OverlayManager.make_plot(5, 0, winds)
            for t in tiles:
                tile_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for Winds = " + str(round(totalTime, 2)) + " minutes"

    elif sys.argv[-1] == "plot-all":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager as om
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        from pl_plot.plotter import WaveWatchPlotter, WindPlotter, Plotter
        wave = 0
        sst = 1
        wind = 0

        if wave:
            DataFileManager.get_latest_wave_watch_files()
            print "\n--- Plotting WW3 - Height and Direction ---"
            wave = DataFile.objects.filter(type='WAVE').latest('model_date')
            id = wave.id
            for t in xrange(0, 85, 4):
                try:
                    print "Plotting WW3 - File ID:", id, "Time Index:", t
                    tile_wave_watch_overlay(om.make_wave_watch_plot(4, t, id))
                    tile_wave_watch_overlay(om.make_wave_watch_plot(6, t, id))
                    print "plot/tile success"
                except Exception:
                    print '-' * 60
                    traceback.print_exc(file=sys.stdout)
                    print '-' * 60
                print
        if sst:
            #DataFileManager.fetch_new_files()
            print "\n--- Plotting ROMS Fields - SST, Salinity, SSH ---"
            sst_files = DataFile.objects.all().filter(type = "NCDF")
            for file in sst_files:
                plotter = Plotter(file.file.name)
                number_of_times = plotter.get_number_of_model_times()
                id = file.id
                for t in xrange(number_of_times):
                    if t % 2 != 0:
                        try:
                            print "Plotting ROMS - File ID:", id, "Time Index:", t
                            #tile_overlay(om.make_plot(1, t, id))
                            #tile_overlay(om.make_plot(2, t, id))
                            #tile_overlay(om.make_plot(3, t, id))
                            #tile_overlay(om.make_plot(7, t, id))
                            #tile_overlay(om.make_plot(8, t, id))
                            tile_overlay(om.make_plot(9, t, id))
                            print "plot/tile success"
                        except Exception:
                            print '-' * 60
                            traceback.print_exc(file=sys.stdout)
                            print '-' * 60
                        print

        if wind:
            print "\n Plotting NAMS - Winds"
            start = time.time()
            DataFileManager.get_wind_file()
            winds = DataFile.objects.filter(type='WIND').latest('model_date')
            id = winds.id
            plotter = WindPlotter(winds.file.name)
            number_of_times = plotter.get_number_of_model_times()
            for t in xrange(number_of_times):
                try:
                    print "Plotting and Tiling NAMS - Time_Index:", t
                    tile_overlay(om.make_plot(5, t, id))
                    print "plot/tile success"
                except Exception:
                    print '-' * 60
                    traceback.print_exc(file=sys.stdout)
                    print '-' * 60
            end = time.time()
            total = (end - start)/ 60
            print "Total time taken for plotting and tiling = " + str(round(total, 2)) + " minutes"

    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
