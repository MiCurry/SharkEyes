import numpy
import scipy
from scipy import ndimage
from matplotlib import pyplot, colors

from django.conf import settings
from pl_download.models import DataFile
from pl_plot.plotter import WindPlotter, NcepWW3Plotter
from pl_download.models import DataFile
import os
from scipy.io import netcdf
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta, time



numpy.set_printoptions(threshold=numpy.inf) # This is helpful for testing purposes:
# it sets print options so that when you print a large array, it doesn't get truncated in the middle
# and you can see each element of the array.

# When you add a new function, add it as a new function definition to fixtures/initial_data.json

VERBOSE = settings.VERBOSE

NUM_COLOR_LEVELS = 80
NUM_COLOR_LEVELS_FOR_WAVES = 120
#WAVE_DIRECTION_DOWNSAMPLE = 20

#These heights are in meters
MIN_WAVE_HEIGHT = 0
MAX_WAVE_HEIGHT = 7
METERS_TO_FEET = 3.28

# Min and max time for a single wave to pass
MIN_WAVE_PERIOD = 3
MAX_WAVE_PERIOD = 26

MIN_TEMP_C_TOP = 0
MAX_TEMP_C_TOP = 15

MIN_TEMP_F_TOP = 46
MAX_TEMP_F_TOP = 58
MIN_TEMP_F_BOT = 32
MAX_TEMP_F_BOT = 60

MIN_SAL_TOP = 28
MAX_SAL_TOP = 34
MIN_SAL_BOT = 32
MAX_SAL_BOT = 34


def get_rho_mask(data_file):
    rho_mask = numpy.logical_not(data_file.variables['mask_rho'][:])
    return rho_mask

""" WAVES """
def wave_direction_function(ax, data_file, bmap, key_ax, forecast_index, downsample_ratio):
    all_day_height = data_file.variables['HTSGW_surface'][:, :, :]
    all_day_direction = data_file.variables['DIRPW_surface'][:,:,:]
    lats = data_file.variables['latitude'][:, :]
    longs = data_file.variables['longitude'][:, :]

    directions = all_day_direction[forecast_index, :, :]
    height = all_day_height[forecast_index, :, :]
    directions_mod = 90.0 - directions + 180.0

    index = directions_mod > 180
    directions_mod[index] = directions_mod[index] - 360;
    index = directions_mod < -180;
    directions_mod[index] = directions_mod[index] + 360;


    # The sine and cosine functions expect Radians, so we use the deg2rad function to convert the
    # directions, which are in Degrees.
    # Multiplying the U and the V, each, by 'height' in order to SCALE the vectors.
    U = height*numpy.cos(numpy.deg2rad(directions_mod))
    V = height*numpy.sin(numpy.deg2rad(directions_mod))

    U_downsampled = crop_and_downsample_wave(U, downsample_ratio)
    V_downsampled = crop_and_downsample_wave(V, downsample_ratio)

    x, y = bmap(longs, lats)

    x_zoomed = crop_and_downsample_wave(x, downsample_ratio)
    y_zoomed = crop_and_downsample_wave(y, downsample_ratio)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    # Some documentation here: http://matplotlib.org/api/pyplot_summary.html
    overlay = bmap.quiver(x_zoomed, y_zoomed, U_downsampled, V_downsampled, ax=ax, units='inches',
                          color='black', scale=75.0, headwidth=2, headlength=3,
                          headaxislength=2.5, minlength=0.5, minshaft=.9)

    # Set up the conversions to feet from meters
    half = 0.5*METERS_TO_FEET
    one = 1.0*METERS_TO_FEET
    two = 2.0*METERS_TO_FEET
    three = 3.0*METERS_TO_FEET
    five = 5.0*METERS_TO_FEET
    six = 6.0*METERS_TO_FEET

    #get the wave period data from a netCDF file
    #-------------------------------------------------------------------------
    all_day = data_file.variables['PERPW_surface'][:, :, :]

    # Mask all of the data points that are "nan" (not a number) in the data file; these represent land
    #-------------------------------------------------------------------------
    period_masked = numpy.ma.masked_array(all_day[forecast_index][:, :],numpy.isnan(all_day[forecast_index][:,:]))

    #This is the average wave period for the day
    #-------------------------------------------------------------------------
    mean_val = numpy.mean(period_masked)
    #The mean val is calculated to a large number of decimal places. This rounds it to two.
    #-------------------------------------------------------------------------
    mean_val = round(mean_val, 2)

    #This is the maximum wave period value for the day
    #-------------------------------------------------------------------------
    max_val = numpy.amax(period_masked)
    #This rounds the max value just like the average
    #-------------------------------------------------------------------------
    max_val = round(max_val, 2)

    #TextBox is the wave period key. The spacing exists specifically for readability
    #If you need to modify the way wave period looks in the window do it here
    #-------------------------------------------------------------------------
    textBox = pyplot.text(0, 0,"       Wave period average and maximum values ""\n" "Average: " + str(mean_val) + " seconds " "  -  "" Maximum: " + str(max_val) + " seconds", withdash=False, backgroundcolor='black', color='white')
    key_ax.set_axis_off()

