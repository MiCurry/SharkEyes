import os
import urllib
import urllib2
from ftplib import FTP
from defusedxml import ElementTree
from lxml import etree
from uuid import uuid4
from urlparse import urljoin
from datetime import datetime, timedelta
from dateutil import parser
from operator import __or__ as OR
from scipy.io import netcdf_file

from celery import shared_task
from django.utils import timezone
from django.db.models.aggregates import Max
from django.db.models import Q
from django.db import models
from django.conf import settings


CATALOG_XML_NAME = "catalog.xml"
XML_NAMESPACE = "{http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0}"
HOW_LONG_TO_KEEP_FILES = settings.HOW_LONG_TO_KEEP_FILES

# This is how many days' worth of older forecasts to grab from the database
PAST_DAYS_OF_FILES_TO_DISPLAY = settings.PAST_DAYS_OF_FILES_TO_DISPLAY


def extract_modified_datetime_from_xml(elem):
    modified_datetime_string = elem.find(XML_NAMESPACE + 'date').text
    naive_datetime = parser.parse(
        modified_datetime_string)  # the date in the xml file follows iso standards, so we're gold.
    modified_datetime = timezone.make_aware(naive_datetime, timezone.utc)
    return modified_datetime


def get_ingria_xml_tree():
    # todo: need to handle if the xml file isn't available
    xml_url = urljoin(settings.BASE_NETCDF_URL, CATALOG_XML_NAME)
    catalog_xml = urllib2.urlopen(xml_url)
    tree = ElementTree.parse(catalog_xml)
    return tree

