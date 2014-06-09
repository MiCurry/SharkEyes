from django.db import models
from django.conf import settings
from celery import shared_task
from urlparse import urljoin
from django.utils import timezone
import urllib
import os
from uuid import uuid4
from django.conf import settings
from urlparse import urljoin
import urllib2
from defusedxml import ElementTree
from datetime import datetime, timedelta
from dateutil import parser, tz
from django.db.models.aggregates import Max
from django.db.models import Q
from operator import __or__ as OR

CATALOG_XML_NAME = "catalog.xml"
XML_NAMESPACE = "{http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0}"

# delete() - https://docs.djangoproject.com/en/1.7/ref/contrib/admin/actions/

def get_ingria_xml_tree():
    # todo: need to handle if the xml file isn't available
    xml_url = urljoin(settings.BASE_NETCDF_URL, CATALOG_XML_NAME)
    catalog_xml = urllib2.urlopen(xml_url)
    tree = ElementTree.parse(catalog_xml)
    return tree


def extract_modified_datetime_from_xml(elem):
    modified_datetime_string = elem.find(XML_NAMESPACE + 'date').text
    naive_datetime = parser.parse(modified_datetime_string)  # the date in the xml file follows iso standards, so we're gold.
    modified_datetime = timezone.make_aware(naive_datetime, timezone.utc)
    return modified_datetime


def is_new_file_to_download():
    three_days_ago = timezone.now().date()-timedelta(days=3)
    today = timezone.now().date()
    recent_netcdf_files = DataFile.objects.filter(model_date__range=[three_days_ago, today])

    # empty lists return false
    if not recent_netcdf_files:
        return True

    local_file_modified_datetime = recent_netcdf_files.latest('generated_datetime').generated_datetime

    tree = get_ingria_xml_tree()
    tags = tree.iter(XML_NAMESPACE + 'dataset')

    for elem in tags:
        if not elem.get('name').startswith('ocean_his'):
            continue
        server_file_modified_datetime = extract_modified_datetime_from_xml(elem)
        if server_file_modified_datetime <= local_file_modified_datetime:
            return False

    return True


@shared_task(name='pl_download.fetch_new_files')
# grabs file for next few days.
# todo make each file download in a separate task
def fetch_new_files():
    if not is_new_file_to_download():
       return False

    # download new file for next few days
    days_to_retrieve = [timezone.now().date(),
                        timezone.now().date()+timedelta(days=1),
                        timezone.now().date()+timedelta(days=2),
                        timezone.now().date()+timedelta(days=3)]
    files_to_retrieve = []
    tree = get_ingria_xml_tree()    # yes, we just did this to see if there's a new file. refactor later.
    tags = tree.iter(XML_NAMESPACE + 'dataset')

    for elem in tags:
        server_filename = elem.get('name')
        if not server_filename.startswith('ocean_his'):
            continue
        date_string_from_filename = server_filename.split('_')[-1]
        model_date = datetime.strptime(date_string_from_filename, "%d-%b-%Y.nc").date()   # this could fail, need error handling badly
        modified_datetime = extract_modified_datetime_from_xml(elem)

        for day_to_retrieve in days_to_retrieve:
            if model_date - day_to_retrieve == timedelta(days=0):
                files_to_retrieve.append((server_filename, model_date, modified_datetime))

    destination_directory = os.path.join(settings.MEDIA_ROOT, settings.NETCDF_STORAGE_DIR)

    for server_filename, model_date, modified_datetime in files_to_retrieve:
        url = urljoin(settings.BASE_NETCDF_URL, server_filename)
        local_filename = "{0}_{1}.nc".format(model_date, uuid4())
        urllib.urlretrieve(url=url, filename=os.path.join(destination_directory, local_filename)) # this also needs a try/catch

        datafile = DataFile(
            type='NCDF',
            download_datetime=timezone.now(),
            generated_datetime=modified_datetime,
            model_date=model_date,
            file=local_filename,
        )
        datafile.save()

    return True


class DataFileManager(models.Manager):
    @staticmethod
    def get_next_few_days_files_from_db():
        next_few_days_of_files = DataFile.objects.filter(
            model_date__gte=(timezone.now()-timedelta(hours=2)).date(),
            model_date__lte=(timezone.now()+timedelta(days=4)).date()
        )
        and_the_newest_for_each_model_date = next_few_days_of_files.values('model_date', 'type').annotate(
            newest_generation_time=Max('generated_datetime'))

        # if we expected a lot of new files, this would be bad (we're making a Q object for each file we want, basically)
        q_objects = []
        for filedata in and_the_newest_for_each_model_date:
            new_q = Q(type=filedata.get('type'), model_date=filedata.get('model_date'), generated_datetime=filedata.get('newest_generation_time'))
            q_objects.append(new_q)

        # assumes you're not redownloading the same file for the same model and generation dates.
        actual_datafile_objects = DataFile.objects.filter(reduce(OR, q_objects))
        return actual_datafile_objects


class DataFile(models.Model):
    DATA_FILE_TYPES = (
        ('NCDF', "NetCDF"),
    )
    type = models.CharField(max_length=10, choices=DATA_FILE_TYPES, default='NCDF')
    download_datetime = models.DateTimeField()
    generated_datetime = models.DateTimeField()
    model_date = models.DateField()
    file = models.FileField(upload_to=settings.NETCDF_STORAGE_DIR, null=True)