def wave_height_function(ax, data_file, bmap, key_ax, forecast_index, downsample_ratio):
    # Wave Model Data Information:
    # Wave Data comes in 3D arrays (number of forecasts, latitude, longitude)
    # As of right now (March 15) there are 85 forecasts in each netCDF file from 12 pm onward by the hour
    # Wave Heights are measured in meters
    # Wave direction is measured in Degrees, where 360 means waves are coming from the north, traveling southward.
    # 350 would mean waves are traveling from the north-west, headed south-east.
    # Data points over 1000 usually mark land
     # Need to convert each point from meters to feet
     #-------------------------------------------------------------------------
     def meters_to_feet(height):
        return height * METERS_TO_FEET

     vectorized_conversion = numpy.vectorize(meters_to_feet)

     # If we are using the file with merged fields (both high-res and low-res data) provided
     # by Tuba and Gabriel
     #-------------------------------------------------------------------------
     longs = [item for sublist in data_file.variables['longitude'][:1] for item in sublist]
     lats = data_file.variables['latitude'][:, 0]

     #get the wave height data from netCDF file
     #-------------------------------------------------------------------------
     all_day = data_file.variables['HTSGW_surface'][:, :, :]

     #convert/mesh the latitude and longitude data into 2D arrays to be used by contourf below
     #-------------------------------------------------------------------------
     x,y = numpy.meshgrid(longs,lats)

     #obtain all forecasts
     #heights is measured in meters, if a data point is over 1000 meters it is either not valid or it represents land
     #so we are masking all data over 1000
     #-------------------------------------------------------------------------
     heights_masked = numpy.ma.masked_array(all_day[forecast_index][:, :],numpy.isnan(all_day[forecast_index][:,:]))

     # Need to convert each height given in meters into FEET
     #-------------------------------------------------------------------------
     heights = vectorized_conversion(heights_masked)

     #Min period is now in feet
     #-------------------------------------------------------------------------
     min_period = MIN_WAVE_HEIGHT*METERS_TO_FEET

     #Max period is now in feet
     #-------------------------------------------------------------------------
     max_period = MAX_WAVE_HEIGHT*METERS_TO_FEET

     #Allocates colors to the data by setting the range of the data and by setting color increments
     #-------------------------------------------------------------------------
     contour_range = max_period - min_period
     contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS_FOR_WAVES

     #Now the contour range
     #-------------------------------------------------------------------------
     color_levels = []
     for i in xrange(NUM_COLOR_LEVELS_FOR_WAVES+1):
         color_levels.append(min_period+1 + i * contour_range_inc)

     #Fill the contours with the colors
     #-------------------------------------------------------------------------
     overlay = bmap.contourf(x, y, heights, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap_for_waves())

     #Create the color bar
     #-------------------------------------------------------------------------
     cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
     cbar.ax.tick_params(labelsize=10)
     cbar.ax.xaxis.label.set_color('white')
     cbar.ax.xaxis.set_tick_params(labelcolor='white')

     #DIVISION by ZERO sometimes causes a warning but it doesn't seem to cause any problems
     #-------------------------------------------------------------------------
     locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS_FOR_WAVES))[::10]    # we just want every 10th label
     float_labels = numpy.arange(min_period, max_period + 0.01, contour_range_inc)[::10]

     labels = ["%.1f" % num for num in float_labels]
     cbar.ax.xaxis.set_ticks(locations)
     cbar.ax.xaxis.set_ticklabels(labels)
     cbar.set_label("Wave Height (feet)")

def ww3_direction(ax, data_file, bmap, key_ax, forecast_index, downsample_ratio):
    """ NCEP WW3 Direction and Period. Period is saved to a figure in keys similar to
    wave_direction_function above.

    Create a quiver/vector plot of ncep ww3 period for the given datafile at the
    given forecast_index. As well produce a key that contains the mean and max wave
    period for the forecast_index.

    :param data_file: Datafile of a NCEP WW3 download. See settings.py or pl_download for link
    :param forecast_index: Time slice of desired plot
    :return:
    """
    UNIT = -1 # Unit Length

    """ lon comes in degrees east and because we coded the bmap latitude and longitude
    in degrees west we need to covert to degrees west. """
    def convert_to_degrees_west(x):
        y = 180 - x; return -(y + 180)

    direction_string = 'Primary_wave_direction_surface'
    directions = data_file.variables[direction_string]
    directions = directions[forecast_index]

    lats = data_file.variables['lat']
    lons = data_file.variables['lon']

    lons = map(float, lons) # Lons and Lats need to be floats and not a NETCDF variable
    lats = map(float, lats) # Lons and Lats need to be floats and not a NETCDF variable
    lons = map(convert_to_degrees_west, lons)


    """ Primary_wave_direction_surface comes in degrees. quiver() requires its input
    to be in U and V vectors, so we need to generate both U and V vectors from a
    degree:
    
        To do this, take the degree at unit length and find its components:
        
            u vector = sin(theta) * UNIT
            v vector = cos(theta) * UNIT 
            
        Where UNIT == 1 or -1
            
    """
    directions = numpy.deg2rad(directions) # Numpy likes rads
    u = numpy.sin(directions) * UNIT
    v = numpy.cos(directions) * UNIT


    x, y = numpy.meshgrid(lons, lats)

    bmap.drawcoastlines()
    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.quiver(x, y, u, v,
                          ax=ax,
                          color='black',
                          scale=9.5,
                          scale_units='inches',
                          )


    """ Wave Period 
   
    Find the mean and max period of the whole domain and save it to a textbox
    that will be loaded as a key and shown on the website.
    
    """
    period_string = 'Primary_wave_mean_period_surface'
    wave_period = data_file.variables[period_string][forecast_index]

    period_masked = numpy.ma.masked_array(wave_period,numpy.isnan(wave_period))

    mean_val = numpy.mean(period_masked)
    mean_val = round(mean_val, 2) # Round to two decimal places and not a million

    max_val = numpy.amax(period_masked)
    max_val = round(max_val, 2)

    textBox = pyplot.text(0,
                          0,
                          "    Extended - Wave period average and maximum values ""\n" "Average: " + str(mean_val) + " seconds " "  -  "" Maximum: " + str(max_val) + " seconds",
                          withdash=False,
                          backgroundcolor='black',
                          color='white')
    key_ax.set_axis_off()