class DataFileManager(models.Manager):
    @staticmethod
    @shared_task(name='pl_download.fetch_new_files')
    def fetch_new_files():
        """ DEPRECATED - DOWNLOAD IS UNRELIABLE - Downloads OSU ROMS forecast model as a NCDF from
        http://ingria.coas.oregonstate.edu/opendap/ORWA/.

        :return: ids of downloaded files
        """
        if not DataFileManager.is_new_file_to_download():
            print "No New SST Files Available."
            return []

        # download new file for next few days
        days_to_retrieve = [timezone.now().date(),
                             timezone.now().date()+timedelta(days=1),
                            timezone.now().date()+timedelta(days=2),
                            timezone.now().date()+timedelta(days=3)]

        print "NetCDF File Dates To Attempt Retrieval Of:"
        print "\t" + str(days_to_retrieve[0])
        print "\t" + str(days_to_retrieve[1])
        print "\t" + str(days_to_retrieve[2])
        print "\t" + str(days_to_retrieve[3])

        files_to_retrieve = []
        tree = get_ingria_xml_tree()    # yes, we just did this to see if there's a new file. refactor later.
        tags = tree.iter(XML_NAMESPACE + 'dataset')

        for elem in tags:
            server_filename = elem.get('name')
            if not server_filename.startswith('ocean_his'):
                continue
            date_string_from_filename = server_filename.split('_')[-1]
            model_date = datetime.strptime(date_string_from_filename, "%d-%b-%Y.nc").date()   # this could fail, need error handling badly
            modified_datetime = extract_modified_datetime_from_xml(elem)

            for day_to_retrieve in days_to_retrieve:
                if model_date - day_to_retrieve == timedelta(days=0):
                    files_to_retrieve.append((server_filename, model_date, modified_datetime))
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)

        new_file_ids = []

        for server_filename, model_date, modified_datetime in files_to_retrieve:
            url = urljoin(settings.BASE_NETCDF_URL, server_filename)
            local_filename = "{0}_{1}.nc".format(settings.OSU_ROMS_DF_FN, model_date)
            print "Retrieving: " + str(local_filename)
            urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename)) # this also needs a try/catch
            datafile = DataFile(
                type='NCDF',
                download_datetime=timezone.now(),
                generated_datetime=modified_datetime,
                model_date=model_date,
                file=local_filename,
            )
            datafile.save()

            new_file_ids.append(datafile.id)

        return new_file_ids

    @staticmethod
    @shared_task(name='pl_download.download_osu_roms')
    def download_osu_roms():
        """ Downloads Alex's K's OSU ROMS' Model from Craig Risens 'Wilson' server:
        http://wilson.coas.oregonstate.edu:8080/thredds/catalog/NANOOS/OCOS_Files/catalog.html

        url = "http://wilson.coas.oregonstate.edu:8080/thredds/fileServer/NANOOS/OCOS_Files/ocean_his_"+ref_number+model_date+".nc"

        :return: File id's of the downloaded files
        """
        verbose = 0

        if verbose > 0:
            print "OSU_ROMS DOWNLOAD"

        local_filename = ""
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)
        BASE_URL = "http://wilson.coas.oregonstate.edu:8080/thredds/fileServer/NANOOS/OCOS_Files/"
        XML_URL = 'http://wilson.coas.oregonstate.edu:8080/thredds/catalog/NANOOS/OCOS_Files/catalog.xml'

        catalog = etree.parse(XML_URL)

        file_ids = []

        for element in catalog.iter():
            file = element.get('name')

            if not file:
                continue
            elif file.startswith('ocean_his'):
                datestring = file.split('_')[-1]
                file_date = datetime.strptime(datestring, "%d-%b-%Y.nc").date()

                url = BASE_URL + file
                local_filename = "{0}_{1}.nc".format(settings.OSU_ROMS_DF_FN, file_date)

                try:
                    print "Downloading OSU ROMS File {0}".format(url,)
                    urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))
                    datafile = DataFile(
                        type='NCDF',
                        download_datetime=timezone.now(),
                        generated_datetime=timezone.now(),
                        model_date=file_date,
                        file=local_filename,
                    )
                    datafile.save()
                    file_ids.append(datafile.id)

                except Exception:
                    print "Unable to download OSU ROMS File from wilson.coas.oregonstat.edu"
                    continue

                print "Downloaded OSU ROMS File from wilson {0}".format(local_filename)

        return file_ids

    @staticmethod
    @shared_task(name='pl_download.get_latest_wave_watch_files')
    def get_latest_wave_watch_files():
        """ Downloads OSU WW3 forecasts from Tuba's server as a NCDF File

        :return: id's of downloaded files
        """

        new_file_ids = []

        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR)

        #outer.nc is the low-resolution grid, osuww3.nc is the grid with both high- and low-res data compiled into one.
        #static_file_names = ["shelf1.nc", "shelf2.nc", "shelf3.nc"]
        file_name = "osuww3.nc"

        ftp = FTP('cil-www.oce.orst.edu')
        ftp.login()

        # retrieve the ftp modified datetime format
        ftp_dtm = ftp.sendcmd('MDTM' + " /pub/outgoing/ww3data/" + file_name)
        initial_datetime = datetime.strptime(ftp_dtm[4:], "%Y%m%d%H%M%S").strftime("%Y-%m-%d")

        naive_datetime = parser.parse(initial_datetime)
        modified_datetime = timezone.make_aware(naive_datetime, timezone.utc)

        # Check if we've downloaded it before: does DataFile contain a Wavewatch entry whose model_date matches this one?
        matches_old_file = DataFile.objects.filter(
            #NOTE: this assumes that the file contains one day of hindcasts, so the model date is one day BEHIND
            # the date on which we download the file.
            # This is prone to fail. However, when we actually save the record in the database,
            # THAT model_date is guaranteed to be correct.
            model_date=datetime.date( modified_datetime - timedelta(days=1)),
            type='WAVE'
        )
        if not matches_old_file:
            print "New OSU WW3 File"

            url = urljoin(settings.WAVE_WATCH_URL, file_name)
            local_filename = "{0}_{1}.nc".format(settings.OSU_WW3_DF_FN, initial_datetime)
            urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))

            file = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, local_filename))

            # The times in the file are UTC in seconds since Jan 1, 1970.
            all_day_times = file.variables['time'][:]
            basetime = datetime(1970,1,1,0,0,0)
            first_forecast_time = basetime + timedelta(all_day_times[0]/3600.0/24.0,0,0)

            datafile = DataFile(
                type='WAVE',
                download_datetime=timezone.now(), # This is UTC, as should be all the items saved into a Django database
                generated_datetime=modified_datetime,
                model_date = first_forecast_time,
                file=local_filename,
            )
            datafile.save()

            new_file_ids.append(datafile.id)
            ftp.quit()

            return new_file_ids
        else:
            print "No New OSU WW3 Files."
            ftp.quit()
            return []

    @staticmethod
    @shared_task(name='pl_download.get_wind_file')
    def get_wind_file():
        """ Downloads a NAM's WIND forecast as a NCDF File.

        :return:
        """
        #list of file ids created
        new_file_ids = []

        #Directory where files will be saved
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.WIND_DIR)

        current_time = datetime.now().date()
        generated_time = datetime.now().today()
        modified_datetime = timezone.make_aware(generated_time, timezone.utc)
        end_time = datetime.now().date()+timedelta(days=4)
        begin = str(current_time) + 'T00%3A00%3A00Z'
        end = str(end_time) + 'T00%3A00%3A00Z'

        local_filename = "{0}_{1}.nc".format(settings.NAMS_WIND_DF_FN, current_time)

        #Check to see if we've download this file before
        matches_old_file = DataFile.objects.filter(
            model_date=current_time,
            type='WIND'
        )

        hour_check = 0
        current_date = datetime.now()
        early_time = datetime(day=current_date.day, month=current_date.month, year=current_date.year, hour=4, minute=0,second=0)
        late_time = datetime(day=current_date.day, month=current_date.month, year=current_date.year, hour=19, minute=0,second=0)
        generated_time = datetime.now().today()
        if generated_time < early_time or generated_time > late_time:
            hour_check = 1

        if not matches_old_file and hour_check == 1:
            print "Downloading Wind file "
            #If you need to modify the time, or coordinates for the downloaded wind file change this values in url
            url = 'http://thredds.ucar.edu/thredds/ncss/grib/NCEP/NAM/CONUS_12km/conduit/Best?var=u-component_of_wind_height_above_ground&var=v-component_of_wind_height_above_ground&north=48.563922&west=-129.876507&east=-123.863860&south=40&disableProjSubset=on&horizStride=1&time_start='+begin+'&time_end='+end+'&timeStride=1&vertCoord=&addLatLon=true&accept=netcdf'
            urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))
            print "Download Complete "

            #Saving the file to the database
            datafile = DataFile(
                type='WIND',
                download_datetime=timezone.now(),
                generated_datetime=modified_datetime,
                model_date=current_time,
                file=local_filename,
            )
            datafile.save()
            new_file_ids.append(datafile.id)

            return new_file_ids
        else:
            print "No new wind files "
            return []

    @classmethod
    def is_new_file_to_download(cls):
        """ DEPRECATED: Determine if there is a new file to download. Used by fetch_new_file and uses
        the old download location """
        three_days_ago = timezone.now().date()-timedelta(days=3)
        today = timezone.now().date()

        recent_netcdf_files = DataFile.objects.filter(type="NCDF", model_date__range=[three_days_ago, today])

        if not recent_netcdf_files:
            return True

        local_file_modified_datetime = recent_netcdf_files.latest('generated_datetime').generated_datetime

        tree = get_ingria_xml_tree()
        tags = tree.iter(XML_NAMESPACE + 'dataset')

        for elem in tags:
            if not elem.get('name').startswith('ocean_his'):
                continue
            server_file_modified_datetime = extract_modified_datetime_from_xml(elem)
            if server_file_modified_datetime.date() > local_file_modified_datetime.date():
                return True

        return False

    @classmethod
    def get_next_few_days_files_from_db(cls):
        """ This function gets the file ID's from the database that do not have plots.

        :return: A list of
        """
        next_few_days_of_files = DataFile.objects.filter(
            model_date__gte=(timezone.now()-timedelta(days=PAST_DAYS_OF_FILES_TO_DISPLAY+1)).date(),
            model_date__lte=(timezone.now()+timedelta(days=4)).date()
        )

        # Select the most recent within each model date and type (ie wave or SST)
        and_the_newest_for_each_model_date = next_few_days_of_files.values('model_date', 'type').annotate(newest_generation_time=Max('generated_datetime'))

        # if we expected a lot of new files, this would be bad (we're making a Q object for each file we want, basically)
        q_objects = []
        for filedata in and_the_newest_for_each_model_date:
            new_q = Q(type=filedata.get('type'), model_date=filedata.get('model_date'),
                      generated_datetime=filedata.get('newest_generation_time'))
            q_objects.append(new_q)

        # assumes you're not re-downloading the same file for the same model and generation dates.
        actual_datafile_objects = DataFile.objects.filter(reduce(OR, q_objects))

        return actual_datafile_objects


    @classmethod
    def delete_old_files(cls):
        """ Used to automatically delete files from the disk. This runs each time do_pipeline() is run, which
        is every 6 hours
        """
        how_old_to_keep = timezone.datetime.now()-timedelta(days=HOW_LONG_TO_KEEP_FILES)
        # NETCDF files
        # delete files whose model date is earlier than how old we want to keep.
        old_netcdf_files = DataFile.objects.filter(model_date__lte=how_old_to_keep)
        # Delete the file items from the database, and the actual image files.
        for filename in old_netcdf_files:
            DataFile.delete(filename) # Custom delete method for DataFiles: this deletes the actual files from disk too

        return True

