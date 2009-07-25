import datetime
import re

from google.appengine.ext import db
from google.appengine.tools import bulkloader

import data

class OriginLoader(bulkloader.Loader):
  def __init__(self):
    bulkloader.Loader.__init__(self, 'Origin',
      [
        ('tag', str),
        ('api_url', str),
        ('max_id', long),
        ('count', long),
      ])
  def generate_key(self, i, values):
    return values[1] + '#' + values[0]

class OriginExporter(bulkloader.Exporter):
  def __init__(self):
    bulkloader.Exporter.__init__(self, 'Origin',
      [
        ('tag',     str, None),
        ('api_url', str, None),
        ('max_id',  str, None),
        ('count',   str, None),
      ])


class DestinationLoader(bulkloader.Loader):
  def __init__(self):
    bulkloader.Loader.__init__(self, 'Destination',
      [
        ('api_url', str),
        ('username', str),
        ('password', str),
        ('consumer_key', str),
        ('consumer_secret', str),
        ('oauth_token', str),
        ('oauth_token_secret', str),
      ])
  def generate_key(self, i, values):
    return values[1] + '#' + values[0]

class DestinationExporter(bulkloader.Exporter):
  def __init__(self):
    bulkloader.Exporter.__init__(self, 'Destination',
      [
        ('api_url',  str, None),
        ('username', str, None),
        ('password', str, None),
        ('consumer_key', str, None),
        ('consumer_secret', str, None),
        ('oauth_token', str, None),
        ('oauth_token_secret', str, None),
      ])


class SiteLoader(bulkloader.Loader):
  def __init__(self):
    bulkloader.Loader.__init__(self, 'Site',
      [
        ('host', load_string),
        ('name', load_string),
      ])
  def generate_key(self, i, values):
    return values[0]

class SiteExporter(bulkloader.Exporter):
  def __init__(self):
    bulkloader.Exporter.__init__(self, 'Site',
      [
        ('host', export_string, None),
        ('name', export_string, None),
      ])


class ArticleLoader(bulkloader.Loader):
  def __init__(self):
    bulkloader.Loader.__init__(self, 'Article',
      [
        ('url',    load_string),
        ('author', load_optional_string),
        ('title',  load_optional_string),
        ('date',   load_optional_date),
      ])
  def generate_key(self, i, values):
    return values[0]
  def create_entity(self, values, key_name=None, parent=None):
    url = values[0]
    host, path = re.match(r'(?i)^http://([^/]+)(/?.*)', url).groups()
    return bulkloader.Loader.create_entity(self, values, key_name, data.Site.get_by_key_name(host))

class ArticleExporter(bulkloader.Exporter):
  def __init__(self):
    bulkloader.Exporter.__init__(self, 'Article',
      [
        ('url',    export_string, None),
        ('author', export_optional_string, None),
        ('title',  export_optional_string, None),
        ('date',   export_optional_date,   None),
      ])


class TweetLoader(bulkloader.Loader):
  def __init__(self):
    bulkloader.Loader.__init__(self, 'Tweet',
      [
        ('id',                long),
        ('created_at',        load_datetime),
        ('from_user',         load_string),
        ('from_user_id',      long),
        ('to_user',           load_optional_string),
        ('to_user_id',        load_optional_long),
        ('iso_language_code', load_string),
        ('source',            load_string),
        ('raw_text',          load_string),
        ('text',              load_string),
        ('short_url',         load_optional_link),
        ('long_url',          load_optional_link),
        ('is_retweet',        bool),
        
        ('origin',            load_origin),
        ('article',           load_article),
      ])
  def generate_key(self, i, values):
    return 't' + str(values[0])

class TweetExporter(bulkloader.Exporter):
  def __init__(self):
    bulkloader.Exporter.__init__(self, 'Tweet',
      [
        ('id',                str, None),
        ('created_at',        export_datetime, None),
        ('from_user',         export_string, None),
        ('from_user_id',      str, None),
        ('to_user',           export_optional_string, None),
        ('to_user_id',        export_optional_long, None),
        ('iso_language_code', export_string, None),
        ('source',            export_string, None),
        ('raw_text',          export_string, None),
        ('text',              export_string, None),
        ('short_url',         export_optional_link, None),
        ('long_url',          export_optional_link, None),
        ('is_retweet',        str, None),

        ('origin',            export_origin,  None),
        ('article',           export_article, ''),
      ])


def load_optional_string(x):
  if x:
    return unicode(x, 'utf-8')
  else:
    return None

def export_optional_string(x):
  if x is None:
    return ''
  else:
    return x.encode('utf-8')

def load_string(x):
  return unicode(x, 'utf-8')

def export_string(x):
  return x.encode('utf-8')

def load_optional_date(x):
  if x:
    return datetime.datetime.strptime(x, '%Y-%m-%d').date()
  else:
    return None

def export_optional_date(x):
  if x is None:
    return ''
  else:
    return datetime.date.strftime(x, '%Y-%m-%d')

def load_date(x):
  return datetime.datetime.strptime(x, '%Y-%m-%d').date()

def export_date(x):
  return datetime.date.strftime(x, '%Y-%m-%d')

def load_datetime(x):
  return datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S')

def export_datetime(x):
  return datetime.datetime.strftime(x, '%Y-%m-%d %H:%M:%S')

def load_optional_long(x):
  if x:
    return long(x)
  else:
    return None

def export_optional_long(x):
  if x is None:
    return ''
  else:
    return str(x)

def load_optional_link(x):
  if x:
    return db.Link(x)
  else:
    return None

def export_optional_link(x):
  if x is None:
    return ''
  else:
    return x # db.Link is a subclass of unicode

def load_origin(x):
  url, tag = x.split('#')
  return data.Origin.all().filter('tag =', tag).filter('api_url =', url).get()

def export_origin(x):
  return x.api_url + '#' + x.tag

def load_article(x):
  return data.Article.all().filter('url =', x).get()

def export_article(x):
  return x.url

loaders   = [ OriginLoader,   DestinationLoader,   SiteLoader,   ArticleLoader,   TweetLoader   ]
exporters = [ OriginExporter, DestinationExporter, SiteExporter, ArticleExporter, TweetExporter ]


# env PYTHONPATH=toss140 appcfg.py download_data --config_file=toss140/loader.py \
#  --filename=data/Origin.csv --kind=Origin --url=http://2.latest.toss140.appspot.com/remote_api \
#  --email=robin.houston@gmail.com toss140