def ww3_height(ax, data_file, bmap, key_ax, forecast_index, downsample_ratio):
    """ Produces a contourf color map for NCEP's WW3.

    Put heights into contourf() function with modified latitude and longitude
    to produce the desired color plot.

    Longitude is converted into degrees west, so this function is expecting
    longitude to be passed in as degrees east.

    :param data_file: A netcdf file containing the correct fields
    :param bmap: The Basemap containing the latitude and longitude map constraints. Where longitude
    is passed in as degrees east.
    :param forecast_index: the time slice to be used with the data_file
    """

    def meters_to_feet(height):
        return height * METERS_TO_FEET

    vectorized_conversion = numpy.vectorize(meters_to_feet)

    """ longitude comes in degrees east and because we coded the bmap latitude and longitude
    in degrees west we need to covert to degrees west. """
    def convert_to_degrees_west(x):
        y = 180 - x; return -(y + 180)

    min_period = MIN_WAVE_HEIGHT * METERS_TO_FEET
    max_period = MAX_WAVE_HEIGHT * METERS_TO_FEET

    contour_range = max_period - min_period
    contour_range_inc = float(contour_range) / NUM_COLOR_LEVELS_FOR_WAVES

    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS_FOR_WAVES + 1):
        color_levels.append(min_period + 1 + i * contour_range_inc)

    height = "Significant_height_of_combined_wind_waves_and_swell_surface"

    heights = data_file.variables[height][forecast_index, :, :]
    heights = numpy.ma.masked_array(heights, numpy.isnan(heights))
    heights = vectorized_conversion(heights)

    lons = data_file.variables['lon']
    lats = data_file.variables['lat']

    lats = map(float, lats) # Converting the latitude into Floats and not netcdf variables
    lons = map(float, lons) # Likewise
    lons = map(convert_to_degrees_west, lons)

    x, y = numpy.meshgrid(lons, lats)

    print "x shape", x.shape
    print "y shape", y.shape
    print "heights shape", heights.shape

    overlay = bmap.contourf(x, y, heights, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap_for_waves())

    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0 / (NUM_COLOR_LEVELS_FOR_WAVES))[::10]  # we just want every 10th label
    float_labels = numpy.arange(min_period, max_period + 0.01, contour_range_inc)[::10]

    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Wave Height (Feet) - Extended")


