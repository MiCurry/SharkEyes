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
        wave = DataFileManager.get_latest_wave_watch_files();
        sst = DataFileManager.fetch_new_files();
        if wave:
            tiles = []
            #first entry is day-1 at 12pm
            #need to offset 16 to match with sst plot
            #NOTE it increments in 1 hour changes
            tiles += OverlayManager.make_wave_watch_plot(4, 16, wave[0])
            tiles += OverlayManager.make_wave_watch_plot(6, 16, wave[0])
            tiles += OverlayManager.make_wave_watch_plot(7, 16, wave[0])
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
    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)