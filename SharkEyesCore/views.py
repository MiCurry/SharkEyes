from django.shortcuts import render
from pl_plot.models import OverlayManager, OverlayDefinition
from pl_download.models import DataFile
from scipy.io import netcdf
import numpy as np
from django.conf import settings
import os
from datetime import datetime, timedelta
import pytz
import json
import logging
from django.db import connection
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import HttpResponse
from django.template import Library
from django.template.defaultfilters import stringfilter
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from mpl_toolkits.basemap import Basemap
import re

# Django likes to remove whitespace from HTML strings. Use spacify("string with space") to preserve whitespace
register = Library()
@stringfilter
def spacify(value, autoescape=None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x
    return mark_safe(re.sub('\s', '&'+'nbsp;', esc(value)))
spacify.needs_autoescape = True
register.filter(spacify)

# We have a debugging file to easily get pring output from the Seacat servers.
logging.basicConfig(filename='/opt/sharkeyes/src/debugging.txt', level=logging.INFO)

# Helper Functions for right_click_menu
# Converts decimal lat longs into degree minutes and seconds
def dd_to_deg(dd):
    results = []
    degrees = int(dd)
    minutes = int((dd - degrees)*60)
    seconds = np.round((dd - degrees - minutes/60) * 3600, 1)
    results.append(str(degrees))
    results.append(str(abs(minutes)))
    results.append(str(abs(seconds)))
    return results

# Organizes the date into a usable list of values
# ------------------------------------------------------------------
def prep_date(date):
    clean_date = []
    date = date.split(',')
    date = [str(date[x]) for x in range(len(date))]
    if date[2] == ' midnight':
        date[2] = "12 a.m."
    if date[2] == " noon":
        date[2] = "12 p.m."
    hour_anti_post = date[2].split()
    hour = hour_anti_post[0]
    anti_post = hour_anti_post[1]
    month_day = date[0].split()
    month = month_day[0]
    if len(month)> 3:
        month = month[0:3]
    if month == 'Jan':
        month = '01'
    elif month == 'Feb':
        month = '02'
    elif month == 'Mar':
        month = '03'
    elif month == 'Apr':
        month = '04'
    elif month == 'May':
        month = '05'
    elif month == 'Jun':
        month = '06'
    elif month == 'Jul':
        month = '07'
    elif month == 'Aug':
        month = '08'
    elif month == 'Sep':
        month = '09'
    elif month == 'Oct':
        month = '10'
    elif month == 'Nov':
        month = '11'
    elif month == 'Dec':
        month = '12'
    day = month_day[1]
    if len(day) < 2:
        day = "0" + day
    clean_date.append(hour)
    clean_date.append(anti_post)
    clean_date.append(month)
    clean_date.append(day)
    return clean_date

def get_x_y_wind(lat, lon, dataset, model):
    indices = []
    # m = Basemap(rsphere=(6371229.00, 6356752.3142), projection='merc',
    #             llcrnrlat=40.5833284543, urcrnrlat=47.4999927992,
    #                    llcrnrlon=-129, urcrnrlon=-123.7265625)
    # xpt, ypt = m(lon,lat)
    # print "x ", xpt/100
    # print "y ", ypt/100
    print "lat ", lat
    print "lon ", lon
    lat_name = 'lat'
    lon_name = 'lon'
    file_lats = dataset.variables[lat_name][:]
    file_lons = dataset.variables[lon_name][:]
    file_lat = np.abs(file_lats - lat).argmin()
    file_lon = np.abs(file_lons - lon).argmin()
    print "Argmin lat", file_lat
    print "Argmin lon", file_lon
    file_lat = np.unravel_index(file_lat, file_lats.shape)
    file_lon = np.unravel_index(file_lon, file_lons.shape)
    print "Unravel lat", file_lat
    print "Unravel lon", file_lon
    file_lat_y = file_lat[0]
    file_lat_x = file_lat[1]
    print"lat y x", file_lat_y, file_lat_x
    file_lon_y = file_lon[0]
    file_lon_x = file_lon[1]
    print"lon y x", file_lon_y, file_lon_x
    print "lat ", file_lats[file_lat_y][file_lat_x]
    print "lon ", file_lons[file_lon_y][file_lon_x]
    indices.append(file_lat_y)
    indices.append(file_lat_x)
    return indices

# Finds the correct lat and lon indices for the model
# --------------------------------------------------------------------
def get_lat_long_index(lat, lon, dataset, model):
    indices = []
    lat_name = ''
    lon_name = ''
    if model == 'wind':
        #flatSize = 5612
        lat_name = 'lat'
        lon_name = 'lon'
    elif model == 'seas':
        lat_name = 'lat_rho'
        lon_name = 'lon_rho'
    elif model == 'wave':
        lat_name = 'latitude'
        lon_name = 'longitude'
        lon = lon%360 #The wave watch longitude values are saved in degrees east. This converts them to degrees west which is what we get from the front-end
    file_lats = dataset.variables[lat_name][:]
    file_lons = dataset.variables[lon_name][:]
    file_lat = np.abs(file_lats - lat).argmin()
    file_lon = np.abs(file_lons - lon).argmin()
    file_lat = np.unravel_index(np.ravel(file_lat, file_lats.shape), file_lats.shape)
    # file_lon = np.unravel_index(np.ravel(file_lon, file_lons.shape), file_lons.shape)
    file_lat = file_lat[0][0]
    # file_lon = file_lon[1][0]
    # print "lat ", file_lats[file_lat][file_lon]
    # print "lon ", file_lons[file_lat][file_lon]
    indices.append(file_lat)
    indices.append(file_lon)
    return indices

# Calculates the necessary time index for Alex's Model
# --------------------------------------------------------------------
def get_time_index_seas(ncdf_data, day, month, year, hour, meridian):
    if hour == 12 and meridian == "a.m.":
        hour = 0
    if meridian == "p.m." and hour != 12:
        hour = hour + 12
    # Check whether or not daylight savings is active
    dst = 0
    isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
    if isdst_now_in("America/Los_Angeles"):
        dst = -1
    dst_correction = timedelta(hours=dst)
    input_time = datetime(day=day, month=month, year=year, hour=hour, minute=0, second=0, tzinfo=timezone.utc)
    time_zone_correction = timedelta(hours=8)
    input_time = input_time + time_zone_correction + dst_correction
    ocean_time_epoch = datetime(day=1, month=1, year=2005, hour=0, minute=0, second=0, tzinfo=timezone.utc)
    for x in range(0, np.shape(ncdf_data.variables['ocean_time'])[0], 1 ):
        seconds_since_epoch = timedelta(seconds=ncdf_data.variables['ocean_time'][x])
        check_date = ocean_time_epoch + seconds_since_epoch
        if check_date == input_time:
            return x

# Calculates the time index for the wind model
# This function is a bit more complex than the others because
# the wind time indices are not consistent. They swap from every hour to every three hours.
# -----------------------------------------------------------------------
def get_time_index_wind(wind_file, day, month, year, hour, meridian):
    index = 8
    # if hour == 12 and meridian == "a.m.":
    #     hour = 0
    # if hour != 12 and meridian == "p.m.":
    #     hour += 12
    # dst = 0
    # isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
    # if isdst_now_in("America/Los_Angeles"):
    #     dst = 1
    # input_time = datetime(day=day, month=month, year=year, hour=hour, minute=0, second=0, tzinfo=timezone.utc)
    # wind_name = wind_file.file.name
    # wind_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WIND_DIR, wind_name), 'r')
    # indices = np.shape(wind_data.variables['time'])[0]
    # raw_epoch_date = str(wind_file.model_date)
    # epoch_date = raw_epoch_date.split('-')
    # epoch_year = int(epoch_date[0])
    # epoch_month = int(epoch_date[1])
    # epoch_day = int(epoch_date[2])
    # ocean_time_epoch = datetime(day=epoch_day, month=epoch_month, year=epoch_year, hour=7, minute=0, second=0,
    #                             tzinfo=timezone.utc)
    # for x in xrange(0, indices, 1):
    #     modifier = 0
    #     if x == 49 or x == 53 or x == 57 or x == 61:
    #         modifier = 1
    #     elif x == 51 or x == 55 or x == 59 or x == 63:
    #         modifier = -1
    #     hours_since_epoch = timedelta(hours=(wind_data.variables['time'][x] + dst - wind_data.variables['reftime'][0]) + modifier)
    #     current_date = ocean_time_epoch + hours_since_epoch
    #     if current_date == input_time:
    #         index = x
    return index

# Calculates the time index for Tuba's WW3 file
# -----------------------------------------------------------------------------
def get_time_index_wave (wave_data, day, month, year, hour, meridian):
    if hour == 12 and meridian == "a.m.":
        hour = 0
    if hour != 12 and meridian == "p.m.":
        hour += 12
    dst = 0
    isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
    if isdst_now_in("America/Los_Angeles"):
        dst = -1
    dst_correction = timedelta(hours=dst)
    time_zone_correction = timedelta(hours=8)
    input_time = datetime(day=day, month=month, year=year, hour=hour, minute=0, second=0, tzinfo=timezone.utc)
    input_time = input_time + time_zone_correction + dst_correction
    all_day_times = wave_data.variables['time'][:]
    basetime = datetime(1970, 1, 1, 0, 0, 0)  # Jan 1, 1970
    # This is the first forecast: right now it is Noon (UTC) [~5 AM PST] on the day before the file was downloaded
    forecast_zero = basetime + timedelta(all_day_times[0] / 3600.0 / 24.0, 0, 0)
    for x in range(0, 84, 1):
        model_time = timezone.make_aware(forecast_zero + timedelta(hours=x), timezone.utc)
        if input_time == model_time:
            return x

# Returns which model types are being displayed
# ------------------------------------------------------------------------------
def get_models(keys):
    models = {'wave':0, 'seas':0, 'wind':0 }
    for x in keys:
        if x.find('sst') != -1:
            models['seas'] = 1
        elif x.find('currents') != -1:
            models['seas'] = 1
        elif x.find('wave_h') != -1:
            models['wave'] = 1
        elif x.find('wave_d')!= -1:
            models['wave'] = 1
        elif x.find('barb') != -1:
            models['wind'] = 1
        elif x.find('bottom_t') != -1:
            models['seas'] = 1
        elif x.find('bottom_s') != -1:
            models['seas'] = 1
        elif x.find('salt') != -1:
            models['seas'] = 1
        elif x.find('ssh') != -1:
            models['seas'] = 1
    return models

#This is where we associate the Javascript variables (overlays, defs etc) with the Django objects from the database.
def home(request):
    #Models determines which models are displayed on the website. They will appear in the order provided by models[]. Change this order to change the order of the buttons and which buttons appear.
    # 1 = SST,
    # 2 = Salinity,
    # 3 = Currents,
    # 4 = Wave Height,
    # 5 = Winds,
    # 6 = Wave Direction/Period,
    # 7 = Bottom Temperature,
    # 8 = Bottom Salinity,
    # 9 = Sea Surface Height
    models = [1,3,4,6,5,8,2,7,9]
    fields = []
    for value in models:
        fields.append(OverlayDefinition.objects.get(pk=value))
    overlays_view_data = OverlayManager.get_next_few_days_of_tiled_overlays(models)
    datetimes = overlays_view_data.values_list('applies_at_datetime', flat=True).distinct().order_by('applies_at_datetime')
    context = {'overlays': overlays_view_data, 'defs': fields, 'times':datetimes }
    return render(request, 'index.html', context)

def oops(request):
    return render(request, 'oops.html')

def about(request):
    return render(request, 'about.html')

# This is the function that runs the backend of the data at the cursor functionality
# ---------------------------------------------------------------------------------------
@csrf_exempt
def right_click_menu(request):
    #Get the latitude and longitude values from the front-end request and round them to 3 decimal places
    lat = json.loads(request.body)["lat"]
    lon = json.loads(request.body)["long"]

    #Check the lat longs to make sure they are within range of the model
    datums = HttpResponse()
    wave_lat_lon_check = 0
    if lat > 47.5 or lat < 40.6 or lon < -129 or lon > -123.8:
        datums.write('<p style="font-size:20px">' + '<b>' 'Lat long selected is outside of the model range' '</b>')
        return datums
    if lat > 47.5 or lat < 41.45 or lon < -127 or lon > -123.8: #Tuba's model covers a smaller area. This is a separate check for WW3 fields
        wave_lat_lon_check = 1

    #Get the currently displayed date from the front-end request and process it for usability
    query_date = json.loads(request.body)["display_date"]
    clean_date = prep_date(query_date)
    hour = clean_date[0]
    meridian = clean_date[1]
    month = clean_date[2]
    day = clean_date[3]
    current_date = datetime.now()
    current_year = str(current_date.year)
    # logging.info('Hour= %s Day= %s Month= %s Meridian= %s',hour, day, month, meridian )
    # logging.info('Current Day= %s Current Year= %s',current_day, current_year )

    #Find out which models are being viewed
    keys = json.loads(request.body)["keys"]
    models = get_models(keys) #The key names are messy. This function parses them and determines what is being viewed

    # Winds currently do not work, so they are disabled. To disable the other models set seas to 0 and wave to 0
    models['wind'] = 0

    #Access the relevant netcdf files. Wave is Tuba's WW3 file, seas is Alex's model, wind is the wind model
    #Access Tuba's wave watch model
    if models['wave'] == 1 and wave_lat_lon_check == 0:
    #Wave Watch 3 file access
        wave_file = DataFile.objects.filter(type='WAVE').latest('model_date')
        wave_name = wave_file.file.name
        wave_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT,settings.WAVE_WATCH_DIR,wave_name), 'r')

        #Get Wave Watch 3 lat lon indices
        wave_index = get_lat_long_index(lat, lon, wave_data, 'wave')
        wave_lat = wave_index[0]
        wave_lon = wave_index[1]

        #Get the wave watch 3 time index
        wave_time_index = get_time_index_wave(wave_data, int(day), int(month), int(current_year), int(hour), meridian)

        #Get the wave watch 3 wave height value and period
        wave_height = wave_data.variables['HTSGW_surface'][wave_time_index, wave_lat, wave_lon]
        wave_period = wave_data.variables['PERPW_surface'][wave_time_index, wave_lat, wave_lon]
        wave_height = np.round(wave_height * 3.28, 1) #Convert from meters to feet and round to 3 decimal places.
        wave_period = np.round(wave_period, 1)
        if np.isnan(wave_height):
            wave_height = "unavailable"

    # Access Alex's model(sst, currents, ssh, salinity, etc...)
    if models['seas'] == 1:
        # Short months are months with 30 days
        short_months = [4,6,9,11]
        day_check = int(day)
        month_check = int(month)
        # Alex's model is spread out across four files. It also uses GMT which is 7 hours ahead. We need to check for month a day changes
        if meridian == "p.m." and int(hour) != 12 and int(hour) > 5:
            if day_check == 31:
                day_check = 1
                month_check = month_check +1
            elif day_check == 30 and month_check in short_months:
                day_check = 1
                month_check = month_check +1
            elif day_check == 28 and month_check == 2: # This does not account for the next leap year in 2020
                day_check = 1
                month_check = month_check +1
            else:
                day_check = day_check + 1
        if day_check < 10:
            day_check = '0'+ str(day_check)
        seas_file_date = "OSU_ROMS_" + current_year + "-" + str(month_check) + "-" + str(day_check) #This is used to create a string for use in the DB lookup
        seas_file = DataFile.objects.filter(type='NCDF').filter(file__startswith=str(seas_file_date))
        seas_name = seas_file[0].file.name
        seas_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR, seas_name), 'r')
        # logging.info('File Name to Lookup %s', seas_file_date )
        # logging.info('Found File %s', str(seas_name) )

        #Get Alex's model lat lon indices
        seas_index = get_lat_long_index(lat, lon, seas_data, 'seas')
        seas_lat = seas_index[0]
        seas_lon = seas_index[1]

        #Get the time index for Alex's model
        seas_time_index = get_time_index_seas(seas_data, int(day), int(month), int(current_year), int(hour), meridian)

        #Get the values from Alex's model
        ssh = seas_data.variables['zeta'][seas_time_index, seas_lat , seas_lon ]
        zeta = seas_data.variables['zeta'][:].copy()
        no_columbia_slice = zeta[seas_time_index, :, :]
        no_columbia_slice = no_columbia_slice[75:354, :]
        no_columbia_slice[:, 196:309] = np.nan
        no_columbia_slice = np.reshape(no_columbia_slice, 86490)
        for x in range(len(no_columbia_slice)):
            if no_columbia_slice[x] > 10:
                no_columbia_slice[x] = np.nan
        mean_val = np.nanmean(no_columbia_slice)
        ssh = np.round(((ssh - mean_val)  * 3.28 ), 1) - 1 #convert from meters to feet
        surface_temp = seas_data.variables['temp'][seas_time_index, 39, seas_lat, seas_lon]
        surface_temp = np.round(surface_temp * 1.8 + 32, 1) #convert from celsius to fahrenheit
        bottom_temp = seas_data.variables['temp'][seas_time_index, 0, seas_lat, seas_lon]
        bottom_temp = np.round(bottom_temp * 1.8 + 32, 1) #convert from celsius to fahrenheit
        surface_salt = seas_data.variables['salt'][seas_time_index, 39, seas_lat, seas_lon]
        surface_salt = np.round(surface_salt, 1)
        bottom_salt = seas_data.variables['salt'][seas_time_index, 0, seas_lat, seas_lon]
        bottom_salt = np.round(bottom_salt, 1)
        seas_u = seas_data.variables['u'][seas_time_index, 39, seas_lat, seas_lon]
        seas_v = seas_data.variables['v'][seas_time_index, 39, seas_lat, seas_lon]
        current_speed = np.round(np.sqrt(seas_u ** 2 + seas_v ** 2) * 1.944, 1)#convert from m/s to knots

    if models['wind'] == 1:
        #Wind file access
        wind_file = DataFile.objects.filter(type='WIND').latest('model_date')
        wind_name = wind_file.file.name
        wind_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT,settings.WIND_DIR,wind_name), 'r')

        #Get wind file lat lon indices
        wind_index = get_x_y_wind(lat, lon, wind_data, 'wind')
        print "wind index ", wind_index
        x = wind_index[1]
        y = wind_index[0]
        print "x ", x
        print "y ", y

        #Get the time index for the wind model
        wind_time_index = get_time_index_wind(wind_file, int(day), int(month), int(current_year), int(hour), meridian)  # Gets the wind time index
        print "wind time index ", wind_time_index

        #Get the wind model values
        wind_u = wind_data.variables['u-component_of_wind_height_above_ground'][wind_time_index,0,y,x]
        wind_v = wind_data.variables['v-component_of_wind_height_above_ground'][wind_time_index,0,y,x]
        print "wind u ", wind_u
        print "wind v ", wind_v
        wind_speed = np.round(np.sqrt(wind_u**2 + wind_v**2) * 1.944, 1)#converts from m/s to knots and rounds to 3 decimals
        print "wind speed ", wind_speed

    #Build the html strings to send back to the front-end
    d = u"\u00b0" #unicode degree symbol
    # We want to display the lat longs in degrees minutes seconds. This converts them to that. Currently we are doing lat long display on the front-end
    # degree_lat = dd_to_deg(np.round(lat,5))
    # degree_lon = dd_to_deg(np.round(lon,5))
    # display_lat = degree_lat[0] + d + degree_lat[1] + '\'' + degree_lat[2]
    # display_lon = degree_lon[0] + d + degree_lon[1] + '\'' + degree_lon[2]

    if models['seas'] == 0 and models['wave'] == 0 and models['wind'] == 0:
            datums.write('<p style="font-size:20px">' + '<b>' 'Select a field to view lat long specific information' '</b>')
            return datums
    #datums.write('<p style="font-size:20px">' + '<b>' + " Lat " + '</b>' + display_lat + '<br>')
    #datums.write('<p style="font-size:20px">' + '<b>' + " Long " + '</b>' + display_lon + '<br>')
    if models['seas'] == 1:
        datums.write('<p class="sst">' + '<b>' + spacify("SST:                   ") + '</b>' + str(surface_temp) + ' ' + d + 'F' + '<br>')
        datums.write('<p class="currents">' + '<b>' + spacify("SS Currents:     ") + '</b>' + str(current_speed) + ' Kts' + '<br>')
    if models['wave'] == 1 and wave_lat_lon_check == 0:
        datums.write('<p class="wheight">' + '<b>' + spacify("Wave Height:    ") + '</b>' + str(wave_height) + ' Ft' + '<br>')
    if models['wave'] == 1 and wave_lat_lon_check == 0:
        datums.write('<p class="wdir">' + '<b>' + spacify("Wave Period:    ") + '</b>' + str(wave_period) + ' Sec' + '<br>')
    if models['wave'] ==1 and wave_lat_lon_check == 1:
        datums.write('<p class="wheight">' + '<b>' + spacify("Wave Height:  ") + '</b>' + 'Outside Model'  + '<br>')
        datums.write('<p class="wdir">' + '<b>' + spacify("Wave Period:  ") + '</b>' + 'Outside Model' + '<br>')
    if models['wind'] == 1:
        datums.write('<p style="font-size:18px">' + '<b>' + "Winds: " + '</b>' + str(wind_speed) + ' Kts' + '<br>')
    if models['seas'] == 1:
        datums.write('<p class="btemp">' + '<b>' + spacify("Bottom Temp:  ") + '</b>' + str(bottom_temp) + ' ' + d + 'F' + '<br>')
        datums.write('<p class="ssalt">' + '<b>' + spacify("SS Salinity:       ") + '</b>' + str(surface_salt) + '<br>')
        datums.write('<p class="bsalt">' + '<b>' + spacify("Bottom Salt:     ") + '</b>' + str(bottom_salt) + '<br>')
        datums.write('<p class="ssh">' + '<b>' + spacify("SSH:                   ") + '</b>' + str(ssh) + ' Ft' + '<br>')
    return datums

