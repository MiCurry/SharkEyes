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
        sst = 0
        wind = 1
        if wave:
            DataFileManager.get_latest_wave_watch_files()
        if sst:
            DataFileManager.download_osu_roms()
        if wind:
            DataFileManager.get_wind_file()

    elif sys.argv[-1] == "plot":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager
        from pl_chop.tasks import tile_overlay, tile_wave_watch_overlay
        from pl_plot.plotter import WindPlotter, Plotter
        wave = 0
        sst = 0
        wind = 1
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
            print "Time value ", plotter.get_time_at_oceantime_index(0)
            tiles = []
            begin = time.time()
            tiles += OverlayManager.make_plot(5, 63, winds.id)
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
        sst = 0
        wind = 1

        if wave:
            DataFileManager.get_latest_wave_watch_files()
            print "\n--- Plotting WW3 - Height and Direction ---"
            wave = DataFile.objects.filter(type='WAVE').latest('model_date')
            id = wave.id
            for t in xrange(20, 85, 4):
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
            DataFileManager.download_osu_roms()
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
            for t in range(0, number_of_times, 1):
                indices = [55,56,57,59,60,61,63,64,65,67,68]
                if t < 48 and t % 4 == 0:
                    print "Plotting and Tiling NAMS - Time_Index:", t
                    tile_overlay(om.make_plot(5, t, id))
                elif t > 48 and t in indices:
                    print "Plotting and Tiling NAMS - Time_Index:", t
                    tile_overlay(om.make_plot(5, t, id))
                print "plot/tile success"
                print '-' * 60
                traceback.print_exc(file=sys.stdout)
                print '-' * 60
            end = time.time()
            total = (end - start)/ 60
            print "Total time taken for plotting and tiling = " + str(round(total, 2)) + " minutes"

    elif sys.argv[-1] == "wavedates":
        print "Wave Watch Times"
        from datetime import datetime, timedelta
        from django.utils import timezone
        import numpy
        import pytz
        from scipy.io import netcdf
        from django.conf import settings
        from pl_download.models import DataFile
        wave = DataFile.objects.filter(type='WAVE').latest('model_date')
        wave_name = wave.file.name
        wave_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, wave_name), 'r')
        all_day_times = wave_data.variables['time'][:]
        basetime = datetime(1970, 1, 1, 0, 0, 0)  # Jan 1, 1970
        # This is the first forecast: right now it is Noon (UTC) [~5 AM PST] on the day before the file was downloaded
        forecast_zero = basetime + timedelta(all_day_times[0] / 3600.0 / 24.0, 0, 0)
        for x in range(0, 84, 1):
            model_time = timezone.make_aware(forecast_zero + timedelta(hours=x), timezone.utc)
            print "Model date =", model_time, "at index", x

    elif sys.argv[-1] == "alexdates":
        print "Times for Alexander's Model"
        from datetime import datetime, timedelta
        from django.utils import timezone
        import numpy
        import pytz
        from scipy.io import netcdf
        from django.conf import settings
        from pl_download.models import DataFile
        sst = DataFile.objects.all().filter(type="NCDF")
        for x in sst:
            sst_name = x.file.name
            print "File Name ", sst_name
            sst_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR, sst_name), 'r')
            # dst = 0
            # isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
            # if isdst_now_in("America/Los_Angeles"):
            #     dst = -1
            # dst_hours = timedelta(hours=dst)
            ocean_time_epoch = datetime(day=1, month=1, year=2005, hour=0, minute=0, second=0, tzinfo=timezone.utc)
            for x in range(0, numpy.shape(sst_data.variables['ocean_time'])[0], 1):
                seconds_since_epoch = timedelta(seconds=sst_data.variables['ocean_time'][x])
                check_date = ocean_time_epoch + seconds_since_epoch
                print "Date = ", check_date, " at index ", x

    elif sys.argv[-1] == "winddates": #use this to view what the timestamps are for each index of the wind model
        print "Times for the wind model"
        from datetime import datetime, timedelta
        from django.utils import timezone
        import numpy
        import pytz
        from scipy.io import netcdf
        from django.conf import settings
        from pl_download.models import DataFile
        # The Wind model uses a dynamic reference date for date calculation
        # This calculates that date and then uses it to calculate the dates for each index
        windFile = DataFile.objects.filter(type='WIND').latest('model_date')
        windName = windFile.file.name
        windData = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WIND_DIR, windName), 'r')
        # modified_datetime = timezone.make_aware(generated_time, timezone.utc)
        # print "Modified Datetime ", modified_datetime
        time_var = 'time'
        reftime_var = 'reftime'
        try:
            windData.variables["time"]
        except Exception:
            print "Variables = time1"
            time_var = 'time1'
            reftime_var = 'reftime1'
        indices = numpy.shape(windData.variables[time_var])[0]
        print "Indices ", indices
        times = [61,63,64,65,67,68,69,71,72] # 49, 51, 53,  these are setup for when the model swaps to three hour increments use this to view just those dates
        raw_epoch_date = str(windFile.model_date)
        epoch_date = raw_epoch_date.split('-')
        epoch_year = int(epoch_date[0])
        epoch_month = int(epoch_date[1])
        epoch_day = int(epoch_date[2])
        ocean_time_epoch = datetime(day=epoch_day, month=epoch_month, year=epoch_year, hour=0, minute=0, second=0,
                                    tzinfo=timezone.utc)
        print "Ocean Time Epoch ", ocean_time_epoch
        for x in range(0, indices, 1):
            modifier = 0
            # if x < 48 and x % 4 == 0:
            hours_since_epoch = timedelta(hours=(windData.variables[time_var][x] - (windData.variables[reftime_var][0] + modifier)))
            print "Local Time", ocean_time_epoch + hours_since_epoch, " at index ", x
            # elif x in times:
            #     if x == 57 or x == 61:
            #         modifier = 1
            #     elif x == 55 or x == 59 or x == 63:
            #         modifier = -1
            #     hours_since_epoch = timedelta(
            #         hours=(windData.variables['time'][x] + dst - windData.variables['reftime'][0]) + modifier)
            #     print "Time", ocean_time_epoch + hours_since_epoch, " at index ", x

    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
