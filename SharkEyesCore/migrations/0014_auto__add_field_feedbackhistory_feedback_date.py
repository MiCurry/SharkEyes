# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'FeedbackHistory.feedback_date'
        db.add_column(u'SharkEyesCore_feedbackhistory', 'feedback_date',
                      self.gf('django.db.models.fields.CharField')(default=datetime.datetime(2016, 3, 5, 0, 0), max_length=100),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'FeedbackHistory.feedback_date'
        db.delete_column(u'SharkEyesCore_feedbackhistory', 'feedback_date')


    models = {
        u'SharkEyesCore.feedbackhistory': {
            'Meta': {'object_name': 'FeedbackHistory'},
            'feedback_comments': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'feedback_date': ('django.db.models.fields.CharField', [], {'default': 'datetime.datetime(2016, 3, 5, 0, 0)', 'max_length': '100'}),
            'feedback_email': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'feedback_name': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'feedback_phone': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'feedback_title': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'SharkEyesCore.feedbackquestionaire': {
            'Meta': {'object_name': 'FeedbackQuestionaire'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ss_currents_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'ss_temperature_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'usage_comment': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'usage_comparison': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'usage_device': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'usage_frequency': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'usage_likes': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'usage_location': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'usage_model_suggestion': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'usage_suggestion': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'wave_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'wind_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'})
        }
    }

    complete_apps = ['SharkEyesCore']