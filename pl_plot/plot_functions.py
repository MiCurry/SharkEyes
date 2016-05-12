import math
import os
import sys
from datetime import datetime, timedelta

import numpy
import scipy
from scipy import ndimage
from scipy.interpolate import interp1d
from matplotlib import pyplot, colors, image
from mpl_toolkits.basemap import Basemap
from PIL import Image
from pydap.client import open_url

from django.conf import settings

numpy.set_printoptions(threshold=numpy.inf) # This is helpful for testing purposes:
# it sets print options so that when you print a large array, it doesn't get truncated in the middle
# and you can see each element of the array.


# When you add a new function, add it as a new function definition to fixtures/initial_data.json

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

#
def get_rho_mask(data_file):
    rho_mask = numpy.logical_not(data_file.variables['mask_rho'][:])
    #rho_mask[207:221, 133:135] = 1
    #rho_mask[201:202, 133:135] = 1
    return rho_mask

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
    all_day = data_file.variables['PERPW_surface'][:, :, :]

    # Mask all of the data points that are "nan" (not a number) in the data file; these represent land
    period_masked = np.ma.masked_array(all_day[forecast_index][:, :],np.isnan(all_day[forecast_index][:,:]))

    #This is the average wave period for the day
    mean_val = np.mean(period_masked)
    #The mean val is calculated to a large number of decimal places. This rounds it to two.
    mean_val = round(mean_val, 2)

    #This is the maximum wave period value for the day
    max_val = np.amax(period_masked)
    #This rounds the max value just like the average
    max_val = round(max_val, 2)

    #textBox is a hack that makes an unused Cartesian plot with a label over the top of it. This label has the wave period data.
    #the spacing is purposefully there to have a nice readable label. The black background helps to mask the figure behind the label.
    textBox = pyplot.text(0, 0,"       Wave period average and maximum values ""\n" "Average: " + str(mean_val) + " seconds " "  -  "" Maximum: " + str(max_val) + " seconds", withdash=False, backgroundcolor='black', color='white')

    # Print a half-meter arrow, with a legend saying this is half a meter
    quiverkey1 = key_ax.quiverkey(overlay, 1, .4, 0.5,
                                  "Wave Height: %.1f ft" % half,
                                  labelpos='S',
                                  labelcolor='white',
                                  color='white',
                                  labelsep=.5,
                                  coordinates='axes')
    quiverkey2 = key_ax.quiverkey(overlay, 4, .4, 1.0,
                                  "%.1f ft" % one,
                                  labelpos='S',
                                  labelcolor='white',
                                  color='white',
                                  labelsep=.5,
                                  coordinates='axes')
    quiverkey3 = key_ax.quiverkey(overlay, 5.4, .4, 2.0,
                                  "%.1f ft" % two,
                                  labelpos='S',
                                  labelcolor='white',
                                  color='white',
                                  labelsep=.5,
                                  coordinates='axes')

    quiverkey4 = key_ax.quiverkey(overlay, 6.8, .4, 3.0,
                                  "%.1f ft" % three,
                                  labelpos='S',
                                  labelcolor='white',
                                  color='white',
                                  labelsep=.5,
                                  coordinates='axes')

    quiverkey5 = key_ax.quiverkey(overlay, 8.5, .4, 5.0, "%.1f ft" % five,
                                  labelpos='S',
                                  labelcolor='white',
                                  color='white',
                                  labelsep=.5,
                                  coordinates='axes')

    quiverkey6 = key_ax.quiverkey(overlay, 10.3, .4, 6.0,
                                  "%.1f ft" % six,
                                  labelpos='S',
                                  labelcolor='white',
                                  color='white',
                                  labelsep=.5,
                                  coordinates='axes')

    key_ax.set_axis_off()


