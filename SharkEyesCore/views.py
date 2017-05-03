from django.shortcuts import render
from pl_plot.models import OverlayManager, OverlayDefinition
from dateutil import tz
import json
from django.db import connection
from django.db import IntegrityError, transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import HttpResponse

#This is where we associate the Javascript variables (overlays, defs etc) with the Django objects from the database.
def home(request):
    #This determines which models are ran
    #1 = SST, 2 = Salinity, 3 = Currents, 4 = Wave Height, 5 = Winds, 6 = Wave Direction
    #-------------------------------------------------------------------------
    models = [1,2,7,3,4,5,6]
    overlays_view_data = OverlayManager.get_next_few_days_of_tiled_overlays(models)
    datetimes = overlays_view_data.values_list('applies_at_datetime', flat=True).distinct().order_by('applies_at_datetime')
    context = {'overlays': overlays_view_data, 'defs': OverlayDefinition.objects.filter(is_base=True, id__in=models), 'times':datetimes }
    return render(request, 'index.html', context)

def oops(request):
    return render(request, 'oops.html')

def about(request):
    return render(request, 'about.html')

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