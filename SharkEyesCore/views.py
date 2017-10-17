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
from django.db import connection
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import HttpResponse

# Helper Functions for right_click_menu
# Organizes the date into a usable list of values
# ------------------------------------------------------------------
def prepDate(date):
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

# Finds the correct lat and lon indices for the model
# --------------------------------------------------------------------
def getLatLongIndex(lat, lon, dataset, model):
    indices = []
    flatSize = 0
    lat_name = ''
    lon_name = ''
    if model == 'wind':
        flatSize = 5612
        lat_name = 'lat'
        lon_name = 'lon'
    elif model == 'ncdf':
        flatSize = 161820
        lat_name = 'lat_rho'
        lon_name = 'lon_rho'
    elif model == 'wave':
        flatSize = 284257
        lat_name = 'latitude'
        lon_name = 'longitude'
        lon = lon%360 #The wave watch longitude values are saved in degrees east. This converts them to degrees west which is what we get from the front-end
    #lat = np.round(lat, 7)
    #lon = np.round(lon, 7)
    file_lats = dataset.variables[lat_name][:]
    file_lons = dataset.variables[lon_name][:]
    file_lat = np.abs(file_lats - lat).argmin()
    file_lon = np.abs(file_lons - lon).argmin()
    print "file_lat ", file_lat
    print "file_lon ", file_lon
    file_lat = np.unravel_index(np.ravel(file_lat, file_lats.shape), file_lats.shape)
    #file_lon = np.unravel_index(np.ravel(file_lon, file_lons.shape), file_lons.shape)
    print "file_lat ", file_lat
    print "file_lon ", file_lon
    file_lat = file_lat[0][0]
    #file_lon = file_lon[1][0]
    print "file_lat ", file_lat
    print "file_lon ", file_lon
    print "lat ", file_lats[file_lat][file_lon]
    print "lon ", file_lons[file_lat][file_lon]
    indices.append(file_lat)
    indices.append(file_lon)
    return indices

# Calculates the necessary time index for Alex's Model
# --------------------------------------------------------------------
def getTimeIndexNCDF(ncdf_data, day, month, year, hour, meridian):
    if hour == 12 and meridian == "a.m.":
        hour = 0
    input_time = datetime(day=day, month=month, year=year, hour=hour, minute=0, second=0, tzinfo=timezone.utc)
    dst = 0
    isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
    if isdst_now_in("America/Los_Angeles"):
        dst = 1
    dst_hours = timedelta(hours=dst)
    time_zone_correction = timedelta(hours=6)
    input_time = input_time + dst_hours - time_zone_correction
    ocean_time_epoch = datetime(day=1, month=1, year=2005, hour=0, minute=0, second=0, tzinfo=timezone.utc)
    for x in range(0, np.shape(ncdf_data.variables['ocean_time'])[0], 1 ):
        seconds_since_epoch = timedelta(seconds=ncdf_data.variables['ocean_time'][x])
        check_date = ocean_time_epoch + seconds_since_epoch
        # print "check date ", check_date
        # print "input time ", input_time
        if check_date == input_time:
            print "index ", x
            return x

# Calculates the time index for the wind model
# This function is a bit more complex than the others because
# the wind time indices are not consistent. They swap from every hour to every three hours.
# -----------------------------------------------------------------------
def getTimeIndexWind(wind_file, day, month, year, hour, meridian):
    index = 0
    if hour == 12 and meridian == "a.m.":
        hour = 0
    if hour != 12 and meridian == "p.m.":
        hour += 12
    dst = 0
    isdst_now_in = lambda zonename: bool(datetime.now(pytz.timezone(zonename)).dst())
    if isdst_now_in("America/Los_Angeles"):
        dst = 1
    input_time = datetime(day=day, month=month, year=year, hour=hour, minute=0, second=0, tzinfo=timezone.utc)
    wind_name = wind_file.file.name
    wind_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT, settings.WIND_DIR, wind_name), 'r')
    indices = np.shape(wind_data.variables['time'])[0]
    for x in xrange(0, indices, 1):
        raw_epoch_date = str(wind_file.model_date)
        epoch_date = raw_epoch_date.split('-')
        epoch_year = int(epoch_date[0])
        epoch_month = int(epoch_date[1])
        epoch_day = int(epoch_date[2])
        ocean_time_epoch = datetime(day=epoch_day, month=epoch_month, year=epoch_year, hour=7, minute=0, second=0,
                                    tzinfo=timezone.utc)
        modifier = 0
        if x == 49 or x == 53 or x == 57 or x == 61:
            modifier = 1
        elif x == 51 or x == 55 or x == 59 or x == 63:
            modifier = -1
        hours_since_epoch = timedelta(hours=(wind_data.variables['time'][x] + dst - wind_data.variables['reftime'][0]) + modifier)
        current_date = ocean_time_epoch + hours_since_epoch
        if current_date == input_time:
            index = x
    #print "Index ", index
    return index