# Wave Model Data Information:
# Wave Data comes in 3D arrays (number of forecasts, latitude, longitude)
# As of right now (March 15) there are 85 forecasts in each netCDF file from 12 pm onward by the hour
# Wave Heights are measured in meters
# Wave direction is measured in Degrees, where 360 means waves are coming from the north, traveling southward.
# 350 would mean waves are traveling from the north-west, headed south-east.
# Data points over 1000 usually mark land
def wave_height_function(ax, data_file, bmap, key_ax, forecast_index, downsample_ratio):

     # Need to convert each point from meters to feet
     def meters_to_feet(height):
        return height * METERS_TO_FEET

     vectorized_conversion = numpy.vectorize(meters_to_feet)

     #grab longitude and latitude from netCDF file if we are using the old OuterGrid format which was lower resolution
     #longs = data_file.variables['longitude'][:]
     #lats = data_file.variables['latitude'][:]

     # If we are using the file with merged fields (both high-res and low-res data) provided
     # by Tuba and Gabriel
     longs = [item for sublist in data_file.variables['longitude'][:1] for item in sublist]
     lats = data_file.variables['latitude'][:, 0]

     #get the wave height data from netCDF file
     all_day = data_file.variables['HTSGW_surface'][:, :, :]

     #convert/mesh the latitude and longitude data into 2D arrays to be used by contourf below
     x,y = numpy.meshgrid(longs,lats)

     #obtain all forecasts
     #heights is measured in meters, if a data point is over 1000 meters it is either not valid or it represents land
     #so we are masking all data over 1000
     #heights = numpy.ma.masked_greater(all_day[forecast_index][:][:], 1000)

     heights_masked = numpy.ma.masked_array(all_day[forecast_index][:, :],numpy.isnan(all_day[forecast_index][:,:]))

     # Need to convert each height given in meters into FEET
     heights = vectorized_conversion(heights_masked)

     #get the max and min period wave period for the day: used to set color contours
     #min_period = int(math.floor(numpy.amin(heights))) # This was used when we determined min period for a certain day

     #Min period is now in feet
     min_period = MIN_WAVE_HEIGHT*METERS_TO_FEET

     #max_period = int(math.ceil(numpy.amax(numpy.ma.masked_greater(heights, 1000))))
     #max_period = int(math.ceil(numpy.amax(heights)))
     #Max period is now in feet
     max_period = MAX_WAVE_HEIGHT*METERS_TO_FEET

     #Allocates colors to the data by setting the range of the data and by setting color increments
     contour_range = max_period - min_period
     contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS_FOR_WAVES

     #Now the contour range
     color_levels = []
     for i in xrange(NUM_COLOR_LEVELS_FOR_WAVES+1):
         color_levels.append(min_period+1 + i * contour_range_inc)

     #Fill the contours with the colors
     overlay = bmap.contourf(x, y, heights, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap_for_waves())

     #Create the color bar
     cbar = pyplot.colorbar(overlay, orientation='horizontal', cax=key_ax)
     cbar.ax.tick_params(labelsize=10)
     cbar.ax.xaxis.label.set_color('white')
     cbar.ax.xaxis.set_tick_params(labelcolor='white')

     #todo DIVISION by ZERO sometimes causes a warning but it doesn't seem to cause any problems
     locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS_FOR_WAVES))[::10]    # we just want every 10th label
     float_labels = numpy.arange(min_period, max_period + 0.01, contour_range_inc)[::10]

     labels = ["%.1f" % num for num in float_labels]
     cbar.ax.xaxis.set_ticks(locations)
     cbar.ax.xaxis.set_ticklabels(labels)
     cbar.set_label("Wave Height (feet)")

# Plot the period of the waves as daily average and maximum integer values.
def wave_period_function(data_file, forecast_index):
     #This is a hopefully temporary solution to implementing wave period. This replaces the colorbar key that used to
     #exist for the now removed wave period color map. This makes an image with the wave period values that is displayed in the
     #same spot as a colormap key. When make_wave_watch_plot() is called with 7 this figure is automatically named and placed in the
     #/media/keys folder.

     #get the wave period data from a netCDF file
     all_day = data_file.variables['PERPW_surface'][:, :, :]

     # Mask all of the data points that are "nan" (not a number) in the data file; these represent land
     period_masked = numpy.ma.masked_array(all_day[forecast_index][:, :],numpy.isnan(all_day[forecast_index][:,:]))

     #This is the average wave period for the day
     mean_val = numpy.mean(period_masked)
     #The mean val is calculated to a large number of decimal places. This rounds it to two.
     mean_val = round(mean_val, 2)

     #This is the maximum wave period value for the day
     max_val = numpy.amax(period_masked)
     #This rounds the max value just like the average
     max_val = round(max_val, 2)

     #textBox is a hack that makes an unused Cartesian plot with a label over the top of it. This label has the wave period data.
     #the spacing is purposefully there to have a nice readable label. The black background helps to mask the figure behind the label.
     textBox = pyplot.text(0, 0,"       Wave period average and maximum values ""\n" "Average: " + str(mean_val) + " seconds " "  -  "" Maximum: " + str(max_val) + " seconds", withdash=False, backgroundcolor='black', color='white')