""" OSU ROMS """
def sst_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    def celsius_to_fahrenheit(temp):
        return temp * 1.8 + 32
    vectorized_conversion = numpy.vectorize(celsius_to_fahrenheit)

    # temperature has dimensions ('ocean_time', 's_rho', 'eta_rho', 'xi_rho')
    # s_rho corresponds to layers, of which there are 30, so we take the top one.
    #-------------------------------------------------------------------------
    surface_temp = numpy.ma.array(vectorized_conversion(data_file.variables['temp'][time_index][39]), mask=get_rho_mask(data_file))
    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]

    #get the max and min temps for the daytem
    #-------------------------------------------------------------------------
    #all_day = data_file.variables['temp'][:, 39, :, :]
    #min_temp = int(math.floor(celsius_to_fahrenheit(numpy.amin(all_day))))
    #max_temp = int(math.ceil(celsius_to_fahrenheit(numpy.amax(numpy.ma.masked_greater(all_day, 1000)))))
    min_temp = 46
    max_temp = 58

    x, y = bmap(longs, lats)
    print "st shape", surface_temp.shape
    print "x shape", x.shape
    print "y shape", y.shape


    # calculate and plot colored contours for TEMPERATURE data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    #-------------------------------------------------------------------------
    contour_range = ((max_temp) - (min_temp))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS
    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_temp+1 + i * contour_range_inc)

    print "temp.SHAPE:", surface_temp.shape
    print "lat.SHAPE:", lats.shape
    print "lon.SHAPE:", longs.shape
    print "x.SHAPE:", x.shape
    print "y.SHAPE:", y.shape

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, surface_temp, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
    #-------------------------------------------------------------------------
    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::10]    # we just want every 10th label
    float_labels = numpy.arange(min_temp, max_temp + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Fahrenheit")

def bottom_temp_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    def celsius_to_fahrenheit(temp):
        return temp * 1.8 + 32
    vectorized_conversion = numpy.vectorize(celsius_to_fahrenheit)

    # temperature has dimensions ('ocean_time', 's_rho', 'eta_rho', 'xi_rho')
    # s_rho corresponds to layers, of which there are 30, so we take the top one.
    #-------------------------------------------------------------------------
    surface_temp = numpy.ma.array(vectorized_conversion(data_file.variables['temp'][time_index][0]), mask=get_rho_mask(data_file))
    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]

    #get the max and min temps for the daytem
    #-------------------------------------------------------------------------
    #all_day = data_file.variables['temp'][:, 0, :, :]
    #min_temp = int(math.floor(celsius_to_fahrenheit(numpy.amin(all_day))))
    #max_temp = int(math.ceil(celsius_to_fahrenheit(numpy.amax(numpy.ma.masked_greater(all_day, 1000)))))
    min_temp = 32
    max_temp = 60

    x, y = bmap(longs, lats)

    # calculate and plot colored contours for TEMPERATURE data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    #-------------------------------------------------------------------------
    contour_range = ((max_temp) - (min_temp))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS
    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_temp+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, surface_temp, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
    #-------------------------------------------------------------------------
    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::10]    # we just want every 10th label
    float_labels = numpy.arange(min_temp, max_temp + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Fahrenheit")

def salt_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    # salt has dimensions ('ocean_time', 's_rho', 'eta_rho', 'xi_rho')
    # s_rho corresponds to layers, of which there are 30, so we take the top one.
    surface_salt = numpy.ma.array(data_file.variables['salt'][time_index][39], mask=get_rho_mask(data_file))

    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]

    #get the max and min salinity for the day
    #all_day = data_file.variables['salt'][:, 39, :, :]
    #min_salt = int(math.floor(numpy.amin(all_day)))
    #max_salt = int(math.ceil(numpy.amax(numpy.ma.masked_greater(all_day, 1000))))
    min_salt = 28
    max_salt = 34

    x, y = bmap(longs, lats)

    # calculate and plot colored contours for salinity data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    contour_range = ((max_salt) - (min_salt))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS

    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_salt+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, surface_salt, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::10]    # we just want every third label
    float_labels = numpy.arange(min_salt, max_salt + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Salinity (PSU)")

def bottom_salt_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    # salt has dimensions ('ocean_time', 's_rho', 'eta_rho', 'xi_rho')
    # s_rho corresponds to layers, of which there are 30, so we take the top one.
    surface_salt = numpy.ma.array(data_file.variables['salt'][time_index][0], mask=get_rho_mask(data_file))

    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]

    #get the max and min salinity for the day
    #all_day = data_file.variables['salt'][:, 0, :, :]
    #min_salt = int(math.floor(numpy.amin(all_day)))
    #max_salt = int(math.ceil(numpy.amax(numpy.ma.masked_greater(all_day, 1000))))
    min_salt = 32
    max_salt = 34

    x, y = bmap(longs, lats)

    # calculate and plot colored contours for salinity data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    contour_range = ((max_salt) - (min_salt))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS

    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_salt+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, surface_salt, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::10]    # we just want every third label
    float_labels = numpy.arange(min_salt, max_salt + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Salinity (PSU)")

def ssh_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    def meters_to_feet(height):
        return height * METERS_TO_FEET
    vectorized_conversion = numpy.vectorize(meters_to_feet)

    # Sea Surface Height has dimensions ('ocean_time', 'eta_rho', 'xi_rho')
    #-------------------------------------------------------------------------

    #all_day = data_file.variables['zeta'][:, :, :]
    zeta = data_file.variables['zeta'][:].copy()
    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]
    no_columbia_slice = zeta[time_index,:,:]
    no_columbia_slice = no_columbia_slice[75:354,:]
    no_columbia_slice[:,196:309]=numpy.nan
    no_columbia_slice = numpy.reshape(no_columbia_slice, 86490)
    for x in range(len(no_columbia_slice)):
        if no_columbia_slice[x] > 10:
            no_columbia_slice[x] = numpy.nan
    surface_height = numpy.ma.array(vectorized_conversion(data_file.variables['zeta'][time_index]), mask=get_rho_mask(data_file))
    # temp2 = vectorized_conversion(data_file.variables['zeta'][time_index,75:354,:])
    # temp2 = numpy.reshape(temp2, 86490)
    # for x in range(len(temp2)):
    #     if temp2[x] > 10:
    #         temp2[x] = numpy.nan
    # min_val = numpy.nanmin(temp2)
    # max_val = numpy.nanmax(temp2)
    # print "Min value ssh = ", min_val
    # print "Max value ssh = ", max_val
    # min_val_dummy = numpy.nanmin(no_columbia_slice)
    # max_val_dummy = numpy.nanmax(no_columbia_slice)
    # print "Min value ssh sliced = ", meters_to_feet(min_val_dummy)
    # print "Max value ssh sliced = ", meters_to_feet(max_val_dummy)
    surface_mean = numpy.nanmean(no_columbia_slice)
    surface_mean = meters_to_feet(surface_mean)
    # print "Mean of complete SSH ", numpy.nanmean(temp2)
    # print "Mean of sliced ssh = ", surface_mean
    surface_height_no_mean = numpy.subtract(surface_height, surface_mean)

    #get the max and min temps for the day
    #-------------------------------------------------------------------------
    #all_day = data_file.variables['zeta'][:, :, :]
    #min_height = int(math.floor(meters_to_feet(numpy.amin(all_day))))
    #max_height = int(math.ceil(meters_to_feet(numpy.amax(numpy.ma.masked_greater(all_day, 1000)))))
    min_height = -1.5
    max_height = .25

    x, y = bmap(longs, lats)

    # calculate and plot colored contours for TEMPERATURE data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    #-------------------------------------------------------------------------
    contour_range = ((max_height) - (min_height))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS
    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_height+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, surface_height_no_mean, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
    #-------------------------------------------------------------------------
    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::6]
    float_labels = numpy.arange(min_height, max_height + 0.01, contour_range_inc)[::6]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Feet")

