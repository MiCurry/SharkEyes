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
        tcline = 0
        if wave:
            DataFileManager.get_latest_wave_watch_files()
        if sst:
            DataFileManager.download_osu_roms()
        if wind:
            DataFileManager.get_wind_file()
        if tcline:
            DataFileManager.download_tcline()

    elif sys.argv[-1] == "plot":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        from pl_plot.plotter import WindPlotter, Plotter
        wave = 0
        sst = 0
        wind = 1
        t_cline = 1

        if wave:
            #DataFileManager.get_latest_wave_watch_files()
            wave = DataFile.objects.filter(type='WAVE').latest('model_date')
            tiles = []
            begin = time.time()
            #first entry is day-1 at 12pm
            #need to offset 16 to match with sst plot
            #NOTE it increments in 1 hour changes
            tiles += OverlayManager.make_wave_watch_plot(4, 20, wave.id)
            #tiles += OverlayManager.make_wave_watch_plot(6, 20, wave.id)
            for t in tiles:
                tile_wave_watch_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for Waves = " + str(round(totalTime, 2)) + " minutes"
        if sst:

            #sst = DataFileManager.download_osu_roms()
            sst = DataFile.objects.all().filter(type="NCDF")
            #plotter = Plotter(sst[0].file.name)
            #print "Time value ", plotter.get_time_at_oceantime_index(0)

            tiles = []
            begin = time.time()
            tiles += OverlayManager.make_plot(1, 5, sst[2].id)
            # tiles += OverlayManager.make_plot(2, 3, sst[2].id)
            # tiles += OverlayManager.make_plot(3, 3, sst[2].id)
            # tiles += OverlayManager.make_plot(7, 3, sst[2].id)
            # tiles += OverlayManager.make_plot(8, 3, sst[2].id)
            # tiles += OverlayManager.make_plot(9, 3, sst[2].id)
            for t in tiles:
                tile_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for SST = " + str(round(totalTime, 2)) + " minutes"

        if wind:
            #winds = DataFileManager.get_wind_file()
            winds = DataFile.objects.filter(type='WIND').latest('model_date')
            plotter = WindPlotter(winds.file.name)
            x = 0
            print "Time value ", plotter.get_time_at_oceantime_index(x)
            tiles = []
            begin = time.time()
            tiles += OverlayManager.make_plot(5, x, winds.id)
            for t in tiles:
                tile_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for Winds = " + str(round(totalTime, 2)) + " minutes"

        if t_cline:
            #thermo = DataFileManager.download_tcline()
            thermo = DataFile.objects.filter(type='T-CLINE').latest('model_date')
            tiles = []
            begin = time.time()
            tiles += OverlayManager.make_plot(14, 0, thermo.id)
            for t in tiles:
                tile_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for T-Cline = " + str(round(totalTime, 2)) + " minutes"

    elif sys.argv[-1] == "plot-all":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager as om
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        from pl_plot.plotter import WindPlotter, Plotter
        from datetime import datetime, timedelta
        wave = 1
        sst = 0
        wind = 0

        if wave:
            #DataFileManager.get_latest_wave_watch_files()
            print "\n--- Plotting WW3 - Height and Direction ---"
            wave = DataFile.objects.filter(type='WAVE').latest('model_date')
            wind_id = wave.id
            for t in xrange(80, 85, 4):
                try:
                    print "Plotting WW3 - File ID:", wind_id, "Time Index:", t
                    tile_wave_watch_overlay(om.make_wave_watch_plot(4, t, wind_id))
                    #tile_wave_watch_overlay(om.make_wave_watch_plot(6, t, wind_id))
                    print "plot/tile success"
                except Exception:
                    print '-' * 60
                    traceback.print_exc(file=sys.stdout)
                    print '-' * 60
                print
        if sst:
            DataFileManager.download_osu_roms()
            print "\n--- Plotting ROMS Fields - SST, Salinity, SSH ---"
            sst_files = DataFile.objects.all().filter(type = "NCDF")
            for file in sst_files:
                plotter = Plotter(file.file.name)
                number_of_times = plotter.get_number_of_model_times()
                wind_id = file.id
                for t in xrange(number_of_times):
                    if t % 2 != 0:
                        try:
                            print "Plotting ROMS - File ID:", wind_id, "Time Index:", t
                            tile_overlay(om.make_plot(1, t, wind_id))
                            tile_overlay(om.make_plot(2, t, wind_id))
                            tile_overlay(om.make_plot(3, t, wind_id))
                            tile_overlay(om.make_plot(7, t, wind_id))
                            tile_overlay(om.make_plot(8, t, wind_id))
                            tile_overlay(om.make_plot(9, t, wind_id))
                            print "plot/tile success"
                        except Exception:
                            print '-' * 60
                            traceback.print_exc(file=sys.stdout)
                            print '-' * 60
                        print

        if wind:
            print "\n Plotting NAMS - Winds"
            start = time.time()
            #DataFileManager.get_wind_file()
            winds = DataFile.objects.filter(type='WIND').latest('model_date')
            wind_id = winds.id
            plotter = WindPlotter(winds.file.name)
            number_of_times = plotter.get_number_of_model_times()
            wind_values = plotter.get_wind_indices()
            begin = wind_values['begin']
            print "Begin = ", begin
            swap = wind_values['swap']
            print "Swap = ", swap
            three_hour_indices = wind_values['indices']
            print "Indices = ", three_hour_indices
            print "Pre Swap"
            for t in range(begin, swap, 4):
                print "Plotting and Tiling NAMS - Time: ", plotter.get_time_at_oceantime_index(t)- timedelta(hours=8)
                tile_overlay(om.make_plot(5, t, wind_id))
            print "Post Swap"
            for t in range(swap, number_of_times, 1):
                if t in three_hour_indices:
                    print "Plotting and Tiling NAMS - Time: ", plotter.get_time_at_oceantime_index(t)-timedelta(hours=8)
                    tile_overlay(om.make_plot(5, t, wind_id))
            print "plot/tile success"
            end = time.time()
            total = (end - start)/ 60
            print "Total time taken for plotting and tiling = " + str(round(total, 2)) + " minutes"

    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