def sst_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    def celsius_to_fahrenheit(temp):
        return temp * 1.8 + 32
    vectorized_conversion = numpy.vectorize(celsius_to_fahrenheit)

    # temperature has dimensions ('ocean_time', 's_rho', 'eta_rho', 'xi_rho')
    # s_rho corresponds to layers, of which there are 30, so we take the top one.
    surface_temp = numpy.ma.array(vectorized_conversion(data_file.variables['temp'][time_index][29]), mask=get_rho_mask(data_file))
        
    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]

    #get the max and min temps for the daytem
    all_day = data_file.variables['temp'][:, 29, :, :]
    min_temp = int(math.floor(celsius_to_fahrenheit(numpy.amin(all_day))))
    max_temp = int(math.ceil(celsius_to_fahrenheit(numpy.amax(numpy.ma.masked_greater(all_day, 1000)))))
    
    x, y = bmap(longs, lats)

    # calculate and plot colored contours for TEMPERATURE data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    contour_range = ((max_temp - 1) - (min_temp + 1))
    contour_range_inc = float(contour_range)/NUM_COLOR_LEVELS
    color_levels = []
    for i in xrange(NUM_COLOR_LEVELS+1):
        color_levels.append(min_temp+1 + i * contour_range_inc)

    bmap.drawmapboundary(linewidth=0.0, ax=ax)
    overlay = bmap.contourf(x, y, surface_temp, color_levels, ax=ax, extend='both', cmap=get_modified_jet_colormap())

    # add colorbar.
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


# We are not using the Salt model at this time.
def salt_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    # salt has dimensions ('ocean_time', 's_rho', 'eta_rho', 'xi_rho')
    # s_rho corresponds to layers, of which there are 30, so we take the top one.
    surface_salt = numpy.ma.array(data_file.variables['salt'][time_index][29], mask=get_rho_mask(data_file))

    longs = data_file.variables['lon_rho'][:]
    lats = data_file.variables['lat_rho'][:]

    #get the max and min salinity for the day
    all_day = data_file.variables['salt'][:, 29, :, :]
    min_salt = int(math.floor(numpy.amin(all_day)))
    max_salt = int(math.ceil(numpy.amax(numpy.ma.masked_greater(all_day, 1000))))

    x, y = bmap(longs, lats)

    # calculate and plot colored contours for salinity data
    # 21 levels, range from one over min to one under max, as the colorbar caps each have their color and will color
    # out of bounds data with their color.
    contour_range = ((max_salt - 1) - (min_salt + 1))
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

    locations = numpy.arange(0, 1.01, 1.0/(NUM_COLOR_LEVELS))[::3]    # we just want every third label
    float_labels = numpy.arange(min_salt, max_salt + 0.01, contour_range_inc)[::3]
    labels = ["%.1f" % num for num in float_labels]
    cbar.ax.xaxis.set_ticks(locations)
    cbar.ax.xaxis.set_ticklabels(labels)
    cbar.set_label("Salinity (PSU)")


def currents_function(ax, data_file, bmap, key_ax, time_index, downsample_ratio):
    def compute_average(array):
        avg = numpy.average(array)
        return numpy.nan if avg > 10**3 else avg

    print "Currents Downsample Ratio:", downsample_ratio

    currents_u = data_file.variables['u'][time_index][29]
    currents_v = data_file.variables['v'][time_index][29]
    rho_mask = get_rho_mask(data_file)

    # average nearby points to align grid, and add the edge column/row so it's the right size.
    right_column = currents_u[:, -1:]
    currents_u_adjusted = ndimage.generic_filter(scipy.hstack((currents_u, right_column)),
                                                 compute_average, footprint=[[1], [1]], mode='reflect')
    bottom_row = currents_v[-1:, :]
    currents_v_adjusted = ndimage.generic_filter(scipy.vstack((currents_v, bottom_row)),
                                                 compute_average, footprint=[[1], [1]], mode='reflect')

    # zoom
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

    # TODO I assume this .5144 value is based on converting meters-per-second to Knots.
    # TODO Would be good to verify, and set it as a constant.
    quiverkey = key_ax.quiverkey(overlay, .95, .4, 0.5*.5144, ".5 knots", labelpos='S', labelcolor='white',
                                 color='white', labelsep=.5, coordinates='axes')
    quiverkey1 = key_ax.quiverkey(overlay, 3.75, .4, 1*.5144, "1 knot", labelpos='S', labelcolor='white',
                                  color='white', labelsep=.5, coordinates='axes')
    quiverkey2 = key_ax.quiverkey(overlay, 6.5, .4, 2*.5144, "2 knots", labelpos='S', labelcolor='white',
                                  color='white', labelsep=.5, coordinates='axes')
    key_ax.set_axis_off()