class DataFile(models.Model):
    """ The Model or "Object" that is used by our Web Management Server (Django) to describe our
    downloaded files. Objects are created and then they are stored in a table inside our database
    by calling datafile.save().

    If this is edited you must migrate the appropriate servers.
    """
    DATA_FILE_TYPES = (
        ('NCDF', "NetCDF"), ('WAVE', "WaveNETCDF"), ('WIND', "WindNETCDF")
    )
    type = models.CharField(max_length=10, choices=DATA_FILE_TYPES, default='NCDF')
    download_datetime = models.DateTimeField()
    generated_datetime = models.DateTimeField()
    model_date = models.DateField()
    file = models.FileField(upload_to=settings.NETCDF_STORAGE_DIR, null=True)

    def delete(self,*args,**kwargs):
        """ Custom delete method which will also delete the DataFile's image file from the disk """
        alex_model_path = os.path.join(
            settings.MEDIA_ROOT  + settings.NETCDF_STORAGE_DIR + "/" + self.file.name)

        wave_model_path = os.path.join(
            settings.MEDIA_ROOT + settings.WAVE_WATCH_DIR + "/" + self.file.name
        )

        wind_model_path = os.path.join(
            settings.MEDIA_ROOT + settings.WIND_DIR + "/" + self.file.name
        )

        if os.path.isfile(alex_model_path):
            os.remove(alex_model_path)

        if os.path.isfile(wave_model_path):
            os.remove(wave_model_path)

        if os.path.isfile(wind_model_path):
            os.remove(wind_model_path)

        #Delete the model instance
        super(DataFile, self).delete(*args,**kwargs)
