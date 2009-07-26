import logging
import re

from google.appengine.ext import db
from google.appengine.api import memcache

import oauth

class Origin(db.Model):
  tag = db.StringProperty(required=True, default='toss140')
  api_url = db.LinkProperty(required=True)
  max_id = db.IntegerProperty(required=True, default=1)
  count = db.IntegerProperty(required=True, default=0)

class Destination(db.Model):
  api_url = db.LinkProperty(required=True, default='http://twitter.com/statuses/update.json')

  username = db.StringProperty(required=True, default='toss140')
  password = db.StringProperty(required=False, default='')

  consumer_key = db.StringProperty(required=False)
  consumer_secret = db.StringProperty(required=False)
  oauth_token = db.StringProperty(required=False)
  oauth_token_secret = db.StringProperty(required=False)

  def _url_with_basic_auth(self):
    return self.api_url.replace('://', '://%s:%s@' % (self.username, self.password), 1)
  
  def post(self, message):
    payload = ('status', message.encode('utf-8'))
    if self.password:
      url = self._url_with_basic_auth()
      fh = urllib.urlopen(url, urllib.urlencode(payload))
      response = fh.read()
    else:
      response = oauth.OAuth(self.consumer_key, self.consumer_secret)\
        .oauth_request(self.api_url, self.oauth_token, self.oauth_token_secret,
          payload)

    logging.debug(response)
    return response

# The key name is the hostname of the web site
class Site(db.Model):
  host = db.StringProperty(required=True)
  name = db.StringProperty(required=True)
  num_summaries = db.IntegerProperty(required=True, default=0)

# Every Article should have a parent that is a Site
# The key name is the ultimate URL of the article
class Article(db.Model):
  url    = db.StringProperty(required=True)
  author = db.StringProperty(required=False)
  title  = db.StringProperty(required=False)
  date   = db.DateProperty  (required=False)
  added_at = db.DateTimeProperty(required=True, auto_now_add=True)
  
  def tweets(self):
    return Tweet.all().filter('article =', self).order('-created_at')

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

  origin = db.ReferenceProperty(required=True, reference_class=Origin)
  article = db.ReferenceProperty(required=False, reference_class=Article, default=None)

class Tweeter(db.Model):
  name = db.StringProperty(required=True)
  num_summaries = db.IntegerProperty(required=True, default=0)

class Author(db.Model):
  name = db.StringProperty(required=True)
  num_summaries = db.IntegerProperty(required=True, default=0)

class User(db.Model):
  id = db.IntegerProperty(required=True)
  name = db.StringProperty(required=True)
  screen_name = db.StringProperty(required=True)
  profile_image_url = db.LinkProperty(required=True)
  
  oauth_token = db.StringProperty(required=True) # The access token
  oauth_token_secret = db.StringProperty(required=True)

def get_origins():
  origins = Origin.all().fetch(16)
  if origins:
    return origins
  twitter_origin = Origin(
    key_name='twitter#toss140',
    api_url='http://search.twitter.com/',
    max_id=2597007905,
    count=Tweet.all().count(),
  )
  twitter_origin.put()
  identica_origin = Origin(
    key_name='identica#toss140',
    api_url='http://identi.ca/api/',
  )
  identica_origin.put()
  return [twitter_origin, identica_origin]

def get_site(hostname):
  site = Site.get_by_key_name(hostname)
  if not site:
    site = Site(key_name=hostname, host=hostname, name=get_site_name(hostname))
    site.put()
  return site

def get_site_name(hostname):
  # It's hard to get the name from the site itself, because different sites format
  # the <title> of the front page in a bewildering variety of different ways. Just
  # fake the name up from the URL, and expect it will be edited by hand.
  return re.sub(r'^www\.', '', hostname)