@csrf_exempt
def tides(request):
    #This responds to requests from the Javascript to grab tide info
    #It retrieves the information from the static tide files
    #-------------------------------------------------------------------------
    station_id = json.loads(request.body)["station_id"]
    display_date = json.loads(request.body)["display_date"]
    address = '/opt/sharkeyes/src/static_files/tides/' + station_id + '.txt'
    fopen = open(address, 'r')
    response = HttpResponse()
    response.write('<table class="tides"><tr><th>Time</th><th></th><th>Feet</th><th>H/L</th>')
    for line in fopen:
        info = line.split()
        if info[0] == display_date:
            info.pop(5)
            response.write('<tr>')
            for x in info[2:]:
                response.write('<th style="padding:0 10px 0 0px;">' + x + '</th>')
            response.write('</tr>')
    response.write('</table>')
    return response

@csrf_exempt
def survey(request):
    return render(request, 'survey.html')

@csrf_exempt
def save_survey(request):
    usage_location = json.loads(request.body)["usage_location"]
    usage_frequency = json.loads(request.body)["usage_frequency"]
    usage_device = json.loads(request.body)["usage_device"]
    ss_temperature_accuracy = json.loads(request.body)["sst_accuracy"]
    ss_currents_accuracy = json.loads(request.body)["currents_accuracy"]
    wave_accuracy = json.loads(request.body)["wave_accuracy"]
    wind_accuracy = json.loads(request.body)["wind_accuracy"]
    btemp_accuracy = json.loads(request.body)["btemp_accuracy"]
    salt_accuracy = json.loads(request.body)["salt_accuracy"]
    bsalt_accuracy = json.loads(request.body)["bsalt_accuracy"]
    ssh_accuracy = json.loads(request.body)["ssh_accuracy"]
    usage_comparison = json.loads(request.body)["usage_comparison"]
    usage_likes = json.loads(request.body)["usage_likes"]
    usage_suggestion = json.loads(request.body)["usage_suggestion"]
    usage_model_suggestion = json.loads(request.body)["usage_model_suggestion"]
    port = json.loads(request.body)["port"]
    general_comment = json.loads(request.body)["usage_comments"]
    sent = False

    try:
        #Establish DB Connection
        cursor = connection.cursor()
        #Execute SQL Query
        cursor.execute("""INSERT INTO SharkEyesCore_feedbackquestionaire(usage_location, usage_frequency, usage_device,usage_comment, 
                        ss_temperature_accuracy, ss_currents_accuracy, wave_accuracy, wind_accuracy, btemp_accuracy, salt_accuracy, bsalt_accuracy, 
                        ssh_accuracy, usage_comparison,usage_likes, usage_suggestion, port,  
                        usage_model_suggestion, sent ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s, %s, %s, %s);""",
                       (usage_location, usage_frequency, usage_device, general_comment, ss_temperature_accuracy, ss_currents_accuracy,wave_accuracy,
                        wind_accuracy, btemp_accuracy, salt_accuracy, bsalt_accuracy, ssh_accuracy, usage_comparison, usage_likes, usage_suggestion, port, usage_model_suggestion, sent))
        #Nothing needs to be returned
    except IntegrityError as e:
        print "Error Message: "
        print e.message

    return render(request, 'survey.html')
@csrf_exempt
def save_feedback(request):
    #Access feedback data to be saved into the database
    feedback_title = json.loads(request.body)["title"]
    feedback_comment = json.loads(request.body)["comment"]
    sent = False  #By default, a survey has Not yet been delivered
    feedback_name = json.loads(request.body)["name"]
    feedback_email = json.loads(request.body)["email"]
    feedback_phone = json.loads(request.body)["phone"]
    feedback_date = timezone.now()

    try:
        #Establish DB Connection
        cursor = connection.cursor()
        #Execute SQL Query
        cursor.execute("""INSERT INTO SharkEyesCore_feedbackhistory (feedback_title, feedback_comments, sent, feedback_name, feedback_email, feedback_phone, feedback_date) VALUES (%s, %s, %s, %s, %s, %s, %s);""", (feedback_title, feedback_comment, sent, feedback_name, feedback_email, feedback_phone, feedback_date))
        #Nothing needs to be returned
    except IntegrityError as e:
        print "Error Message: "
        print e.message
    return render(request, 'index.html')