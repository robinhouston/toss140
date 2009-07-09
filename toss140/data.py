import logging
import urllib

from google.appengine.ext import db
from google.appengine.api import memcache

class Stats(db.Model):
  tag = db.StringProperty(required=True, default='toss140')
  max_id = db.IntegerProperty(required=True, default=1)
  count = db.IntegerProperty(required=True, default=0)

# The key name is the hostname of the web site
class Site(db.Model):
  host = db.StringProperty(required=True)
  name = db.StringProperty(required=False, default=None)

# Every Article should have a parent that is a Site
# The key name is the ultimate URL of the article
class Article(db.Model):
  url    = db.StringProperty(required=True)
  pub    = db.StringProperty(required=False)
  author = db.StringProperty(required=False)
  title  = db.StringProperty(required=False)
  date   = db.DateProperty  (required=False)

class Tweet(db.Model):
  id = db.IntegerProperty(required=True)
  created_at = db.DateTimeProperty(required=True)
  from_user = db.StringProperty(required=True)
  from_user_id = db.IntegerProperty(required=True)
  to_user = db.StringProperty(required=False)
  to_user_id = db.IntegerProperty(required=False)
  iso_language_code = db.StringProperty(required=True)
  source = db.StringProperty(required=True)
  raw_text = db.StringProperty(required=True, multiline=True)
  text = db.StringProperty(required=True, multiline=True)
  short_url = db.LinkProperty(required=False)
  long_url = db.LinkProperty(required=False)
  is_retweet = db.BooleanProperty(required=True, default=False)

  article = db.ReferenceProperty(required=False, reference_class=Article, default=None)


_STATS_KEY = db.Key.from_path('Stats', 'toss140')

def get_stats():
  stats = Stats.get(_STATS_KEY)
  if not stats:
    stats = Stats(key_name='toss140')
  return stats

def get_site(hostname):
  site = Site.get_by_key_name(hostname)
  if not site:
    site = Site(key_name=hostname, host=hostname, name=get_site_name(hostname))
    site.put()
  return site

def get_site_name(hostname):
  url = 'http://' + hostname + '/'