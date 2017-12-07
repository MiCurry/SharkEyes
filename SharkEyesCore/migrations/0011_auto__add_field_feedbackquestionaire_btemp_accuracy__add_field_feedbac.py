# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'FeedbackQuestionaire.btemp_accuracy'
        db.add_column(u'SharkEyesCore_feedbackquestionaire', 'btemp_accuracy',
                      self.gf('django.db.models.fields.CharField')(default=' ', max_length=4),
                      keep_default=False)

        # Adding field 'FeedbackQuestionaire.salt_accuracy'
        db.add_column(u'SharkEyesCore_feedbackquestionaire', 'salt_accuracy',
                      self.gf('django.db.models.fields.CharField')(default=' ', max_length=4),
                      keep_default=False)

        # Adding field 'FeedbackQuestionaire.bsalt_accuracy'
        db.add_column(u'SharkEyesCore_feedbackquestionaire', 'bsalt_accuracy',
                      self.gf('django.db.models.fields.CharField')(default=' ', max_length=4),
                      keep_default=False)

        # Adding field 'FeedbackQuestionaire.ssh_accuracy'
        db.add_column(u'SharkEyesCore_feedbackquestionaire', 'ssh_accuracy',
                      self.gf('django.db.models.fields.CharField')(default=' ', max_length=4),
                      keep_default=False)

        # Adding field 'FeedbackQuestionaire.port'
        db.add_column(u'SharkEyesCore_feedbackquestionaire', 'port',
                      self.gf('django.db.models.fields.CharField')(default=' ', max_length=2000),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'FeedbackQuestionaire.btemp_accuracy'
        db.delete_column(u'SharkEyesCore_feedbackquestionaire', 'btemp_accuracy')

        # Deleting field 'FeedbackQuestionaire.salt_accuracy'
        db.delete_column(u'SharkEyesCore_feedbackquestionaire', 'salt_accuracy')

        # Deleting field 'FeedbackQuestionaire.bsalt_accuracy'
        db.delete_column(u'SharkEyesCore_feedbackquestionaire', 'bsalt_accuracy')

        # Deleting field 'FeedbackQuestionaire.ssh_accuracy'
        db.delete_column(u'SharkEyesCore_feedbackquestionaire', 'ssh_accuracy')

        # Deleting field 'FeedbackQuestionaire.port'
        db.delete_column(u'SharkEyesCore_feedbackquestionaire', 'port')


    models = {
        u'SharkEyesCore.feedbackhistory': {
            'Meta': {'object_name': 'FeedbackHistory'},
            'feedback_comments': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'feedback_date': ('django.db.models.fields.CharField', [], {'default': 'datetime.datetime(2017, 12, 7, 0, 0)', 'max_length': '100'}),
            'feedback_email': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'feedback_name': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'feedback_phone': ('django.db.models.fields.CharField', [], {'max_length': '2000', 'blank': 'True'}),
            'feedback_title': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'SharkEyesCore.feedbackquestionaire': {
            'Meta': {'object_name': 'FeedbackQuestionaire'},
            'bsalt_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'btemp_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'port': ('django.db.models.fields.CharField', [], {'max_length': '2000'}),
            'salt_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'sent': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ss_currents_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'ss_temperature_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'ssh_accuracy': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
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