# Calculates the time index for Tuba's WW3 file
# -----------------------------------------------------------------------------
def getTimeIndexWave(hour, day, meridian):
    index = 0
    modifier = 0
    if day == 1: #One file covers 3.5 days. This checks how many days ahead the request is and adds a modifier the the time index.
        modifier = 24
    if day == 2:
        modifier = 48
    if day == 3:
        modifier = 72
    if hour%2 == 1:
        new_time = hour - 1
    else:
        new_time = hour
    if meridian == 'p.m.':
        if new_time == 12: #Noon
            index = 0
        elif new_time == 4:
            index = 4
        elif new_time == 8:
            index = 8
    if meridian == 'a.m.':
        if new_time == 12: #Midnight
            index = 12
        elif new_time == 4:
            index = 16
        elif new_time == 8:
            index = 20
    return index + modifier

# Returns which model types are being displayed
# ------------------------------------------------------------------------------
def getModels(keys):
    models = []
    wave = 0
    ncdf = 0
    wind = 0
    for x in keys:
        if x.find('wave') != -1 and wave == 0:
            models.append('wave')
            wave = 1
        elif x.find('sst') != -1 or x.find('currents') != -1 or x.find('bottom') != -1 or x.find('salt') != -1 or x.find('ssh') != -1 and ncdf == 0:
            models.append('ncdf')
            ncdf = 1
        elif x.find('barb') != -1 and wind == 0:
            models.append('wind')
            wind = 1
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
    print "Lat ", lat
    print "Lon ", lon

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
    clean_date = prepDate(query_date)
    hour = clean_date[0]
    meridian = clean_date[1]
    month = clean_date[2]
    day = clean_date[3]
    current_date = datetime.now()
    current_year = str(current_date.year)
    current_day = str(current_date.day)
    print "day ", current_day

    #Find out which models are being viewed
    keys = json.loads(request.body)["keys"]
    models = getModels(keys) #The key names are messy. This function parses them and determines what is being viewed
    #This determines which models to display at the cursor
    wave = 0
    ncdf = 0
    wind = 0
    for x in models:
        if x == 'wave':
            wave = 1
        elif x == 'ncdf':
            ncdf = 1
        elif x == 'wind':
            wind = 1
    #To disable any of the models just set its variable to 1 after this check
    wind = 0

    #Access the relevant netcdf files. Wave is Tuba's WW3 file, ncdf is Alex's model, wind is the wind model
    if wave == 1 and wave_lat_lon_check == 0:
    #Wave Watch 3 file access
        wave_file = DataFile.objects.filter(type='WAVE').latest('model_date')
        wave_name = wave_file.file.name
        wave_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT,settings.WAVE_WATCH_DIR,wave_name), 'r')

        #Get Wave Watch 3 lat lon indices
        wave_index = getLatLongIndex(lat, lon, wave_data, 'wave')
        wave_lat = wave_index[0]
        wave_lon = wave_index[1]

        #Get the wave watch 3 time index
        wave_date = str(wave_file.model_date)
        wave_date = wave_date.split('-')
        wave_day = int(day) - int(wave_date[2])#Needed because one wind file covers 3 days. This finds out how many days out the request is
        wave_time_index = getTimeIndexWave(int(hour), wave_day, meridian)

        #Get the wave watch 3 wave height value
        wave_height = wave_data.variables['HTSGW_surface'][wave_time_index, wave_lat, wave_lon]
        wave_height = np.round(wave_height * 3.28, 3) #Convert from meters to feet and round to 3 decimal places.

    if ncdf == 1:
        #Alex's model(sst, currents, ssh, salinity, etc...) file access
        if int(day) < int(current_day):
            day = current_day
        ncdf_file_date = "OSU_ROMS_" + current_year + "-" + month + "-" + day #This is used to create a string for use in the DB lookup
        ncdf_file = DataFile.objects.filter(type='NCDF').filter(file__startswith=str(ncdf_file_date))
        ncdf_name = ncdf_file[0].file.name
        ncdf_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT,settings.NETCDF_STORAGE_DIR,ncdf_name), 'r')

        #Get Alex's model lat lon indices
        ncdf_index = getLatLongIndex(lat, lon, ncdf_data, 'ncdf')
        ncdf_lat = ncdf_index[0]
        ncdf_lon = ncdf_index[1]

        #Get the time index for Alex's model
        ncdf_time_index = getTimeIndexNCDF(ncdf_data, int(day), int(month), int(current_year), int(hour), meridian)

        #Get the values from Alex's model
        ssh = ncdf_data.variables['zeta'][ncdf_time_index,ncdf_lat:ncdf_lat+1,ncdf_lon:ncdf_lon+1]
        ssh = np.round(ssh[0][0] * 3.28, 3) #convert from meters to feet
        surface_temp = ncdf_data.variables['temp'][ncdf_time_index,39,ncdf_lat:ncdf_lat+1,ncdf_lon:ncdf_lon+1]
        surface_temp = np.round(surface_temp[0][0] * 1.8 + 32, 3) #convert from celsius to fahrenheit
        bottom_temp = ncdf_data.variables['temp'][ncdf_time_index,0,ncdf_lat:ncdf_lat+1,ncdf_lon:ncdf_lon+1]
        bottom_temp = np.round(bottom_temp[0][0] * 1.8 + 32, 3) #convert from celsius to fahrenheit
        surface_salt = ncdf_data.variables['salt'][ncdf_time_index,39,ncdf_lat:ncdf_lat+1,ncdf_lon:ncdf_lon+1]
        surface_salt = np.round(surface_salt[0][0], 3)
        bottom_salt = ncdf_data.variables['salt'][ncdf_time_index,0,ncdf_lat:ncdf_lat+1,ncdf_lon:ncdf_lon+1]
        bottom_salt = np.round(bottom_salt[0][0], 3)
        ncdf_u = ncdf_data.variables['u'][ncdf_time_index,39,ncdf_lat:ncdf_lat+1,ncdf_lon:ncdf_lon+1]
        ncdf_v = ncdf_data.variables['v'][ncdf_time_index,39,ncdf_lat:ncdf_lat+1,ncdf_lon:ncdf_lon+1]
        current_speed = np.round(np.sqrt(ncdf_u[0][0]**2 + ncdf_v[0][0]**2) * 1.944, 3)#convert from m/s to knots

    if wind == 1:
        #Wind file access
        wind_file = DataFile.objects.filter(type='WIND').latest('model_date')
        wind_name = wind_file.file.name
        wind_data = netcdf.netcdf_file(os.path.join(settings.MEDIA_ROOT,settings.WIND_DIR,wind_name), 'r')

        #Get wind file lat lon indices
        wind_index = getLatLongIndex(lat, lon, wind_data, 'wind')
        x = wind_index[1]
        y = wind_index[0]

        #Get the time index for the wind model
        wind_time_index = getTimeIndexWind(wind_file, int(day), int(month), int(current_year), int(hour), meridian)  # Gets the wind time index
        print "got here"

        #Get the wind model values
        wind_u = wind_data.variables['u-component_of_wind_height_above_ground'][wind_time_index,0,y,x]
        wind_v = wind_data.variables['v-component_of_wind_height_above_ground'][wind_time_index,0,y,x]
        wind_speed = np.round(np.sqrt(wind_u**2 + wind_v**2) * 1.944, 3)#converts from m/s to knots and rounds to 3 decimals

    #Build the html strings to send back to the front-end
    d = u"\u00b0" #unicode degree symbol
    if ncdf == 0 and wave == 0 and wind == 0:
        datums.write('<p style="font-size:20px">' + '<b>' 'Select a field to view lat long specific information' '</b>')
        return datums
    datums.write('<p style="font-size:20px">' + '<b>' + "Location: " + " Lat " + '</b>' + str(np.round(lat,3)) + '<b>' + " Lon " + '</b>' + str(np.round(lon,3)) + '<br>')
    if ncdf == 1:
        datums.write('<p style="font-size:20px">' + '<b>' + "Sea Surface Temperature: " + '</b>' + str(surface_temp) + ' ' + d + 'F' + '<br>')
        datums.write('<p style="font-size:20px">' + '<b>' + "Surface Currents: " + '</b>' + str(current_speed) + ' Knots' + '<br>')
    if wave == 1 and wave_lat_lon_check == 0:
        datums.write('<p style="font-size:20px">' + '<b>' + "Wave Height: " + '</b>' + str(wave_height) + ' Feet' + '<br>')
    if wave ==1 and wave_lat_lon_check == 1:
        datums.write('<p style="font-size:20px">' + '<b>' 'There is no wave height data for this location' '</b>')
    if wind == 1:
        datums.write('<p style="font-size:20px">' + '<b>' + "Winds: " + '</b>' + str(wind_speed) + ' Knots' + '<br>')
    if ncdf == 1:
        datums.write('<p style="font-size:20px">' + '<b>' + "Bottom Temperature: " + '</b>' + str(bottom_temp) + ' ' + d + 'F' + '<br>')
        datums.write('<p style="font-size:20px">' + '<b>' + "Surface Salinity: " + '</b>' + str(surface_salt) + '<br>')
        datums.write('<p style="font-size:20px">' + '<b>' + "Bottom Salinity: " + '</b>' + str(bottom_salt) + '<br>')
        datums.write('<p style="font-size:20px">' + '<b>' + "Sea Surface Height: " + '</b>' + str(ssh) + ' Feet' + '<br>')
    return datums