# Wind_functions
# The NAM's model are produced every 3 hours instead of every 4 hours like the rest
# of our models. Because of that we need to interpolate them as seen below.
def wind_function(ax, data_file, bmap, time_index, downsample_ratio, interp):
    start_time = datetime.strptime(time.units, "Hour since %Y-%m-%dT%H:%M:%SZ") #Not used currently

    print "CREATING A WIND PLOT"
    print "DOWNSAMPLERATIO = ", downsample_ratio, "Time Index =", time_index

    # Set up lat and lon variables from the provided file
    tmp = numpy.loadtxt('/opt/sharkeyes/src/latlon.g218')
    lat = numpy.reshape(tmp[:, 2], [614,428])
    lon = numpy.reshape(tmp[:, 3], [614,428])
    x, y = bmap(lon, lat)
    for i in range(0, len(lon)):
        lon[i] = -lon[i]

    var_u = 'u-component_of_wind_height_above_ground'
    var_v = 'v-component_of_wind_height_above_ground'
    landMask = 'Land_cover_0__sea_1__land_surface'

    data_file = open_url(settings.WIND_URL)

    if(interp == "TRUE"):
        # Grab all the times for interpolating
        wind_u = data_file[var_u][:, 0, :, :] # All times of u
        wind_v = data_file[var_v][:, 0, :, :] # All times of v
    else:
        # Don't grab all the times for when we don't interpolate
        wind_u = data_file[var_u][time_index+104, 0, :, :]
        wind_v = data_file[var_v][time_index+104, 0, :, :]

    # Remove the surface height dimension (Its only 1-Demensional)
    wind_u = numpy.squeeze(wind_u) # Removes The Surface Height Dimension
    wind_v = numpy.squeeze(wind_v) # Ditto

    if(0): # Debug
        print "Wind_u.shape", wind_u.shape
        print "Wind_v.shape", wind_v.shape

    #TODO: This can be cleaned up
    if(interp == "TURE"):
        print "INTERPOLATING"

        time = data_file['time']
        ts1 = [], ts2 = []

        wind_u = numpy.reshape(wind_u, (147, 428, 614))
        wind_v = numpy.reshape(wind_v, (147, 428, 614))

        size = time.shape[0]

        # Create two different time stamps used for interpolating
        ts2 = numpy.arange(0, size * 3, 4) # One for every 4 hours
        ts1 = numpy.arange(0, size * 3, 3) # One for every 3  hours

        if(0): # Debug
            print "Wind_u:", wind_u.shape
            print "Wind_v:", wind_v.shape
            print "time.shape:", time.shape
            print "ts1.shape:", ts1.shape[0]
            print "ts2.shape:", ts2.shape[0]

        wind_u_int = numpy.empty([110, 427, 613]) # Array to be filled
        wind_v_int = numpy.empty([110, 427, 613]) # Ditto


        # Loop through each lat and long and intpolate each value from time stamp ts1
        # to ts2.  (ie from every 3rd hours to every 4hrs between the NAMS model time) see help(numpy.interp)
        for i in range(0, 427):
            for j in range(0, 613):
                wind_u_int[:,i,j] = numpy.interp(ts2, ts1, wind_u[:,i,j])
                wind_v_int[:,i,j] = numpy.interp(ts2, ts1, wind_v[:,i,j])

    if(interp == "TRUE"):
        wind_u = wind_u_int[time_index+104, :, :] #Pull out the time
        wind_v = wind_v_int[time_index+104, :, :] #Pull out the time
    else:
        wind_u = wind_u[time_index+104, :, :] #Pull out the time
        wind_v = wind_v[time_index+104, :, :] #Pull out the time

    wind_u = numpy.squeeze(wind_u) # Squeeze out the time
    wind_v = numpy.squeeze(wind_v) # Squeeze out the time

    wind_u = numpy.reshape(wind_u, (614, 428))
    wind_v = numpy.reshape(wind_v, (614, 428))

    if downsample_ratio == 1:
        length = 3
    elif downsample_ratio == 5:
        length = 7

    if(0): # Debug
        print "After pulling time"
        print "Wind_u:", wind_u.shape
        print "Wind_v:", wind_v.shape
        print "Lat:", lat.shape
        print "Lon:",  lon.shape
        print "x:", x.shape
        print "y:", y.shape

    bmap.barbs(x[::downsample_ratio, ::downsample_ratio],
               y[::downsample_ratio, ::downsample_ratio],
               wind_u[::downsample_ratio, ::downsample_ratio],
               wind_v[::downsample_ratio, ::downsample_ratio],
               ax=ax,
               length=length)


def crop_and_downsample(source_array, downsample_ratio, average=True):
    ys, xs = source_array.shape
    print "shape is ", source_array.shape
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
def crop_and_downsample_wave(source_array, downsample_ratio, average=True):

    xs = source_array.shape[0]

    # Crop off anything extra: i.e. if downsample ratio is 10, and the height % 10 has a remainder of 1, chop off 1 from the height
    cropped_array = source_array[ :xs - (xs % int(downsample_ratio))]
    #if average:
    #   zoomed_array = scipy.nanmean(numpy.concatenate(
    #    [[cropped_array[i::downsample_ratio, j::downsample_ratio]
    #         for i in range(downsample_ratio)]
    #             for j in range(downsample_ratio)]), axis=0)
    #  else:
    zoomed_array = cropped_array[::downsample_ratio, ::downsample_ratio]
    return zoomed_array
    #return source_array


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
