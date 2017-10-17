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
        wave = 0
        sst = 1
        wind = 0
        if wave:
            DataFileManager.get_latest_wave_watch_files()
        if sst:
            DataFileManager.fetch_new_files()
        if wind:
            DataFileManager.get_wind_file()

    elif sys.argv[-1] == "ncdfinfo":
        from datetime import datetime, timedelta
        from django.utils import timezone
        import numpy
        import pytz
        from scipy.io import netcdf
        from django.conf import settings
        from pl_download.models import DataFile
        sst = DataFile.objects.all().filter(type="NCDF")
        sst_name = sst[0].file.name
        sst_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR, sst_name), 'r')
        dst = 0
        isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
        if isdst_now_in("America/Los_Angeles"):
            dst = -1
        dst_hours = timedelta(hours=dst)
        ocean_time_epoch = datetime(day=1, month=1, year=2005, hour=0, minute=0, second=0, tzinfo=timezone.utc)
        for x in range(0, numpy.shape(sst_data.variables['ocean_time'])[0], 1):
            seconds_since_epoch = timedelta(seconds=sst_data.variables['ocean_time'][x])
            check_date = ocean_time_epoch + seconds_since_epoch + dst_hours
            print "check date ", check_date

    elif sys.argv[-1] == "windinfo": #use this to view what the timestamps are for each index of the wind model
        from datetime import datetime, timedelta
        from django.utils import timezone
        import numpy
        import pytz
        from scipy.io import netcdf
        from django.conf import settings
        from pl_download.models import DataFile
        # The Wind model uses a dynamic reference date for date calculation
        # This calculates that date and then uses it to calculate the dates for each index
        dst = 0
        isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
        if isdst_now_in("America/Los_Angeles"):
            dst = 1
        windFile = DataFile.objects.filter(type='WIND').latest('model_date')
        windName = windFile.file.name
        windData = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WIND_DIR, windName), 'r')
        #indices = numpy.shape(windData.variables['time'])[0]
        times = [48,49,51,52,53,55,56,57,59,60,61,63,64]
        for x in times:
            raw_epoch_date = str(windFile.model_date)
            epoch_date = raw_epoch_date.split('-')
            epoch_year = int(epoch_date[0])
            epoch_month = int(epoch_date[1])
            epoch_day = int(epoch_date[2])
            ocean_time_epoch = datetime(day=epoch_day, month=epoch_month, year=epoch_year, hour=7, minute=0, second=0,
                                        tzinfo=timezone.utc)
            modifier = 0
            if x == 49 or x == 53 or x == 57 or x == 61:
                modifier = 1
            elif x == 51 or x == 55 or x == 59 or x == 63:
                modifier = -1
            hours_since_epoch = timedelta(
                hours=(windData.variables['time'][x] + dst - windData.variables['reftime'][0]) + modifier)
            print "Time Index ", x, " Time", ocean_time_epoch + hours_since_epoch

    elif sys.argv[-1] == "plot":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        from pl_plot.plotter import WindPlotter, Plotter
        wave = 0
        sst = 1
        wind = 0
        if wave:
            #wave = DataFileManager.get_latest_wave_watch_files()
            wave = DataFile.objects.filter(type='WAVE').latest('model_date')
            tiles = []
            begin = time.time()
            #first entry is day-1 at 12pm
            #need to offset 16 to match with sst plot
            #NOTE it increments in 1 hour changes
            tiles += OverlayManager.make_wave_watch_plot(4, 16, wave.id)
            tiles += OverlayManager.make_wave_watch_plot(6, 16, wave.id)
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
            tiles += OverlayManager.make_plot(1, 0, sst[0].id)
            #tiles += OverlayManager.make_plot(2, 0, sst[0].id)
            tiles += OverlayManager.make_plot(3, 0, sst[0].id)
            #tiles += OverlayManager.make_plot(7, 0, sst[0].id)
            #tiles += OverlayManager.make_plot(8, 0, sst[0].id)
            #tiles += OverlayManager.make_plot(9, 0, sst[0].id)
            for t in tiles:
                tile_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for SST = " + str(round(totalTime, 2)) + " minutes"

        if wind:
            #winds = DataFileManager.get_wind_file()
            winds = DataFile.objects.filter(type='WIND').latest('model_date')
            plotter = WindPlotter(winds.file.name)
            print "Time value ", plotter.get_time_at_oceantime_index(0)
            tiles = []
            begin = time.time()
            tiles += OverlayManager.make_plot(5, 0, winds.id)
            for t in tiles:
                tile_overlay(t)
            finish = time.time()
            totalTime = (finish - begin)/ 60
            print "Time taken for Winds = " + str(round(totalTime, 2)) + " minutes"

    elif sys.argv[-1] == "plot-all":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager as om
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        from pl_plot.plotter import WindPlotter, Plotter
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
            #DataFileManager.download_osu_roms()
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
                            tile_overlay(om.make_plot(1, t, id))
                            tile_overlay(om.make_plot(2, t, id))
                            tile_overlay(om.make_plot(3, t, id))
                            tile_overlay(om.make_plot(7, t, id))
                            tile_overlay(om.make_plot(8, t, id))
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
                indices = [48, 49, 51, 52, 53, 55, 56, 57, 59, 60, 61, 63, 64]
                if t < 47 and t % 4 == 0:
                    print "t = ", t
                    print "Plotting and Tiling NAMS - Time_Index:", t
                    tile_overlay(om.make_plot(5, t, id))
                elif t > 47 and t in indices:
                    print "t = ", t
                    print "Plotting and Tiling NAMS - Time_Index:", t
                    tile_overlay(om.make_plot(5, t, id))
                print "plot/tile success"
                print '-' * 60
                traceback.print_exc(file=sys.stdout)
                print '-' * 60
            end = time.time()
            total = (end - start)/ 60
            print "Total time taken for plotting and tiling = " + str(round(total, 2)) + " minutes"

    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