def currents_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    def compute_average(array):
        avg = numpy.average(array)
        return numpy.nan if avg > 10**3 else avg

    currents_u = data_file.variables['u'][time_index][39]
    currents_v = data_file.variables['v'][time_index][39]
    rho_mask = get_rho_mask(data_file)

    # average nearby points to align grid, and add the edge column/row so it's the right size.
    #-------------------------------------------------------------------------
    right_column = currents_u[:, -1:]
    currents_u_adjusted = ndimage.generic_filter(scipy.hstack((currents_u, right_column)),
                                                 compute_average, footprint=[[1], [1]], mode='reflect')
    bottom_row = currents_v[-1:, :]
    currents_v_adjusted = ndimage.generic_filter(scipy.vstack((currents_v, bottom_row)),
                                                 compute_average, footprint=[[1], [1]], mode='reflect')

    # zoom
    #-------------------------------------------------------------------------
    u_zoomed = crop_and_downsample(currents_u_adjusted, downsample_ratio)
    v_zoomed = crop_and_downsample(currents_v_adjusted, downsample_ratio)
    rho_mask[rho_mask == 1] = numpy.nan
    rho_mask_zoomed = crop_and_downsample(rho_mask, downsample_ratio)
    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]

    longs_zoomed = crop_and_downsample(longs, downsample_ratio, False)
    lats_zoomed = crop_and_downsample(lats, downsample_ratio, False)

    u_zoomed[rho_mask_zoomed == 1] = numpy.nan
    v_zoomed[rho_mask_zoomed == 1] = numpy.nan

    x, y = bmap(longs_zoomed, lats_zoomed)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)

    overlay = bmap.quiver(x, y, u_zoomed, v_zoomed, ax=ax, color='black', units='inches',
                          scale=10.0, headwidth=2, headlength=3,
                          headaxislength=2.5, minlength=0.5, minshaft=.9)

    # Multiplying .5, 1, and 2 by .5144 is converting from knots to m/s
    #-------------------------------------------------------------------------
    # quiverkey = key_ax.quiverkey(overlay, .95, .4, 0.5*.5144, ".5 knots", labelpos='S', labelcolor='white',
    #                              color='white', labelsep=.5, coordinates='axes')
    # quiverkey1 = key_ax.quiverkey(overlay, 3.75, .4, 1*.5144, "1 knot", labelpos='S', labelcolor='white',
    #                               color='white', labelsep=.5, coordinates='axes')
    # quiverkey2 = key_ax.quiverkey(overlay, 6.5, .4, 2*.5144, "2 knots", labelpos='S', labelcolor='white',
    #                               color='white', labelsep=.5, coordinates='axes')
    textBox = pyplot.text(0, 0, "Right Click or Double Tap to View Values  ", withdash=False,
                          backgroundcolor='black', color='white', fontsize=17, )

    key_ax.set_axis_off()

