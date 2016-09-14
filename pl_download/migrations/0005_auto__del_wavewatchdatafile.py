# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'WaveWatchDataFile'
        db.delete_table(u'pl_download_wavewatchdatafile')


    def backwards(self, orm):
        # Adding model 'WaveWatchDataFile'
        db.create_table(u'pl_download_wavewatchdatafile', (
            ('file', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True)),
            ('download_datetime', self.gf('django.db.models.fields.DateTimeField')()),
            ('type', self.gf('django.db.models.fields.CharField')(default='NCDF', max_length=10)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('generated_datetime', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal(u'pl_download', ['WaveWatchDataFile'])


    models = {
        u'pl_download.datafile': {
            'Meta': {'object_name': 'DataFile'},
            'download_datetime': ('django.db.models.fields.DateTimeField', [], {}),
            'file': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True'}),
            'generated_datetime': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model_date': ('django.db.models.fields.DateField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'default': "'NCDF'", 'max_length': '10'})
        }
    }

    complete_apps = ['pl_download']