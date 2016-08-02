# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'Wave_Watch_Overlay'
        db.delete_table(u'pl_plot_wave_watch_overlay')

        # Adding field 'OverlayDefinition.forecast'
        db.add_column(u'pl_plot_overlaydefinition', 'forecast',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)


    def backwards(self, orm):
        # Adding model 'Wave_Watch_Overlay'
        db.create_table(u'pl_plot_wave_watch_overlay', (
            ('definition', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['pl_plot.OverlayDefinition'])),
            ('key', self.gf('django.db.models.fields.files.ImageField')(max_length=100, null=True)),
            ('created_datetime', self.gf('django.db.models.fields.DateTimeField')()),
            ('file', self.gf('django.db.models.fields.files.ImageField')(max_length=500, null=True)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal(u'pl_plot', ['Wave_Watch_Overlay'])

        # Deleting field 'OverlayDefinition.forecast'
        db.delete_column(u'pl_plot_overlaydefinition', 'forecast')


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
            'forecast': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
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