def t_cline(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    def meters_to_feet(height):
        return height * METERS_TO_FEET
    vectorized_conversion = numpy.vectorize(meters_to_feet)

    lat_long_data = netcdf.netcdf_file(os.path.join(settings.STATIC_DIR,"latLongs.nc"))

    lats = lat_long_data.variables['lat_rho'][:]
    longs = lat_long_data.variables['lon_rho'][:]
    tcline = numpy.ma.array(vectorized_conversion(data_file.z_K.data), mask=numpy.isnan(data_file.z_K.data))

    min_depth = settings.MIN_TCLINE_DEPTH
    max_depth = settings.MAX_TCLINE_DEPTH

    x, y = bmap(longs, lats)

    contour_range = max_depth - min_depth
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS

    color_levels = []

    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_depth+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x,
                            y,
                            tcline,
                            color_levels,
                            ax=ax,
                            extend='both',
                            cmap=get_modified_jet_colormap())

    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::10]    # we just want every 10th label
    float_labels = numpy.arange(min_depth, max_depth + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    d = u"\u00b0"
    cbar.set_label("Depth in Feet where the water is 2 deg F cooler than the surface")

""" WIND """
# After the 48th time index the NAMS model changes to 3 hour intervals instead of every 4 hours like the rest
# of our models. Because of this we need to interpolate them as seen below.
# -------------------------------------------------------------------------
# The NAM's model are produced every 3 hours instead of every 4 hours like the rest
# of our models. Because of that we need to interpolate them as seen below.
#-------------------------------------------------------------------------
def wind_function(ax, data_file, bmap, time_index, downsample_ratio):
    VERBOSE = 10

    if VERBOSE > 0:
        print "CREATING A WIND PLOT"
    # We are now using barbs instead of vectors. We should not need this anymore
    # -------------------------------------------------------------------------
    # tmp = numpy.loadtxt('/opt/sharkeyes/src/latlon.g218')
    # lat = numpy.reshape(tmp[:, 2], data_file.variables['lat'])
    # lon = numpy.reshape(tmp[:, 3], data_file.variables['lat'])
    # for i in range(0, len(lon)):
    #     lon[i] = -lon[i]

    # Get the lats and longs from the file
    # -------------------------------------------------------------------------
    lat = data_file.variables['lat']
    lon = data_file.variables['lon']
    x, y = bmap(lon, lat)

    # Name of the variables we want to extract from Wind netcdf
    # -------------------------------------------------------------------------
    var_u = 'u-component_of_wind_height_above_ground'
    var_v = 'v-component_of_wind_height_above_ground'

    wind_u = data_file.variables[var_u]
    wind_v = data_file.variables[var_v]

    wind_u = wind_u[:, 0, :, :] # All times of u
    wind_v = wind_v[:, 0, :, :] # All times of

    # The wind data comes in meters per second. This converts it into knots.
    # -------------------------------------------------------------------------
    wind_u = numpy.multiply(wind_u, 1.943)
    wind_v = numpy.multiply(wind_v, 1.943)

    wind_file = DataFile.objects.filter(type='WIND').latest('model_date')
    plotter = WindPlotter(wind_file.file.name)
    wind_values = plotter.get_wind_indices()
    time_var = wind_values['time']
    interp_indices = wind_values['indices']

    interpolate = 0
    if time_index in interp_indices:
        interpolate = 1

    VERBOSE = 1

    interpolate = 1# Interpolation seems to be making all the plots the same.
    if interpolate == 1:
        # Interpolation process
        # -------------------------------------------------------------------------
        if VERBOSE > 0:
            print "INTERPOLATING"

        # Timestamps for interpolation purposes.
        # -------------------------------------------------------------------------
        times = data_file.variables[time_var]
        size = times.shape[0]

        # Create two different time stamps used for interpolating
        ts1 = numpy.arange(0, size * 3, 3) # One for every 3 hours
        ts2 = numpy.arange(0, size * 4, 4) # One for every 4 hours

        # Empty arrays for putting interpolated data
        # -------------------------------------------------------------------------
        wind_u_int = numpy.empty([ts2.shape[0], 92, 61]) # Array to be filled
        wind_v_int = numpy.empty([ts2.shape[0], 92, 61]) # Ditto

        # Interpolation Process interpolates wind_u and wind_v from ts1 to ts2 - Disable to turn off interpolation
        # -------------------------------------------------------------------------

        print ts2.shape
        print ts1.shape

        print wind_u.shape
        print wind_v.shape

        for i in range(0, 92):
            for j in range(0, 61):

                wind_u_int[:,i,j] = numpy.interp(ts2, ts1, wind_u[:,i,j])
                wind_v_int[:,i,j] = numpy.interp(ts2, ts1, wind_v[:,i,j])

        # Access the data at the current time index - Turn off if not interpolating
        # -------------------------------------------------------------------------
        wind_u = wind_u_int[time_index, :, :]
        wind_v = wind_v_int[time_index, :, :]

        # Interp returns an array of float64. This turns it into float32 to reduce memory usage
        # -------------------------------------------------------------------------
        wind_u = wind_u.astype(numpy.float32)
        wind_v = wind_v.astype(numpy.float32)

    if interpolate == 0:
        wind_u = wind_u[time_index, :, :]
        wind_v = wind_v[time_index, :, :]

    # Remove the time values from the data
    # -------------------------------------------------------------------------
    wind_u = numpy.squeeze(wind_u) # Squeeze out the time
    wind_v = numpy.squeeze(wind_v) # Squeeze out the time

    # Modify downsample ratio to change size of barbs
    # -------------------------------------------------------------------------
    length = 0
    if downsample_ratio == 1:
        length = 3
    elif downsample_ratio == 2:
        length = 4.25

    # Creates the unchopped png to be tiled
    # -------------------------------------------------------------------------

    if VERBOSE > 0:
        print "Making Unchopped Wind Barb Image"

    bmap.barbs(x[::downsample_ratio, ::downsample_ratio],
               y[::downsample_ratio, ::downsample_ratio],
               wind_u[::downsample_ratio, ::downsample_ratio],
               wind_v[::downsample_ratio, ::downsample_ratio],
               ax=ax,
               length=length, sizes=dict(spacing=0.2, height=0.3))
               #barb_increments=dict(half=.1, full=10, flag=50))

    if VERBOSE > 0:
        print "WIND PLOT CREATED"

""" RTOFS - NOT IN USE"""
def rtofs_temp(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    depth = 0
    min_temp = 34
    max_temp = 65

    num_color_levels = 80

    def celsius_to_fahrenheit(temp):
        return temp * 1.8 + 32
    vectorized_conversion = numpy.vectorize(celsius_to_fahrenheit)

    temps = data_file.variables['temperature'][time_index, depth]
    lats = data_file.variables['Latitude'][:]
    longs = data_file.variables['Longitude'][:]


    temps = numpy.ma.masked_where(temps > 35, temps) # mask really high values
    temps = numpy.ma.masked_array(temps, numpy.isnan(temps))
    temps = vectorized_conversion(temps) # convert to degrees f

    if VERBOSE > 0:
        print "lats shape", lats.shape
        print "longs shape", longs.shape
        print "temps shape", temps.shape


    x, y = bmap(longs, lats)

    contour_range = ((max_temp) - (min_temp))
    contour_range_inc = float(contour_range)/num_color_levels
    color_levels = []
    for i in xrange(num_color_levels+1):
        color_levels.append(min_temp+1 + i * contour_range_inc)

    bmap.drawcoastlines()
    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, temps, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(num_color_levels))[::10]    # we just want every 10th label
    float_labels = numpy.arange(min_temp, max_temp + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Fahrenheit - Extended")

def rtofs_currents(ax, data_file, bmap, key_ax, time_index, downsample_ratio=1):
    DEPTH = 0

    u = data_file.variables['u'][time_index, DEPTH]
    v = data_file.variables['v'][time_index, DEPTH]
    lats = data_file.variables['Latitude'][:]
    longs = data_file.variables['Longitude'][:]

    time = data_file.variables['MT']

    if VERBOSE > 0:
        print "Time Shape", time.shape
        print "Lats Shape", lats.shape
        print "Longs Shape", longs.shape
        print "U Shape", u.shape
        print "V Shape", v.shape

    DEPTH = 0

    def compute_average(array):
        avg = numpy.average(array)
        return numpy.nan if avg > 10**3 else avg

    def mask_array(array):
        array = numpy.ma.masked_where(array > 2, array) # Mask Really High Values
        array = numpy.ma.masked_array(array, numpy.isnan(array))
        return array

    downsample_ratio = 1

    currents_u = data_file.variables['u'][time_index, DEPTH]
    currents_v = data_file.variables['v'][time_index, DEPTH]
    lats = data_file.variables['Latitude'][:]
    longs = data_file.variables['Longitude'][:]

    # zoom
    #-------------------------------------------------------------------------
    """
    currents_u = crop_and_downsample(currents_u, downsample_ratio)
    currents_v = crop_and_downsample(currents_v, downsample_ratio)

    lats = crop_and_downsample(lats, downsample_ratio, False)
    longs = crop_and_downsample(longs, downsample_ratio, False)
    """

    currents_u = mask_array(currents_u)
    currents_v = mask_array(currents_v)


    x, y = bmap(longs, lats)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)

    overlay = bmap.quiver(x, y, currents_u, currents_v, ax=ax, color='black', units='inches',
                          scale=10.0, headwidth=2, headlength=3,
                          headaxislength=2.5, minlength=0.5, minshaft=.9)

    # Multiplying .5, 1, and 2 by .5144 is converting from knots to m/s
    #-------------------------------------------------------------------------
    quiverkey = key_ax.quiverkey(overlay, .95, .4, 0.5*.5144, "Extended -.5 knots", labelpos='S', labelcolor='white',
                                 color='white', labelsep=.5, coordinates='axes')
    quiverkey1 = key_ax.quiverkey(overlay, 3.75, .4, 1*.5144, "Extended - 1 knot", labelpos='S', labelcolor='white',
                                  color='white', labelsep=.5, coordinates='axes')
    quiverkey2 = key_ax.quiverkey(overlay, 6.5, .4, 2*.5144, "Extended - 2 knots", labelpos='S', labelcolor='white',
                                  color='white', labelsep=.5, coordinates='axes')
    key_ax.set_axis_off()

""" NAVY HYCOM PLOT FUNCTIONS"""
def hycom_sst(ax, data_file, bmap, key_ax, bottom=False, downsample_ratio=None):
    print "HYCOM SST"

    def celsius_to_fahrenheit(temp):
        return temp * 1.8 + 32
    temp_conversion = numpy.vectorize(celsius_to_fahrenheit)

    def convert_to_degrees_west(x):
        y = 180 - x; return -(y + 180)
    lon_conversion = numpy.vectorize(convert_to_degrees_west)

    """ We got to use the scale factor to convert the compressed data into floats """

    if bottom: # Use the same function for top and bottom woot woot
        level = 'water_temp_bottom'
        min_temp = MIN_TEMP_F_BOT
        max_temp = MAX_TEMP_F_BOT
        temps = data_file.variables[level][0][:][:].astype(numpy.float)
    else:
        level = 'water_temp'
        min_temp = MIN_TEMP_F_TOP
        max_temp = MAX_TEMP_F_TOP
        temps = data_file.variables[level][0][0].astype(numpy.float)

    temps = numpy.ma.masked_where(temps == -30000, temps) # mask values
    temps = numpy.ma.masked_array(temps, numpy.isnan(temps))

    temps = numpy.ma.array(temp_conversion(temps))

    print "Temps: ", temps.shape

    longs = data_file.variables['lon'][:]
    longs = numpy.ma.array(lon_conversion(longs))
    lats = data_file.variables['lat'][:]

    longs, lats = numpy.meshgrid(longs, lats)

    x, y = bmap(longs, lats)

    print "Lat: ", lats.shape
    print "Lon: ", longs.shape
    print "Temps: ", temps.shape
    print "x: ", x.shape
    print "y: ", y.shape

    contour_range = ((max_temp) - (min_temp))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS
    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_temp+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, temps, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
    #-------------------------------------------------------------------------
    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::10]    # we just want every 10th label
    float_labels = numpy.arange(min_temp, max_temp + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Fahrenheit - Extended")

def hycom_bot_temp(ax, data_file, bmap, key_ax):
    hycom_sst(ax, data_file, bmap, key_ax, bottom=True)

def hycom_ssc(ax, data_file, bmap, key_ax, downsample_ratio, bottom=False):
    def compute_average(array):
        avg = numpy.average(array)
        return numpy.nan if avg > 10**3 else avg

    def convert_to_degrees_west(x):
        y = 180 - x; return -(y + 180)
    lon_conversion = numpy.vectorize(convert_to_degrees_west)

    print "HYCOM SSC"

    # average nearby points to align grid, and add the edge column/row so it's the right size.
    #-------------------------------------------------------------------------

    if bottom: # Use the same function for top and bottom woot woot
        level_u = 'water_u_bottom'
        level_v = 'water_v_bottom'
        v = data_file.variables[level_v][0][:][:].astype(numpy.float)
        u = data_file.variables[level_u][0][:][:].astype(numpy.float)
    else:
        level_u = 'water_u'
        level_v = 'water_v'
        v = data_file.variables[level_v][0][0][:][:].astype(numpy.float)
        u = data_file.variables[level_u][0][0][:][:].astype(numpy.float)

    lats = data_file.variables['lat'][:]
    longs = data_file.variables['lon'][:]
    longs = numpy.ma.array(lon_conversion(longs))
    longs, lats = numpy.meshgrid(longs, lats)

    u = numpy.ma.masked_where(u == -30000, u) # mask values
    v = numpy.ma.masked_where(v == -30000, v) # mask values
    u = numpy.ma.masked_array(u , numpy.isnan(u))
    v = numpy.ma.masked_array(v , numpy.isnan(v))

    print "Downsample Ratio:", downsample_ratio

    u = crop_and_downsample(u, downsample_ratio, False)
    v = crop_and_downsample(v, downsample_ratio, False)

    longs = crop_and_downsample(longs, downsample_ratio, False)
    lats = crop_and_downsample(lats, downsample_ratio, False)


    x, y = bmap(longs, lats)
    #x, y = bmap(longs_zoomed, lats_zoomed)

    print "Lats : ", lats.shape
    print "Longs: ", longs.shape
    print "u : ", u.shape
    print "v : ", v.shape
    print "x : ", x.shape
    print "y : ", y.shape

    bmap.drawmapboundary(linewidth=0.0, ax=ax)

    overlay = bmap.quiver(x, y, u, v, ax=ax, color='black', units='inches',
                          scale=10.0, headwidth=2, headlength=3,
                          headaxislength=2.5, minlength=0.5, minshaft=.9)

    # Multiplying .5, 1, and 2 by .5144 is converting from knots to m/s
    #-------------------------------------------------------------------------
    # quiverkey = key_ax.quiverkey(overlay, .95, .4, 0.5*.5144, ".5 knots", labelpos='S', labelcolor='white',
    #                              color='white', labelsep=.5, coordinates='axes')
    # quiverkey1 = key_ax.quiverkey(overlay, 3.75, .4, 1*.5144, "1 knot", labelpos='S', labelcolor='white',
    #                               color='white', labelsep=.5, coordinates='axes')
    # quiverkey2 = key_ax.quiverkey(overlay, 6.5, .4, 2*.5144, "2 knots", labelpos='S', labelcolor='white',
    #                               color='white', labelsep=.5, coordinates='axes')
    textBox = pyplot.text(0, 0, "Extended - Right Click or Double Tap to View Values  ", withdash=False,
                          backgroundcolor='black', color='white', fontsize=17, )

    key_ax.set_axis_off()

def hycom_bot_cur(ax, data_file, bmap, key_ax):
    hycom_ssc(ax, data_file, bmap, key_ax, bottom=True)

def hycom_sur_sal(ax, data_file, bmap, key_ax, bottom=False, downsample_ratio=None ):
    def convert_to_degrees_west(x):
        y = 180 - x; return -(y + 180)
    lon_conversion = numpy.vectorize(convert_to_degrees_west)

    if bottom:
        level = 'salinity_bottom'
        min_salt = MIN_SAL_BOT
        max_salt = MAX_SAL_BOT
        salt = numpy.ma.array(data_file.variables[level][0][:][:])
    else:
        level = 'salinity'
        min_salt = MIN_SAL_TOP
        max_salt = MAX_SAL_TOP
        salt = numpy.ma.array(data_file.variables[level][0][0][:][:])

    longs = data_file.variables['lon'][:]
    lats = data_file.variables['lat'][:]
    longs = numpy.ma.array(lon_conversion(longs))
    longs, lats = numpy.meshgrid(longs, lats)
    x, y = bmap(longs, lats)

    # calculate and plot colored contours for salinity data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    contour_range = ((max_salt) - (min_salt))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS

    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_salt+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, salt, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
    cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
    cbar.ax.tick_params(labelsize=10)
    cbar.ax.xaxis.label.set_color('white')
    cbar.ax.xaxis.set_tick_params(labelcolor='white')

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::10]    # we just want every third label
    float_labels = numpy.arange(min_salt, max_salt + 0.01, contour_range_inc)[::10]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Extended - Salinity (PSU)")

