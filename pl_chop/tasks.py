from celery import shared_task
from pl_plot.models import Overlay
from pl_chop import gdal2tiles
from uuid import uuid4
import os
from gdal2tiles import GDAL2Tiles
from django.conf import settings


@shared_task(name='pl_chop.chop_overlay')
def chop_overlay(overlay_id):
    overlay = Overlay.objects.get(pk=overlay_id)
    image = overlay.file
    width = image.width
    height = image.height

    # make sure we have a place to put stuff.
    for directory in [settings.VRT_STORAGE_DIR, settings.TILE_STORAGE_DIR]:
        dest = os.path.join(settings.MEDIA_ROOT, directory)
        if not os.path.exists(dest):
            os.makedirs(dest)

    image_name = os.path.splitext(os.path.split(image.path)[-1])[0] # using a uuid instead to avoid file conflicts
    tile_dir = "tiles-{0}".format(uuid4())
    full_tile_dir = os.path.join(settings.MEDIA_ROOT, settings.TILE_STORAGE_DIR, tile_dir)
    vrt_path = os.path.join(settings.MEDIA_ROOT, settings.VRT_STORAGE_DIR, "{0}.vrt".format(uuid4()))


    '''
    ended up running this manually, which seems to have worked
    gdal_translate -of VRT -a_srs EPSG:4326 -gcp 0 0 -129 47.499  -gcp 2100 0 -123.726 47.499 -gcp 2100 3840 -123.726 40.5833 /home/vagrant/media_root/unchopped/sst_function-56a0e322-c9b9-4213-a938-9d9dd24ad82e.png sst_function-56a0e322-c9b9-4213-a938-9d9dd24ad82e.vrt

    also installing the proj package
    and this link
    sudo ln -s /usr/lib64/libproj.so.0 /usr/lib64/libproj.so

    /home/vagrant/virtualenvs/sharkeyes/bin/python gdal2tiles.py --profile=mercator -z 4-10 sst_function-56a0e322-c9b9-4213-a938-9d9dd24ad82e.vrt asdf_tiles
    '''

    translate_cmd = ("sleep 10 && gdal_translate -of VRT -a_srs EPSG:4326 -gcp 0 0 -129 47.499 "
                     "-gcp {0} 0 -123.726 47.499 -gcp {0} {1} -123.726 40.5833 {2} {3} && echo done").format(
            str(width), str(height), image.path, vrt_path)

    os.system(translate_cmd)

    params = ['--profile=mercator', '-z', '4-10', vrt_path, full_tile_dir]
    tile_generator = GDAL2Tiles(params)
    tile_generator.process()

    overlay.tile_dir = tile_dir
    overlay.save()
    return tile_dir