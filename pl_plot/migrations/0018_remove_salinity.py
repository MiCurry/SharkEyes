# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        # Note: Don't use "from appname.models import ModelName". 
        # Use orm.ModelName to refer to models in this application,
        # and orm['appname.ModelName'] for models in other applications.
        salinity = orm.OverlayDefinition.objects.get(pk=2)
        salinity.is_base = False
        salinity.save()

    def backwards(self, orm):
        salinity = orm.OverlayDefinition.objects.get(pk=2)
        salinity.is_base = False
        salinity.save()

    models = {
        u'pl_plot.overlay': {
            'Meta': {'object_name': 'Overlay'},
            'applies_at_datetime': ('django.db.models.fields.DateTimeField', [], {}),
            'created_datetime': ('django.db.models.fields.DateTimeField', [], {}),
            'definition': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['pl_plot.OverlayDefinition']"}),
            'file': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_tiled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'key': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True'}),
            'tile_dir': ('django.db.models.fields.CharField', [], {'max_length': '240', 'null': 'True'}),
            'zoom_levels': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True'})
        },
        u'pl_plot.overlaydefinition': {
            'Meta': {'object_name': 'OverlayDefinition'},
            'display_name_long': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '240'}),
            'display_name_short': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'function_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_base': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '4'})
        },
        u'pl_plot.parameters': {
            'Meta': {'object_name': 'Parameters'},
            'definition': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['pl_plot.OverlayDefinition']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '240'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '240'})
        }
    }

    complete_apps = ['pl_plot']
    symmetrical = True
