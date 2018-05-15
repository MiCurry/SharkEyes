import traceback

import os
import urllib
import urllib2
from ftplib import FTP

import sys

import numpy
from netCDF4 import Dataset, num2date, date2num
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
        # Because we are extending the two day roms forecast, just grab the last available forecast.
        # This will also allow the NAVY forecast to 'takeover' the OSU ROMS forecast if the OSU ROMS forecast
        # isn't available.
        from pl_plot.plotter import Plotter

        #Todo: Check to see if there is at least one rom file
        #Todo: Intorduce error checking here

        latest_roms = DataFile.objects.filter(type='NCDF').order_by('model_date').reverse()[0]
        plotter = Plotter(latest_roms.file.name)
        return plotter.get_last_model_time()

    @staticmethod
    def get_last_forecast_for_osu_ww3(df_type=None):
        # Not used since OSU WW3 is no longer available
        from pl_plot.plotter import WaveWatchPlotter

        #Todo: Check to see if there is at least one OSU WW3 file
        #Todo: Introduce error checking here

        latest_roms = DataFile.objects.filter(type='WAVE').order_by('model_date').reverse()[0]
        plotter = WaveWatchPlotter(latest_roms.file.name)
        return plotter.get_last_model_time()


    @staticmethod
    @shared_task(name='pl_download.navy_hycom_download')
    def navy_hycom_download(level='top'):

        # TODO: Interpolate

        top = 0.0
        bot = 2500.0
        vert_coord= str(top)

        time_start_dt = DataFileManager.get_last_forecast_for_roms()
        time_start = create_nomads_string_from_datetime(DataFileManager.get_last_forecast_for_roms())
        time_end = create_nomads_string_from_datetime(DataFileManager.get_last_forecast_for_roms() + timedelta(days=30)) # Essentially set to infinity

        URL = 'http://ncss.hycom.org/thredds/ncss/GLBv0.08/expt_93.0/data/forecasts/Forecast_Mode_Run_(FMRC)_best.ncd?' \
              'var=salinity&var=water_temp&var=water_u&var=water_v' \
              '&north=50&west=-150&east=-110&south=25&disableProjSubset=on' \
              '&horizStride=1' \
              '&time_start='+time_start+'' \
              '&time_end='+time_end+'' \
              '&timeStride=1' \
              '&vertCoord='+vert_coord+'' \
              '&addLatLon=true&accept=netcdf'


        print "Downloading HYCOM df...",
        destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)
        local_filename = "{0}_{1}.nc".format(settings.NAVY_HYCOM_DF_FN, create_string_from_dt_for_file(time_start_dt))
        urllib.urlretrieve(url=URL, filename=os.path.join(destination_directory, local_filename))
        print "file downloaded",

        from pl_plot.plotter import HycomPlotter

        plotter = HycomPlotter(local_filename)

        time='time'; salt='salinity'; temp='water_temp'
        cur_u='water_u'; cur_v='water_v'

        depth = plotter.data_file.variables['depth']
        times = plotter.data_file.variables[time]
        salinity = plotter.data_file.variables[salt][:, 0, :, :]
        temps = plotter.data_file.variables[temp][:, 0, :, :]
        curs_u = plotter.data_file.variables[cur_u][:, 0, :, :]
        curs_v = plotter.data_file.variables[cur_v][:, 0, :, :]

        # Squeeze out the depth of each variable...
        salinity = numpy.squeeze(salinity)
        temps = numpy.squeeze(temps)
        curs_u = numpy.squeeze(curs_u)
        curs_v = numpy.squeeze(curs_v)

        lons = plotter.data_file.variables['lon']
        lats = plotter.data_file.variables['lat']

        basetime = datetime.strptime(plotter.data_file.variables[time].units, 'hours since %Y-%m-%d 12:00:00.000 UTC')

        ts1 = times; ts1 = map(float, ts1)

        dates = [(basetime + n * timedelta(hours=4)) for n in range(times.shape[0])]

        ts2 = date2num(dates[:], units=times.units, calendar=times.calendar)

        for i in range(len(ts2)):
            ts2[i] += times[0] + 1 # Now bump up the times to be equal with what we desire


        salinity_int = numpy.empty([ts2.shape[0], lats.shape[0], lons.shape[0]]) # Array to be filled
        temps_int = numpy.empty([ts2.shape[0], lats.shape[0], lons.shape[0]]) # Array to be filled
        curs_u_int = numpy.empty([ts2.shape[0], lats.shape[0], lons.shape[0]]) # Array to be filled
        curs_v_int = numpy.empty([ts2.shape[0], lats.shape[0], lons.shape[0]]) # Array to be filled

        print "...Interpolating...",

        for i in range(lats.shape[0]):
            for j in range(lons.shape[0]):
                """ For each lat and lon across t, time, interpolate from ts1, orginal timestamp,
                the the new timestamp, ts2.
                """
                salinity_int[:, i, j] = numpy.interp(ts2, ts1, salinity[:, i, j]) # Heights interpolated
                temps_int[:, i, j] = numpy.interp(ts2, ts1, temps[:, i, j])
                curs_u_int[:, i, j] = numpy.interp(ts2, ts1, curs_u[:, i, j])
                curs_v_int[:, i, j] = numpy.interp(ts2, ts1, curs_v[:, i, j])

        plotter.close_file() # Close readonly Datafile
        print "saving interpolated values..."

        plotter.write_file(local_filename) # Open datafile for writing

        # Write values
        plotter.data_file.variables[time][:] = ts2
        plotter.data_file.variables[salt][:, :, :] = salinity_int
        plotter.data_file.variables[temp][:, :, :] = temps_int
        plotter.data_file.variables[cur_u][:, :, :] = curs_u_int
        plotter.data_file.variables[cur_v][:, :, :] = curs_v_int

        plotter.close_file() # Close rw datafile

        datafile = DataFile(
            type='HYCOM',
            download_datetime=timezone.now(),
            generated_datetime=timezone.now(),
            model_date=time_start_dt,
            file=local_filename,
        )
        datafile.save() # S-S-Save that datafile entry!
        print "finished! Datafile saved!"

        return datafile.id

    @staticmethod
    @shared_task(name='pl_download.ww3_download')
    def ww3_download():
        """ Downloads a NetCDF of the current days ww3

         Access Link through:
         http://thredds.ucar.edu/thredds/ncss/grib/NCEP/WW3/Regional_US_West_Coast/Best/dataset.html

        :return: id of downloaded datafile
        """

        print "Downlaoding NCEP WW3 from UNIDATA.....",

        # TODO: Check to see if the download file already exists?
        begin_date, end_date = create_nomads_time_series_from_today(start=0, end=20)
        #begin_date = DataFileManager.get_last_forecast_for_osu_ww3() # No longer extending WW3. OSU WW3 is N/A

        begin = datetime.strftime(begin_date, '%Y-%m-%d')
        begin = str(begin) + 'T00%3A00%3A00Z'
        end = str(end_date) + 'T00%3A00%3A00Z'

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

        # Retrieve datafile from the server
        urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename))

        from pl_plot.plotter import NcepWW3Plotter

        """ UCAR NCEP WW3 comes with times: 00:00, 04:00 etc every four hours. Seacast
        uses 01:00, 05:00, so we need to interpolate to these time zones.
        
        To do this we are going to do the interpolation when we download the file, and then
        we will save the NetCDF file with these interpolated values and new time stamp!"""

        plotter = NcepWW3Plotter(local_filename)

        height = "Significant_height_of_combined_wind_waves_and_swell_surface"
        direction = "Primary_wave_direction_surface"
        period = "Primary_wave_mean_period_surface"

        # Original values
        times = plotter.data_file.variables['time']
        heights = plotter.data_file.variables[height][:, :, :]
        directions = plotter.data_file.variables[direction][:, :, :]
        periods = plotter.data_file.variables[period][:, :, :]

        lons = plotter.data_file.variables['lon']
        lats = plotter.data_file.variables['lat']

        # Create the new 'time' variable, which is a list of hours since
        # df.variables['time'].units, to match the time series we want
        basetime = get_datetime_from_units_since(plotter.data_file.variables['time'].units)
        ts1 = times; ts1 = map(float, ts1) # Orginal times converted from type netcdf variable else we get an error

        dates = [(basetime + n * timedelta(hours=4)) for n in range(times.shape[0])]

        ts2 = date2num(dates[:], units=times.units, calendar=times.calendar)

        for i in range(len(ts2)):
            ts2[i] += times[0] + 1 # Now bump up the times to be equal with what we desire

        """ Good ole interpolation """

        heights_int = numpy.empty([ts2.shape[0], lats.shape[0], lons.shape[0]]) # Array to be filled
        period_int = numpy.empty([ts2.shape[0], lats.shape[0], lons.shape[0]]) # Ditto
        direction_int = numpy.empty([ts2.shape[0], lats.shape[0], lons.shape[0]]) # Ditto

        ts1 = map(float, ts1) # Else we get an error
        ts2 = map(float, ts2) # Else we get an error

        print "interpolating...",

        for i in range(lats.shape[0]):
            for j in range(lons.shape[0]):
                """ For each lat and lon across t, time, interpolate from ts1, orginal timestamp,
                the the new timestamp, ts2.
                """
                heights_int[:, i, j] = numpy.interp(ts2, ts1, heights[:, i, j]) # Heights interpolated
                period_int[:, i, j] = numpy.interp(ts2, ts1, periods[:, i, j])
                direction_int[:, i, j] = numpy.interp(ts2, ts1, directions[:, i, j])

        plotter.close_file() # Close readonly Datafile
        print "saving interpolated values..."

        plotter.write_file(local_filename) # Open datafile for writing

        # Write values
        plotter.data_file.variables['time'][:] = ts2
        plotter.data_file.variables[height][:, :, :] = heights_int
        plotter.data_file.variables[period][:, :, :] = period_int
        plotter.data_file.variables[direction][:, :, :] = direction_int

        plotter.close_file() # Close rw datafile

        datafile = DataFile(
            type='NCEP',
            download_datetime=timezone.now(),
            generated_datetime=timezone.now(),
            model_date=begin_date,
            file=local_filename,
        )
        datafile.save() # S-S-Save that datafile entry!

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
    def get_next_few_datafiles_of_a_type(cls, type, past_days=PAST_DAYS_OF_FILES_TO_DISPLAY+1):
        datafiles = DataFile.objects.filter(
            model_date__gte=(timezone.now()-timedelta(days=past_days)).date(),
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

def create_nomads_string_from_datetime(datetime):
    return datetime.strftime('%Y-%m-%dT%H%%3A%M%%3A%SZ')

def create_string_from_dt_for_file(dt):
    return dt.strftime('%d-%b-%Y')

def get_datetime_from_units_since(units_since):
    """
    This probably wont work with every model, so just check and make sure before use.
    :param unit_since: String "units since ...."
    :return:  datetime object with date in that string
    """
    date = datetime.strptime(units_since, "Hour since %Y-%m-%dT00:00:00Z")
    return date


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