def hycom_bot_sal(ax, data_file, bmap, key_ax):
    hycom_sur_sal(ax, data_file, bmap, key_ax, bottom=True)

def hycom_ssh(ax, data_file, bmap, key_ax, time_index, downsample_ratio=1):
    pass

""" HELPER FUNCTIONS """
def crop_and_downsample(source_array, downsample_ratio, average=True):
    ys, xs = source_array.shape

    cropped_array = source_array[:ys - (ys % int(downsample_ratio)), :xs - (xs % int(downsample_ratio))]
    if average:
        zoomed_array = scipy.nanmean(numpy.concatenate(
            [[cropped_array[i::downsample_ratio, j::downsample_ratio]
                                                     for i in range(downsample_ratio)]
                                                    for j in range(downsample_ratio)]), axis=0)
    else:
        zoomed_array = cropped_array[::downsample_ratio, ::downsample_ratio]
    return zoomed_array

# Wave files are in a different format, so they need a separate downsampling function
#-------------------------------------------------------------------------
def crop_and_downsample_wave(source_array, downsample_ratio, average=True):

    xs = source_array.shape[0]
    # Crop off anything extra: i.e. if downsample ratio is 10, and the height % 10 has a remainder of 1, chop off 1 from the height
    #-------------------------------------------------------------------------
    cropped_array = source_array[ :xs - (xs % int(downsample_ratio))]
    zoomed_array = cropped_array[::downsample_ratio, ::downsample_ratio]
    return zoomed_array

