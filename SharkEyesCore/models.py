from django.db import models
from django.core.mail import send_mail
from django.utils import timezone

# SharkEyesCore\models.py
# This file sets up FeedBackHistory and the FeedBackQuestion classes for the site.

# This import is so that we can access the email recipients from the settings_local file for whatever server we are on
from django.conf import settings

class FeedbackHistory (models.Model):
    feedback_title = models.CharField(max_length=2000)
    feedback_comments = models.CharField(max_length=2000)
    sent = models.BooleanField(default=False)
    feedback_name = models.CharField(max_length=2000, blank=True)
    feedback_email = models.CharField(max_length=2000, blank=True)
    feedback_phone = models.CharField(max_length=2000, blank=True)
    feedback_date = models.CharField(max_length=100, default=timezone.now())

    @classmethod
    def send_feedback_forms(cls):
        # Only get the items that have not yet been sent.
        # This does not have error handling in case an email fails to send.
        feedback_items = FeedbackHistory.objects.filter(sent=False)

        # Based on which server we are on, determine who to send the feedback to. Comments on
        # Production go to Flaxen, comments on Staging go to Bethany Carlson or other developer for
        # testing purposes.
        recipient = settings.RECIPIENT

        for each in feedback_items:
            # Use the Django framework's send_mail function to create the email
            # pattern Subject, Body, From, To(as a list)
            #TODO set this to be sent to Flaxen
            send_mail('[Seacast Feedback] ' + each.feedback_title, '\nname: '+ each.feedback_name+ '\nemail: '+ each.feedback_email+ '\nphone: '+ each.feedback_phone+ '\ncomments: '+ each.feedback_comments, 'seacast.mail@gmail.com',
                [recipient], fail_silently=False)
            each.sent = True
            each.save()

class FeedbackQuestionaire (models.Model):
    ACCURACY_TYPE = (
        ('A', "Accurate"),
        ('NA', "Not Accurate"),
        ('U', "Unsure"),
        ('', ""),
    )
    DEVICE_TYPE = (
        ('C', "Computer"),
        ('SM', "Smartphone"),
        ('T', "Tablet"),
        ('', ""),
    )
    FREQUENCY_TYPES = (
        ('1', "Once"),
        ('2-5', "2 - 5 times"),
        ('6-10', "6 - 10 times"),
        ('10+', "more than 10 times"),
        ('', ""),
    )
    LOCATION_TYPES = (
        ('S', 'At Sea'),
        ('L', 'On Land'),
        ('', ""),
    )

    #Where did you user it?
    usage_location=  models.CharField(max_length=4, choices=LOCATION_TYPES)
    #How many times did you use it?
    usage_frequency = models.CharField(max_length=4, choices=FREQUENCY_TYPES)
    #What did you use?
    usage_device = models.CharField(max_length=4, choices=DEVICE_TYPE)
    #General Comments about the experience?
    usage_comment = models.CharField(max_length=2000)
    #sea surface temperature accuracy?
    ss_temperature_accuracy = models.CharField(max_length=4, choices=ACCURACY_TYPE)
    #surface currents accuracy
    ss_currents_accuracy = models.CharField(max_length=4, choices=ACCURACY_TYPE)
    #wave plot accuracy
    wave_accuracy = models.CharField(max_length=4, choices=ACCURACY_TYPE)
    #wind plot accuracy
    wind_accuracy = models.CharField(max_length=4, choices=ACCURACY_TYPE)
    #How does seacast.org compare with other forecasting system?
    usage_comparison = models.CharField(max_length=2000)
    #What are three things you like about seacst.org
    usage_likes = models.CharField(max_length=2000)
    #What are the first three things you would change?
    usage_suggestion = models.CharField(max_length=2000)
    #What other ocean condition would you like to see?
    usage_model_suggestion = models.CharField(max_length=2000)
    # Has this survey been delivered to Flaxen by email yet?
    sent = models.BooleanField(default=False)

    @classmethod
    def send_feedback_survey(cls):
        feedback_items = FeedbackQuestionaire.objects.filter(sent=False)
        # Here's some helpful links for list comprehensions in Python: http://stackoverflow.com/questions/14864300/how-to-access-tuple-elements-in-a-nested-list
        # http://stackoverflow.com/questions/2191699/find-an-element-in-a-list-of-tuples
        for each in feedback_items:
            loc = [item for item in each.LOCATION_TYPES if str(each.usage_location) in item]
            location = str([item[1] for item in loc])

            freq = [item for item in each.FREQUENCY_TYPES if str(each.usage_frequency) in item]
            frequency = str( [item[1] for item in freq])

            dev = [item for item in each.DEVICE_TYPE if str(each.usage_device) in item]
            device = str([item[1] for item in dev])

            sst = [item for item in each.ACCURACY_TYPE if str(each.ss_temperature_accuracy) in item]
            sst_accuracy = str([item[1] for item in sst])

            curr = [item for item in each.ACCURACY_TYPE if str(each.ss_currents_accuracy) in item]
            currents_accuracy = str([item[1] for item in curr])

            wind = [item for item in each.ACCURACY_TYPE if str(each.wind_accuracy) in item]
            wind_accuracy = str([item[1] for item in wind])

            wave = [item for item in each.ACCURACY_TYPE if str(each.wave_accuracy) in item]
            wave_accuracy = str([item[1] for item in wave])

            recipient = settings.RECIPIENT

            # Use the Django framework's send_mail function to create the email
            # pattern Subject, Body, From, To(as a list)
            send_mail('[Seacast Survey] ', '\nLocation: '+location+ '\nUsage Frequency: '+ str(frequency) +
                    '\nDevice: '+ device + '\nGeneral Comments: ' + str(each.usage_comment) +
                    '\nSST accuracy: ' + sst_accuracy + '\nCurrents accuracy: ' + currents_accuracy
                      + '\nWind accuracy: ' + wind_accuracy + '\nWave accuracy: ' + wave_accuracy
                      + '\nHow Seacast compares to other forecasting systems: '+ str(each.usage_comparison)
                      + '\nWhat is liked about Seacast: ' + str(each.usage_likes)
                      + '\nSuggestions to change: ' + str(each.usage_suggestion)
                      + '\nOther information to incorporate: ' + str(each.usage_model_suggestion) ,
                      'seacast.mail@gmail.com',  [recipient], fail_silently=False)
            each.sent = True
            each.save()

