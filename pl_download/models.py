from celery import shared_task
from django.utils import timezone
import urllib
import socket
import os
from uuid import uuid4
from urlparse import urljoin
import urllib2
from defusedxml import ElementTree
from datetime import datetime, timedelta
from dateutil import parser
from django.db.models.aggregates import Max
from django.db.models import Q
from operator import __or__ as OR
from ftplib import FTP
from django.db import models
from scipy.io import netcdf_file
from django.conf import settings

CATALOG_XML_NAME = "catalog.xml"
XML_NAMESPACE = "{http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0}"
HOW_LONG_TO_KEEP_FILES = settings.HOW_LONG_TO_KEEP_FILES

#This is how many days' worth of older forecasts to grab from the database
PAST_DAYS_OF_FILES_TO_DISPLAY = settings.PAST_DAYS_OF_FILES_TO_DISPLAY


#Function used to format a date string for the alternate download option
def make_date_string(dateString):
        newdate = dateString.split("-")
        month = ""
        if newdate[1] == '01':
            month = "Jan"
        elif newdate[1] == '02':
            month = "Feb"
        elif newdate[1] == '03':
            month = "Mar"
        elif newdate[1] == '04':
            month = "Apr"
        elif newdate[1] == '05':
            month = "May"
        elif newdate[1] == '06':
            month = "Jun"
        elif newdate[1] == '07':
            month = "Jul"
        elif newdate[1] == '08':
            month = "Aug"
        elif newdate[1] == '09':
            month = "Sep"
        elif newdate[1] == '10':
            month = "Oct"
        elif newdate[1] == '11':
            month = "Nov"
        else:
            month = "Dec"
        modified_date = newdate[2] + "-" + month +"-"+ newdate [0]
        return modified_date

#gets list of avalible files on ftp site (SST)
def get_ingria_xml_tree():
    # todo: need to handle if the xml file isn't available
    xml_url = urljoin(settings.BASE_NETCDF_URL, CATALOG_XML_NAME)
    catalog_xml = urllib2.urlopen(xml_url)
    tree = ElementTree.parse(catalog_xml)
    return tree

def extract_modified_datetime_from_xml(elem):
    modified_datetime_string = elem.find(XML_NAMESPACE + 'date').text
    naive_datetime = parser.parse(modified_datetime_string)  # the date in the xml file follows iso standards, so we're gold.
    modified_datetime = timezone.make_aware(naive_datetime, timezone.utc)
    return modified_datetime