def get_modified_jet_colormap():
    modified_jet_cmap_dict = {
        'red': ((0., .15, .15),
                (0.05, .15, .15),
                (0.11, .1, .1),
                (0.2, 0, 0),
                (0.4, .3, .3),
                (0.5, .9, .9),
                (0.66, 1, 1),
                (0.89, 1, 1),
                (1, 0.5, 0.5)),
        'green': ((0., 0, 0),
                   (0.05, 0, 0),
                   (0.11, 0, 0),
                   (0.3, 0.4, 0.4),
                   (0.45, 1, 1),
                   (0.55, 1, 1),
                   (0.80, 0.2, 0.2),
                   (0.91, 0, 0),
                   (1, 0, 0)),
        'blue': ((0., 0.5, 0.5),
                  (0.05, 0.5, 0.5),
                  (0.11, .7, .7),
                  (0.34, 1, 1),
                  (0.5, .9, .9),
                  (0.75, 0, 0),
                  (1, 0, 0))
    }
    return colors.LinearSegmentedColormap('modified_jet', modified_jet_cmap_dict, 256)


def get_modified_jet_colormap_for_waves():
    modified_jet_cmap_dict = {
        'red': ((0., .0, .0),
                (0.3, .5, .5),
                (0.4, .7, .7),
                (0.45, .8, .8),
                (0.5, 1, 1),
                (0.55, 1, 1),
                (0.6, 1, 1),
                (0.65, 1, 1),
                (0.85, 1, 1),
                (1, 0.4, 0.4)),
        'green': ((0., .4, .4),
                   (0.2, 1, 1),
                   (0.5, 1, 1),
                   (0.65, .7, .7),
                   (0.8, .45, .45),
                   (0.92, 0.1, 0.1),
                   (0.99, .0, .0),
                   (1, 0, 0)),
        'blue': ((0., .4, .4),
                  (0.2, 1, 1),
                  (0.4, .3, .3),
                  (0.5, .7, .7),
                  (0.6, .2, .2),
                  (0.75, 0, 0),
                  (1, 0, 0))
    }
    return colors.LinearSegmentedColormap('modified_jet', modified_jet_cmap_dict, 256)
