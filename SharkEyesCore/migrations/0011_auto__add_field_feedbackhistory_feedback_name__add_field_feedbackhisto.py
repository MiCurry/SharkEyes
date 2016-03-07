# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'FeedbackHistory.feedback_name'
        db.add_column(u'SharkEyesCore_feedbackhistory', 'feedback_name',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=100, blank=True),
                      keep_default=False)

        # Adding field 'FeedbackHistory.feedback_phone'
        db.add_column(u'SharkEyesCore_feedbackhistory', 'feedback_phone',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=25, blank=True),
                      keep_default=False)

        # Adding field 'FeedbackHistory.feedback_email'
        db.add_column(u'SharkEyesCore_feedbackhistory', 'feedback_email',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=50, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'FeedbackHistory.feedback_name'
        db.delete_column(u'SharkEyesCore_feedbackhistory', 'feedback_name')

        # Deleting field 'FeedbackHistory.feedback_phone'
        db.delete_column(u'SharkEyesCore_feedbackhistory', 'feedback_phone')

        # Deleting field 'FeedbackHistory.feedback_email'
        db.delete_column(u'SharkEyesCore_feedbackhistory', 'feedback_email')


    models = {
        u'SharkEyesCore.feedbackhistory': {
            'Meta': {'object_name': 'FeedbackHistory'},
            'feedback_comments': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'feedback_email': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'feedback_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'feedback_phone': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
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