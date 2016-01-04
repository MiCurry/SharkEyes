#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SharkEyesCore.settings")

    import SharkEyesCore.startup as startup
    startup.run()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)



def setUP():
    from pl_download.models import DataFileManager
    from pl_plot.models import OverlayManager



