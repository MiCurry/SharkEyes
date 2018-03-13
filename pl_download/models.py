import traceback

import os
import urllib
import urllib2
from ftplib import FTP

import sys
from defusedxml import ElementTree
from lxml import etree, html
import requests
from uuid import uuid4
from lxml import etree
from urlparse import urljoin
from datetime import datetime, timedelta
import datetime as dt
from dateutil import parser
from operator import __or__ as OR
from scipy.io import netcdf_file
from scipy.io import netcdf
import pydap.client

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


seacast_lats = settings.SEACAST_DOMAIN['longs']
seacast_longs = settings.SEACAST_DOMAIN['lats']
lat = seacast_lats
long = seacast_longs

def extract_modified_datetime_from_xml(elem):
    modified_datetime_string = elem.find(XML_NAMESPACE + 'date').text
    naive_datetime = parser.parse(
        modified_datetime_string)  # the date in the xml file follows iso standards, so we're gold.
    modified_datetime = timezone.make_aware(naive_datetime, timezone.utc)
    return modified_datetime



def get_unidata_xml_tree():

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
        tree = get_unidata_xml_tree()    # yes, we just did this to see if there's a new file. refactor later.
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
                    urllib.urlretrieve(url=url,
                                       filename=os.path.join(destination_directory, local_filename),
                                       )
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
    @shared_task(name='pl_download.rtofs_download_openDAP')
    def rtofs_download_openDAP(count=None):
        """ Construct a NetCDF by accessing the fields using OPeNDAP

        OPeNDAP/DODS Data URL:
        http://nomads.ncep.noaa.gov:9090/dods/rtofs/rtofs_global20180104/rtofs_glo_3dz_forecast_6hrly_us_west

        http://nomads.ncep.noaa.gov:9090/dods/rtofs/rtofs_global20180104/rtofs_glo_3dz_forecast_6hrly_us_west

        https://publicwiki.deltares.nl/display/OET/Reading+data+from+OpenDAP+using+python

        settings.HYCOM_OPDAP_URL = "http://nomads.ncep.noaa.gov:9090/dods/rtofs/"

        :param count:
        :return:
        """

        HYCOM_SUBSET_US_WEST_6HRLY = "/rtofs_glo_3dz_forecast_6hrly_us_west"
        SALNITY = 'sea_water_salinity'
        TEMPEATURE = 'sea_water_potential_temperature'
        U = 'eastward_sea_water_velocity'
        V = 'northward_sea_water_velocity'


        verbose = 1

        # Construct URL
        date = str(dt.date.today()).replace("-", "", 3) # Todays Date used for access
        index_url = settings.HYCOM_OPENDAP_URL+"rtofs_global"+date+HYCOM_SUBSET_US_WEST_6HRLY

        dataset = pydap.client.open_url(index_url)

        if verbose > 0:
            print "ACCESS URL: ", index_url
            print "Access Successful: ", index_url


        print list(dataset.keys())

        """ NetCDF Info
        
        Dimensions - Records name and length of each dimension used by the variables
        
        Variables - Indicate which dimensions it uses and any attributes such as data 
        units along with containg the data values for the variable
        """

        SEACAST_DOMAIN = settings.SEACAST_DOMAIN
        SEACAST_DOMAIN = {'longs': [-129.0, -123.726199391], 'lats': [40.5840806224, 47.499]}
        LONS = SEACAST_DOMAIN['longs'][0]
        LATS = SEACAST_DOMAIN['lats'][0]

        # Dimensions
        time = dataset['time'][1]
        lev = dataset['lev'][0]
        lat = dataset['lat'][936:]
        lon = dataset['lon']

        def convert_to_degrees_west(x):
            y = 180 - (x); return -(y + 180)

        j = 0
        for i in lon:
            print "J ", j ," lon", i, convert_to_degrees_west(i)
            j += 1

        lat = lat[LATS:]
        lon = lon[LONS:]

        print lat.shape
        print lon.shape

        # Variables
        temp = dataset['temperature'][:,:,:,:]
        #salnity = dataset['salinity']
        #u = dataset['u']
        #u = dataset['v']

        local_filename = "{0}_{1}_{2}.nc".format(settings.HYCOM_DF_FN, date, "test")
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)
        destination_file = os.path.join(destination_directory, local_filename)

        f = netcdf.netcdf_file(destination_file, 'w')

        print lat
        print lon
        print time.dtype

        f.createDimension('time', time.shape[0])
        f.createDimension('lev', lev.shape[0])
        f.createDimension('lat', lat.shape[0])
        f.createDimension('lon', lon.shape[0])


        #f.createVariable('temp', 'f8', ('time', 'lev', 'lat', 'lon'))
        #f.createVariable('salnity', 'float', ('time', 'lev', 'lat', 'lon'))
        #f.createVariable('u', 'float', ('time', 'lev', 'lat', 'lon'))
        #f.createVariable('v', 'float', ('time', 'lev', 'lat', 'lon'))

        f.close()

        return

    @staticmethod
    @shared_task(name='pl_download.rtofs_download')
    def rtofs_download(count=None):
        """ Downloads a netCDF of the current days hycom forecast

        Base Link (settings.HYCOM_URL): http://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/rtofs.

        Example Access Link: nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/rtofs.20170821/rtofs_glo_3dz_f030_6hrly_hvr_reg2.nc

        :return: id of the downloaded datafile
        """

        # Count Can Limit the amount of downloads you want to download

        if count is not None:
            cnt = 0

        verbose = 1

        date = str(dt.date.today()).replace("-", "", 3) # Todays Date used for access
        index_url = settings.HYCOM_URL+date+"/"

        # Calculate what files we need to use for downloading
        HOURS = 96

        page = requests.get(index_url)
        tree = html.fromstring(page.content)

        forecasts = tree.xpath('/html/body/pre/*/text()')

        ids = []

        for forecast in forecasts:
            if "6hrly" in forecast and "US_west" in forecast:

                filename = forecast
                if verbose > 0:
                    print filename

                url = index_url + filename
                tag = url.split('_')[3] # If we don't grab the tag we'll have a bunch of files with the same
                                        # filename as they all have the same date!

                hour = int(tag[1:]) # Hour of the forecast pulled from the html url

                if 'n' in tag:  # Don't grab nowcasts
                    continue

                if int(tag[1:]) < HOURS: # Download files that are not used for extension
                    continue

                local_filename = "{0}_{1}_{2}.nc".format(settings.HYCOM_DF_FN, date, tag)
                destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)
                destination_file = os.path.join(destination_directory, local_filename)

                urllib.urlretrieve(url=url, filename=destination_file)

                data_file = netcdf.netcdf_file(destination_file)
                days = data_file.variables['MT'].data
                epoch = datetime.strptime(data_file.variables['MT'].units, "days since %Y-%m-%d %H:%M:%S")
                model_date = epoch + timedelta(days=days[0]) # Values enced as days since..

                if verbose > 0:
                    print epoch
                    print "Days: ", days
                    print "Model Date: ", model_date

                datafile = DataFile(
                    type='RTOFS',
                    download_datetime=timezone.now(),
                    generated_datetime=timezone.now(),
                    model_date=model_date,
                    file=local_filename,
                )
                datafile.save()
                ids.append(datafile.id)

                if count is not None:
                    if cnt > count:
                        return ids
                    else:
                        cnt += 1

            else:
                continue

        return ids

    @staticmethod
    def test_file(file):
        # Test to see if the file is valid or not
        try:
            data_file = netcdf.netcdf_file(
                os.path.join(
                    settings.MEDIA_ROOT,
                    settings.NETCDF_STORAGE_DIR,
                    file
                )
            )
            return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return False

    @staticmethod
    def get_last_forecast_for_roms(df_type=None):
        from pl_plot.plotter import Plotter

        latest_roms = DataFile.objects.filter(type='NCDF').order_by('id')[0]
        plotter = Plotter(latest_roms.file.name)
        return plotter.get_last_model_time()

    @staticmethod
    def get_last_forecast_for_osu_ww3(df_type=None):
        from pl_plot.plotter import WaveWatchPlotter

        latest_roms = DataFile.objects.filter(type='WAVE').order_by('id')[0]
        plotter = WaveWatchPlotter(latest_roms.file.name)
        return plotter.get_last_model_time()


    @staticmethod
    @shared_task(name='pl_download.navy_hycom_download')
    def navy_hycom_download():

        # SST - Sea Surface Temp & Salnity
        # UV - Sea Surface Currents
        # SSH - Sea Surface Height

        BASE_URL = 'http://tds.hycom.org/thredds/catalog/GLBv0.08/expt_92.9/forecasts/catalog.html'
        XML_URL = 'http://tds.hycom.org/thredds/catalog/GLBv0.08/expt_92.9/forecasts/catalog.xml'

        verbose = 0

        access_date, date_string  = determine_latest_forecast(XML_URL)

        if verbose > 0:
            print "Access Date:", access_date
            print "Access Date String:", date_string

        catalog = etree.parse(XML_URL)
        today = datetime.now().today()

        export = '929'

        file_ids = []

        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)

        # Determine when we should download
        last_roms_forecast_date = DataFileManager.get_last_forecast_for_roms()

        # Download
        for element in catalog.iter():
            file = element.get('name')

            if not file:
                continue

            elif file.startswith('hycom_glbv_'+export+'_'+date_string): # Grab only dates that are the latest
                ''' Grab infromation of the datafile '''
                if verbose > 0:
                    print "File split", file.split('_')

                field = determine_type(file.split('_')[5])
                access_date, date, tag = create_nomads_time_series_from_file_with_tag(file)

                url = create_subset_access_url(file, field, access_date)

                date_tag = date.strftime('%Y-%m-%d')
                datafile = []

                if len(url) == 2: # TEMP and SSC forecasts create two access links for top or bottom
                    ''' Top '''
                    local_filename = []
                    local_filename.append("{0}_{1}_{2}_{3}_top.nc".format(settings.NAVY_HYCOM_DF_FN, date_tag, tag, field))

                    datafile.append(DataFile(
                        type='HYCOM',
                        download_datetime=timezone.now(),
                        generated_datetime=timezone.now(),
                        model_date=date,
                        file=local_filename[0],
                    ))

                    ''' Bottom '''
                    local_filename.append("{0}_{1}_{2}_{3}_bot.nc".format(settings.NAVY_HYCOM_DF_FN, date_tag, tag, field))

                    datafile.append(DataFile(
                        type='HYCOM',
                        download_datetime=timezone.now(),
                        generated_datetime=timezone.now(),
                        model_date=date,
                        file=local_filename[1],
                    ))
                else:
                    ''' SSH '''
                    local_filename = "{0}_{1}_{2}_{3}.nc".format(settings.NAVY_HYCOM_DF_FN, date_tag, tag, field)
                    datafile.append(DataFile(
                        type='HYCOM',
                        download_datetime=timezone.now(),
                        generated_datetime=timezone.now(),
                        model_date=date,
                        file=local_filename,
                    ))

                verbose = 0

                if verbose > 0:
                    print last_roms_forecast_date
                    print type(last_roms_forecast_date)

                date = timezone.make_aware(date, timezone.utc)

                if date > last_roms_forecast_date:
                    if len(local_filename) == 2: # Top and Bottom files
                        for i in range(len(local_filename)):
                            urllib.urlretrieve(url=url[i],
                                               filename=os.path.join(destination_directory, local_filename[i]))
                            if not DataFileManager.test_file(local_filename[i]):
                                print "ERROR DOWNLOADING FILE,", local_filename[i]
                    else: # SST
                        urllib.urlretrieve(url=url,
                                           filename=os.path.join(destination_directory, local_filename))
                        if not DataFileManager.test_file(local_filename):
                            print "ERROR DOWNLOADING FILE,", local_filename

                else:
                    # Don't download - we already have a forecast for this time
                    print "NO DOWNLOAD!", date
                    continue

                for d in datafile:
                    d.save()
                    file_ids.append(d.id)


        print "NAVY HYCOM - COMPLETE"
        return file_ids

    @staticmethod
    @shared_task(name='pl_download.ww3_download')
    def ww3_download():
        """ Downloads a NetCDF of the current days ww3

         Access Link through:
         http://thredds.ucar.edu/thredds/ncss/grib/NCEP/WW3/Regional_US_West_Coast/Best/dataset.html

        :return: id of downloaded datafile
        """
        # TODO: Check to see if the download file already exists?
        begin_date, end_date = create_nomads_time_series_from_today(start=4, end=20)
        begin_date = DataFileManager.get_last_forecast_for_osu_ww3()

        begin = datetime.strftime(begin_date, '%Y-%m-%d')
        begin = str(begin) + 'T00%3A00%3A00Z'
        end = str(end_date) + 'T00%3A00%3A00Z'

        print begin
        print end

        url = "http://thredds.ucar.edu/thredds/ncss/grib/NCEP/WW3/Regional_US_West_Coast/Best?" \
              "var=Direction_of_wind_waves_surface&var=" \
              "Mean_period_of_wind_waves_surface&var=" \
              "Primary_wave_direction_surface&var=" \
              "Primary_wave_mean_period_surface&var=" \
              "Significant_height_of_combined_wind_waves_and_swell_surface&var=Significant_height_of_wind_waves_surface" \
              "&north=50&west=-150&east=-110&south=25&horizStride=1" \
              "&time_start="+begin+"&time_end="+end+"" \
              "&timeStride=1&vertCoord=&addLatLon=true&accept=netcdf" \

        local_filename = "{0}_{1}.nc".format(settings.NCEP_WW3_DF_FN, begin)
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.WAVE_WATCH_DIR)

        urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))

        datafile = DataFile(
            type='NCEP',
            download_datetime=timezone.now(),
            generated_datetime=timezone.now(),
            model_date=begin_date,
            file=local_filename,
        )
        datafile.save()

        return datafile.id

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

        print ftp_dtm
        print ftp_dtm[4]
        print initial_datetime

        naive_datetime = parser.parse(initial_datetime)
        modified_datetime = timezone.make_aware(naive_datetime, timezone.utc)

        print "Dwnloading OSU WW3 File"

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

        if not matches_old_file:
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

    @staticmethod
    @shared_task(name='pl_download.download_tcline')
    def download_tcline():
        startswith = "Tcline_d_davg_"
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)
        print destination_directory
        BASE_URL = "http://wilson.coas.oregonstate.edu:8080/thredds/fileServer/NANOOS/OCOS_TCline/"
        XML_URL = 'http://wilson.coas.oregonstate.edu:8080/thredds/catalog/NANOOS/OCOS_TCline/catalog.xml'

        catalog = etree.parse(XML_URL)

        file_ids = []

        for element in catalog.iter():
            file = element.get('name')

            if not file:
                continue
            elif file.startswith(startswith):
                datestring = file.split('_')[-1]
                file_date = datetime.strptime(datestring, "%d-%b-%Y.nc").date()

                url = BASE_URL + file
                local_filename = "{0}_{1}.nc".format(settings.OSU_TCLINE_DF_FN, file_date)

                try:
                    print "Downloading OSU T-cline File {0}".format(url,)
                    urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))
                    datafile = DataFile(
                        type='T-CLINE',
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

                print "Downloaded t-cline File from Wilson{0}".format(local_filename)

        return file_ids

    @classmethod
    def is_new_file_to_download(cls, model):
        """ DEPRECATED: Determine if there is a new file to download. Used by fetch_new_file and uses
        the old download location """
        three_days_ago = timezone.now().date()-timedelta(days=3)
        today = timezone.now().date()

        if model == "tcline":
            recent_netcdf_files = DataFile.objects.filter(type="T-CLINE", model_date__range=[three_days_ago, today])
            model_start = 'Tcline'
        else:
            recent_netcdf_files = DataFile.objects.filter(type="NCDF", model_date__range=[three_days_ago, today])
            model_start = 'ocean_his'


        if not recent_netcdf_files:
            return True

        local_file_modified_datetime = recent_netcdf_files.latest('generated_datetime').generated_datetime

        tree = get_unidata_xml_tree()
        tags = tree.iter(XML_NAMESPACE + 'dataset')

        for elem in tags:
            if not elem.get('name').startswith(model_start):
                continue
            server_file_modified_datetime = extract_modified_datetime_from_xml(elem)
            if server_file_modified_datetime.date() > local_file_modified_datetime.date():
                return True

        return False

    @classmethod
    def get_next_few_days_files_from_db(cls, days=15):
        """ SOON TO BE DEBRICATED SEE get_next_few_datafiles_of_a_type

        This function gets the file ID's from the database that do not have plots.

        :return: A list of datafiles that haven't had plots generated for them yet
        """
        next_few_days_of_files = DataFile.objects.filter(
            model_date__gte=(timezone.now()-timedelta(days=PAST_DAYS_OF_FILES_TO_DISPLAY+1)).date(),
            model_date__lte=(timezone.now()+timedelta(days=days)).date()
        )

        for i in next_few_days_of_files:
            print i.id

        # Select the most recent within each model date and type (ie wave or SST)
        and_the_newest_for_each_model_date = next_few_days_of_files.values('model_date', 'type').annotate(newest_generation_time=Max('generated_datetime'))

        # if we expected a lot of new files, this would be bad (we're making a Q object for each file we want, basically)
        q_objects = []
        for filedata in and_the_newest_for_each_model_date:
            new_q = Q(type=filedata.get('type'), model_date=filedata.get('model_date'),
                      generated_datetime=filedata.get('newest_generation_time'))
            q_objects.append(new_q)

        print q_objects
        for i in q_objects:
            print i

        # assumes you're not re-downloading the same file for the same model and generation dates.
        actual_datafile_objects = DataFile.objects.filter(reduce(OR, q_objects))

        for i in actual_datafile_objects:
            print i.id

        return actual_datafile_objects

    @classmethod
    def get_next_few_datafiles_of_a_type(cls, type, days=15, past_days=PAST_DAYS_OF_FILES_TO_DISPLAY+1):
        datafiles = DataFile.objects.filter(
            model_date__gte=(timezone.now()-timedelta(days=past_days)).date(),
            model_date__lte=(timezone.now()+timedelta(days=days)).date(),
            type=type
        )

        return [datafile.id for datafile in datafiles]

    @classmethod
    def get_next_few_datafiles_of_hycom_file_ids(cls):
        datafiles = DataFile.objects.filter(
            model_date__gte=(timezone.now()-timedelta(days=0)).date(),
            model_date__lte=(timezone.now()+timedelta(hours=192)).date()
        )

        return [datafile.id for datafile in datafiles]

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


def create_url_temp_sal(file, date):
    # &vertCoord = 0 <- Depth

    top = \
        'http://ncss.hycom.org/thredds/ncss/GLBv0.08/expt_92.9/forecasts/' \
        ''+file+'?' \
        '&var=salinity&var=water_temp' \
        '&north=50&west=228&east=237&south=35' \
        '&horizStride=1' \
        '&time='+date+'' \
        '&vertCoord=0' \
        '&addLatLon=true&accept=netcdf'

    bot = \
        'http://ncss.hycom.org/thredds/ncss/GLBv0.08/expt_92.9/forecasts/' \
        ''+file+'?' \
        'var=salinity_bottom&var=water_temp_bottom' \
        '&north=50&west=228&east=237&south=35' \
        '&horizStride=1' \
        '&time='+date+'' \
        '&addLatLon=true&accept=netcdf'

    return top, bot

def create_url_ssc(file, date):
    # Vert Cord = Depth
    top = \
        'http://ncss.hycom.org/thredds/ncss/GLBv0.08/expt_92.9/forecasts/' \
        ''+file+'?' \
        '&var=water_u&var=water_v' \
        '&north=50&west=228&east=237&south=35' \
        '&horizStride=1' \
        '&time='+date+'' \
        '&vertCoord=0' \
        '&addLatLon=true&accept=netcdf'

    bot = \
        'http://ncss.hycom.org/thredds/ncss/GLBv0.08/expt_92.9/forecasts/' \
        ''+file+'?' \
        'var=water_u_bottom&var=water_v_bottom' \
        '&north=50&west=228&east=237&south=35' \
        '&horizStride=1' \
        '&time='+date+'' \
        '&addLatLon=true&accept=netcdf'

    return top, bot

def create_url_ssh(file, date):
    return \
        'http://ncss.hycom.org/thredds/ncss/GLBv0.08/expt_92.9/forecasts/' \
        ''+file+'?' \
        'var=surf_el' \
        '&north=50&west=228&east=237&south=35' \
        '&horizStride=1' \
        '&time='+date+ \
        '&addLatLon=true' \
        '&accept=netcdf'


def determine_type(fileEnding):
    if fileEnding == 'ssh.nc':
        type = 'ssh'
    if fileEnding == 'ts3z.nc':
        type = 'temp'
    if fileEnding == 'uv3z.nc':
        type = 'cur'

    return type

def determine_latest_forecast(XML_URL):
    catalog = etree.parse(XML_URL)

    i = 0
    for element in catalog.iter():
        file = element.get('name')
        if not file:
            continue
        elif file.startswith('hycom_glbv'):
            date = datetime.strptime(file.split('_')[3][0:8], "%Y%m%d")

            if i == 0:
                date_s = date
            else:
                if date > date_s:
                    date_s = date

            i += 1

    access_date = date_s
    date_string = date_s.strftime("%Y%m%d")

    return access_date, date_string

def create_subset_access_url(file, field, date):
    """

    :param field: ssh, temp, cur
    :param date: DateTime
    :param file: outfile
    :return: subset access url for given type
    """
    verbose = 0

    if verbose > 0:
        print "Type:", field, type(field)
        print "Date:", date, type(date)
        print "File:", file, type(file)

    if field == 'temp':
        return create_url_temp_sal(file, date)
    if field == 'cur':
        return create_url_ssc(file, date)
    if field == 'ssh':
        return create_url_ssh(file, date)


def create_nomads_time_series_from_file_with_tag(file):
    """ create a nomads date & time access from a file that looks like:
    hycom_glbv_929_2018010812_t000 to 2018-01-08T12%3A00%3A00Z

    where `txxx` = the number of hours from the date in the file

    :param file: hycom_glbv_929_yyyymmdd12_txxx
    :return: string in format - YYYY-MM-DDTHH%3AMM%3ASSZ and datetime
    """
    indate = file.split('_')[3][0:8]
    hours = int(file.split('_')[4][1:])

    date = datetime.strptime(indate, '%Y%m%d')
    date = date + timedelta(hours=12)
    date = date + timedelta(hours=hours)

    return date.strftime('%Y-%m-%dT%H%%3A%M%%3A%SZ'), \
           date, \
           file.split('_')[4]

def create_nomads_time_series_from_today(start=0, end=4):
    """ Creates a nomads time series in the format of: T00%3A00%3A00Z with today's date as the start
    and to todays date + range.

    :param start: number of days into the future to start
    :param end: number of days into the future to end
    :return: begin_date, end_date
    """
    begin_date = datetime.now().date() + timedelta( days = start )
    end_date = datetime.now().date() + timedelta( days = end)

    return begin_date, end_date

def create_nomads_time_series_from_datetime(datetime):
    pass

class DataFile(models.Model):
    """ The Model or "Object" that is used by our Web Management Server (Django) to describe our
    downloaded files. Objects are created and then they are stored in a table inside our database
    by calling datafile.save().

    If this is edited you must migrate the appropriate servers.
    """
    DATA_FILE_TYPES = (
        ('NCDF', "NetCDF"),
        ('WAVE', "WaveNETCDF"),
        ('WIND', "WindNETCDF"),
        ('T-CLINE', "Thermocline"),
        ('NCEP', "NCEP_WW3"),
        ('HYCOM', "HYCOM_ROMS"),
        ('RTOFS', 'NOAA_RTOFS')
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
