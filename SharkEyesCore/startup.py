__author__ = 'avaleske'
from django.conf import settings
from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule
import os
import matplotlib
matplotlib.use('Agg')   # set matplotlib backend to not use xwindow as early as possible in app startup

def run():
    pass
