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
            sst = DataFileManager.fetch_new_files()
            tiles = []
            #first entry is day at 4am
            #NOTE it increments in 4 hour changes
            begin = time.time()
            tiles += OverlayManager.make_plot(1, 0, sst[0])
            #tiles += OverlayManager.make_plot(2, 0, sst[0])
            #tiles += OverlayManager.make_plot(3, 0, sst[0])
            #tiles += OverlayManager.make_plot(7, 0, sst[0])
            #tiles += OverlayManager.make_plot(8, 0, sst[0])
            #tiles += OverlayManager.make_plot(9, 0, sst[0])
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
        wave = 1
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
                            #tile_overlay(om.make_plot(3, t, id))
                            #tile_overlay(om.make_plot(7, t, id))
                            #tile_overlay(om.make_plot(8, t, id))
                            #tile_overlay(om.make_plot(9, t, id))
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

        if hycom:
            print "\n Plotting Hycom"
            for i in range(382, 401):
                tile_overlay(om.make_plot(settings.HYCOM_SST, 0, i))
                tile_overlay(om.make_plot(settings.HYCOM_SUR_CUR, 0, i))


        if ncep:
            print "\n Plotting NCEP"
            for i in range(30, 44):
                tile_overlay(om.make_plot(settings.NCEP_WW3_HI, i, 402))
                tile_overlay(om.make_plot(settings.NCEP_WW3_DIR, i, 402))

    elif sys.argv[-1] == "ww3-test":
        "----- Testing WW3 ----------"
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager as om
        from django.conf import settings
        import datetime


        date = str(datetime.date.today()).replace("-", "", 3)

        test_file = "{0}_{1}.nc".format("ww3", date, )
        dir = os.path.join(settings.MEDIA_ROOT, settings.WW3_DIR)
        file_target = os.path.join(dir, test_file)

        entry = DataFile.objects.filter(
            model_date=datetime.date.today(),
            type='NCDF'
        )

        if os.path.isfile(file_target):
            os.remove(file_target)
        if entry:
            entry.delete()

        file_id = DataFileManager.ww3_download()

        entry = DataFile.objects.filter(
            model_date=datetime.date.today(),
            type='WAVE'
        )


        if os.path.isfile(file_target):
            print "Test 1 Passed - File Succesfully Downloaded"
        else:
            print "Test 1 FAILED - Could not succesfullyt download file"
        if entry:
            print "Test 2 Passed - File Succesfully added to database"
        else:
            print "Test 2 FAILED - Could not sucesfully add file to the database"

        print file_target

        '''
        for i in range(6):
            print "Generating NCEP Dir Overlay: ", i
            om.make_wave_watch_plot(10, i, file_id)

        for i in range(6):
            print "Generating NCEP Height Overlay: ", i
            om.make_wave_watch_plot(11, i, file_id)
        '''

    elif sys.argv[-1] == "hycom-test":
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager
        from django.conf import settings
        import datetime

        print "----- Testing HYCOM Download -----"

        date = str(datetime.date.today()).replace("-", "", 3)

        print "Downloading a bunch of hycom files!"
        #ids = DataFileManager.hycom_download()

        print DataFileManager.get_next_few_datafiles_of_hycom()


        #print "Creating Overlay: HYCOM_SST"
        #OverlayManager.make_plot(settings.HYCOM_SST, 0, 316)
        #print "Creating Overlay: HYCOM_SUR_CUR"
        #OverlayManager.make_plot(settings.HYCOM_SUR_CUR, 0, 316)

    elif sys.argv[-1] == "osu-ww3":
        print
        "----- Testing OSU Height ----------"
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager as om

        id = DataFileManager.get_latest_wave_watch_files()

        """
        for i in range(10):
            om.make_wave_watch_plot(4, i, 290)
            om.make_wave_watch_plot(6, i, 290)
        """

    elif sys.argv[-1] == "ncep-dir":
        print "----- Testing NCEP WW3 Direction ----------"
        from pl_download.models import DataFileManager, DataFile
        from pl_plot.models import OverlayManager as om

        file_id = DataFileManager.ww3_download()

        for i in range(4):
            print "Generating plot ... ", i
            om.make_wave_watch_plot(10, i, file_id)

    elif sys.argv[-1] == "roms_dl":
        print "------ OSU ROMS Download Test ------"
        from pl_download.models import DataFileManager

        DataFileManager.download_osu_roms()

    elif sys.argv[-1] == "task-check":
        from pl_plot.models import OverlayManager

        tl = OverlayManager.get_tasks_for_base_plots_for_next_few_days()
        print tl

    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
