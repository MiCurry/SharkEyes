from django.shortcuts import render
from pl_plot.models import OverlayManager, OverlayDefinition
from dateutil import tz
import json
from django.db import connection
from django.db import IntegrityError, transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


#This is where we associate the Javascript variables (overlays, defs etc) with the Django objects from the database.
def home(request):
    # TODO: add 7 back in if you want to add in the wave period model
    # maybe not sure how wind is stored in the database...
    models = [1,3,4,6, 7]

    overlays_view_data = OverlayManager.get_next_few_days_of_tiled_overlays(models)
    print
    print
    print "overlay view data"
    print str(len(overlays_view_data))
    print overlays_view_data

    datetimes = overlays_view_data.values_list('applies_at_datetime', flat=True).distinct()
    print "datetimes"
    for d in datetimes:
        print "    " + str(d)

    context = {'overlays': overlays_view_data, 'defs': OverlayDefinition.objects.filter(is_base=True, id__in=models), 'times':datetimes }

    return render(request, 'index.html', context)

def oops(request):
    return render(request, 'oops.html')

def about(request):
    return render(request, 'about.html')

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
    feedback_name = json.loads(request.body)["name"]
    feedback_phone = json.loads(request.body)["phone"]
    feedback_email = json.loads(request.body)["email"]
    feedback_title = json.loads(request.body)["title"]
    feedback_comment = json.loads(request.body)["comment"]
    sent = False  #By default, a survey has Not yet been delivered

    try:
        #Establish DB Connection
        cursor = connection.cursor()
        #Execute SQL Query
        cursor.execute("""INSERT INTO SharkEyesCore_feedbackhistory (feedback_name, feedback_phone, feedback_email, feedback_title, feedback_comments, sent ) VALUES (%s, %s, %s);""", (feedback_name, feedback_phone, feedback_email, feedback_title, feedback_comment, sent))
        #Nothing needs to be returned
    except IntegrityError as e:
        print "Error Message: "
        print e.message
    return render(request, 'index.html')