class DataFileManager(models.Manager):
    # grabs file for next few days.
    # todo make each file download in a separate task
    @staticmethod
    @shared_task(name='pl_download.fetch_new_files')

    #FETCH FILES FOR CURRENTS AND SST
    def fetch_new_files():
        alternate = 0
        if alternate == 0:
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
                local_filename = "{0}_{1}.nc".format(model_date, uuid4())
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

        #The normal server we use can be unreliable. Using this alternate downloader will get the files from a more reliable server. This method
        #requires you to check the server at http://wilson.coas.oregonstate.edu:8080/thredds/catalog/NANOOS/OCOS_Files/catalog.html
        #for the current newNum values. It will be a four digit number after ocean_his in the filename. Use the value for the current day's file
        elif alternate == 1:
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

            new_file_ids = []
            files_to_retrieve = []
            destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)
            for x in range(0, 3, 1):
                #newNum is the number corresponding to the filename numbers from the server. You will need to check the server for the current numbers.
                newNum = 4506 + x #4455 is old. This number needs to be changed to match the current server files each time you run the alternate downloader.
                ref_number = str(newNum) + "_"
                model_date = make_date_string(str(datetime.now().date()+timedelta(days=x)))
                files_to_retrieve.append((model_date, ref_number))

            for model_date, stupid_number in files_to_retrieve:
                url = "http://wilson.coas.oregonstate.edu:8080/thredds/fileServer/NANOOS/OCOS_Files/ocean_his_"+ref_number+model_date+".nc"
                print "url", url
                local_filename = "{0}_{1}.nc".format(model_date, uuid4())
                print "Retrieving: " + str(local_filename)
                urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))
                datafile = DataFile(
                    type='NCDF',
                    download_datetime=timezone.now(),
                    generated_datetime=timezone.now(),
                    model_date=datetime.now().date(),
                    file=local_filename,
                )
            datafile.save()
            new_file_ids.append(datafile.id)

            return new_file_ids

    @staticmethod
    @shared_task(name='pl_download.get_latest_wave_watch_files')
    def get_latest_wave_watch_files():
        #list of the new file ids created in this function
        new_file_ids = []

        #directory of where files will be saved at
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR)

        #file names might need to be created dynamically in the future if ftp site changes
        #outer.nc is the low-resolution grid, osuww3.nc is the grid with both high- and low-res data compiled into one.
        #file_name = "outer.nc"
        file_name = "osuww3.nc"
        #static_file_names = ["shelf1.nc", "shelf2.nc", "shelf3.nc"]

        #Connect to FTP site to get the file modification data
        ftp = FTP('cil-www.oce.orst.edu')
        ftp.login()

        #retrieve the ftp modified datetime format
        ftp_dtm = ftp.sendcmd('MDTM' + " /pub/outgoing/ww3data/" + file_name)

        #convert ftp datetime format to a string datetime
        initial_datetime = datetime.strptime(ftp_dtm[4:], "%Y%m%d%H%M%S").strftime("%Y-%m-%d")

        naive_datetime = parser.parse(initial_datetime)
        modified_datetime = timezone.make_aware(naive_datetime, timezone.utc)

        # check if we've downloaded it before: does DataFile contain a Wavewatch entry whose model_date matches this one?
        matches_old_file = DataFile.objects.filter(
            #NOTE: this assumes that the file contains one day of hindcasts, so the model date is one day BEHIND
            # the date on which we download the file.
            # This is prone to fail. However, when we actually save the record in the database,
            # THAT model_date is guaranteed to be correct.
            model_date=datetime.date( modified_datetime - timedelta(days=1)),
            type='WAVE'
        )
        if not matches_old_file:
            print "new wavewatch"
            #Create File Name and Download actual File into media folder
            url = urljoin(settings.WAVE_WATCH_URL, file_name)
            # The date in local_filename is actually 1 day LATER than the file actually applies at
            local_filename = "{0}_{1}_{2}.nc".format("OuterGrid", initial_datetime, uuid4())
            urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))
            file = netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR, local_filename))
            # The times in the file are UTC in seconds since Jan 1, 1970.
            all_day_times = file.variables['time'][:]
            basetime = datetime(1970,1,1,0,0,0)
            # Check the first value of the forecast
            first_forecast_time = basetime + timedelta(all_day_times[0]/3600.0/24.0,0,0)
            #Save the File name into the Database
            datafile = DataFile(
                type='WAVE',
                download_datetime=timezone.now(), # This is UTC, as should be all the items saved into a Django database
                generated_datetime=modified_datetime,
                model_date = first_forecast_time,
                file=local_filename,
            )
            datafile.save()
            new_file_ids.append(datafile.id)
            #quit ftp connection cause we accessed all the data we need
            ftp.quit()
            return new_file_ids
        #Must have already downloaded this file
        else:
            print "No New Wave Watch Files."
            ftp.quit()
            return []

    @staticmethod
    @shared_task(name='pl_download.get_wind_file')
    def get_wind_file():
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

        local_filename = "{0}_{1}_{2}.nc".format("WIND", current_time, uuid4())

        #Check to see if we've download this file before
        matches_old_file = DataFile.objects.filter(
            model_date=current_time,
            type='WIND'
        )

        if not matches_old_file:
            print "Downloading Wind file "
            #If you need to modify the time, or coordinates for the downloaded wind file change this values in url
            url = 'http://thredds.ucar.edu/thredds/ncss/grib/NCEP/NAM/CONUS_12km/conduit/Best?var=u-component_of_wind_height_above_ground&var=v-component_of_wind_height_above_ground&north=48.563922&west=-129.876507&east=-123.863860&south=40&horizStride=1&time_start='+begin+'&time_end='+end+'&timeStride=1&vertCoord=&addLatLon=true&accept=netcdf'
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
    def get_next_few_days_files_from_db(cls):
        next_few_days_of_files = DataFile.objects.filter(
            model_date__gte=(timezone.now()-timedelta(days=PAST_DAYS_OF_FILES_TO_DISPLAY+1)).date(),
            model_date__lte=(timezone.now()+timedelta(days=4)).date()
        )

        #Select the most recent within each model date and type (ie wave or SST)
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
    def is_new_file_to_download(cls):
        three_days_ago = timezone.now().date()-timedelta(days=3)
        today = timezone.now().date()

        #Just for ROMS model
        recent_netcdf_files = DataFile.objects.filter(type="NCDF", model_date__range=[three_days_ago, today])

        # empty lists return false
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
    def delete_old_files(cls):
        how_old_to_keep = timezone.datetime.now()-timedelta(days=HOW_LONG_TO_KEEP_FILES)

        # NETCDF files
        # delete files whose model date is earlier than how old we want to keep.
        old_netcdf_files = DataFile.objects.filter(model_date__lte=how_old_to_keep)

        # Delete the file items from the database, and the actual image files.
        for filename in old_netcdf_files:
            DataFile.delete(filename) # Custom delete method for DataFiles: this deletes the actual files from disk too

        return True

class DataFile(models.Model):
    DATA_FILE_TYPES = (
        ('NCDF', "NetCDF"), ('WAVE', "WaveNETCDF"), ('WIND', "WindNETCDF")
    )
    type = models.CharField(max_length=10, choices=DATA_FILE_TYPES, default='NCDF')
    download_datetime = models.DateTimeField()
    generated_datetime = models.DateTimeField()
    model_date = models.DateField()
    file = models.FileField(upload_to=settings.NETCDF_STORAGE_DIR, null=True)

    #Custom delete method which will also delete the DataFile's image file from the disk
    def delete(self,*args,**kwargs):
        #Seems to be a Django bug (?) which gives the wrong path for self.file.path. This is a workaround.
        pathName = os.path.join(
        settings.MEDIA_ROOT  + settings.NETCDF_STORAGE_DIR + "/" + self.file.name)

        if os.path.isfile(pathName):
            #Delete the physical file from disk
            os.remove(pathName)

        #Delete the model instance
        super(DataFile, self).delete(*args,**kwargs)