@csrf_exempt
def tides(request):
    #This responds to requests from the Javascript to grab tide info
    #It retrieves the information from the static tide files
    #-------------------------------------------------------------------------
    station_id = json.loads(request.body)["station_id"]
    display_date = json.loads(request.body)["display_date"]
    address = '/opt/sharkeyes/src/static_files/tides/' + station_id + '.txt'
    tideData = []
    fopen = open(address, 'r')
    response = HttpResponse()
    response.write('<table style="font-size:20px"><tr><th>Time</th><th></th><th>Feet</th><th>Cm</th><th>High/Low</th> ')
    for line in fopen:
        info = line.split()
        if info[0] == display_date:
            response.write('<tr>')
            for x in info[2:]:
                response.write('<th style="padding:0 15px 0 0px;">' + x + '</th>')
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
    usage_comparison = json.loads(request.body)["usage_comparison"]
    usage_likes = json.loads(request.body)["usage_likes"]
    usage_suggestion = json.loads(request.body)["usage_suggestion"]
    usage_model_suggestion = json.loads(request.body)["usage_model_suggestion"]
    general_comment = json.loads(request.body)["usage_comments"]
    sent = False

    try:
        #Establish DB Connection
        cursor = connection.cursor()
        #Execute SQL Query
        cursor.execute("""INSERT INTO SharkEyesCore_feedbackquestionaire(usage_location, usage_frequency, usage_device,usage_comment, ss_temperature_accuracy, ss_currents_accuracy, wave_accuracy,  wind_accuracy, usage_comparison,usage_likes, usage_suggestion, usage_model_suggestion, sent ) VALUES (%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s, %s);""",(usage_location, usage_frequency, usage_device, general_comment, ss_temperature_accuracy, ss_currents_accuracy,wave_accuracy, wind_accuracy, usage_comparison, usage_likes, usage_suggestion, usage_model_suggestion, sent))
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