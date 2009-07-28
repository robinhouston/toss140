import base64
import logging
import os
import re
import urllib

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import urlfetch

import oauth

def _count(model, prop, value):
  '''Count the number of instances of model whose property 'prop' has value 'value'.'''
  q = model.all().filter(prop + ' = ', value)
  n = q.count()
  if n < 1000:
    return n
  # The limit of the count() method has been reached.
  # Try the slow way -- though this will be limited by request timeout ultimately.
  n = 0
  for x in q:
    n += 1
  return n

class Origin(db.Model):
  tag = db.StringProperty(required=True, default='toss140')
  api_url = db.LinkProperty(required=True)
  max_id = db.IntegerProperty(required=True, default=1)
  count = db.IntegerProperty(required=True, default=0)

class Destination(db.Model):
  update_url = db.LinkProperty(required=True, default='http://twitter.com/statuses/update.json')
  request_token_url = db.LinkProperty(required=False, default='http://twitter.com/oauth/request_token')
  access_token_url = db.LinkProperty(required=False, default='http://twitter.com/oauth/access_token')

  username = db.StringProperty(required=True, default='toss140')
  password = db.StringProperty(required=False, default='')

  consumer_key = db.StringProperty(required=False)
  consumer_secret = db.StringProperty(required=False)
  oauth_token = db.StringProperty(required=False)
  oauth_token_secret = db.StringProperty(required=False)

  def _url_with_basic_auth(self):
    return self.update_url.replace('://', '://%s:%s@' % (self.username, self.password), 1)
  
  _oauth_object = None
  def oauth(self):
    if not self._oauth_object:
      self._oauth_object = oauth.OAuth(self.consumer_key, self.consumer_secret)
    return self._oauth_object
  
  def _oauth_request(self, url, payload):
    return self.oauth().oauth_request(url, self.oauth_token, self.oauth_token_secret, payload)
    
  def post(self, message):
    '''Post a status update to the destination.'''
    payload = [ ('status', message.encode('utf-8')) ]
    if self.password:
      url = self._url_with_basic_auth()
      fh = urllib.urlopen(url, urllib.urlencode(payload))
      response = fh.read()
    else:
      response = self.oauth().oauth_request(
        self.update_url, self.oauth_token, self.oauth_token_secret, payload)

    logging.debug(response)
    return response
  
  def request_token(self):
    response = self.oauth().oauth_request(self.request_token_url)
    mo = re.match(r'^oauth_token=(.*)&oauth_token_secret=(.*)$', response)
    token, secret = mo.groups()
    return token, secret
  
  def tweet(self, user, message):
    payload = [ ('status', message.encode('utf-8')) ]
    response = self.oauth().oauth_request(
      self.update_url, user.oauth_token, user.oauth_token_secret, payload)
  
  def user(self, request_token, request_token_secret):
    response = self.oauth().oauth_request(self.access_token_url, request_token, request_token_secret)
    mo = re.match(r'^oauth_token=(.*)&oauth_token_secret=(.*)&user_id=(.*)&screen_name=(.*)$', response)
    token, secret, user_id, screen_name = mo.groups()
    return User.create_or_update(long(user_id), screen_name, token, secret)

class OAuthRequestToken(db.Model):
  '''An OAuth request token. Deleted when it's been exchanged for an access token.'''
  # key_name should be 'x' + token
  secret = db.StringProperty(required=True)
  callback = db.StringProperty(required=True, default='/')
  added_at = db.DateTimeProperty(required=True, auto_now_add=True)

class User(db.Model):
  user_id = db.IntegerProperty(required=True)
  name = db.StringProperty(required=False)
  screen_name = db.StringProperty(required=True)
  profile_image_url = db.LinkProperty(required=False)

  oauth_token = db.StringProperty(required=True) # The access token
  oauth_token_secret = db.StringProperty(required=True)

  @classmethod
  def create_or_update(cls, user_id, screen_name, oauth_token, oauth_token_secret):
    user = cls.all().filter('user_id =', user_id).get()
    if user:
      user.oauth_token = oauth_token
      user.oauth_token_secret = oauth_token_secret
    else:
      user = cls(
        key_name = base64.urlsafe_b64encode(os.urandom(33)),
        user_id = user_id,
        screen_name = screen_name,
        oauth_token = oauth_token,
        oauth_token_secret = oauth_token_secret,
      )
      user.put()
    return user
  
  def tweet(self, message):
    dest = Destination.all().get()
    return dest.tweet(self, message)

# The key name is the hostname of the web site
class Site(db.Model):
  host = db.StringProperty(required=True)
  name = db.StringProperty(required=True)
  num_tweets = db.IntegerProperty(required=True, default=0)

  def recount(self):
    n = 0
    for article in Article.all().ancestor(self):
      if article.num_tweets:
        n += article.num_tweets
    self.num_tweets = n
    return n

# Every Article should have a parent that is a Site
# The key name is the ultimate URL of the article
class Article(db.Model):
  url    = db.StringProperty(required=True)
  author = db.StringProperty(required=False)
  title  = db.StringProperty(required=False)
  date   = db.DateProperty  (required=False)
  added_at = db.DateTimeProperty(required=True, auto_now_add=True)
  num_tweets = db.IntegerProperty(required=False)
  
  def tweets(self):
    return Tweet.all().filter('article =', self).filter('is_retweet =', False).order('-created_at')
  
  def recount(self):
    self.num_tweets = len(self.tweets().fetch(1000))
    return self.num_tweets

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
  shorter_url = db.LinkProperty(required=False)
  long_url = db.LinkProperty(required=False)
  is_retweet = db.BooleanProperty(required=True, default=False)

  origin = db.ReferenceProperty(required=True, reference_class=Origin)
  article = db.ReferenceProperty(required=False, reference_class=Article, default=None)
  
  number_of_retweets = db.IntegerProperty(required=True, default=0)
  
  def incr_retweets(self):
    db.run_in_transaction(_incr_retweets, self)
    self.number_of_retweets += 1
  
  def _incr_retweets(self):
    tweet = Tweet.get(self.key())
    tweet.number_of_retweets += 1
    tweet.put()
  
  def get_shorter_url(self):
    if not self.shorter_url:
      if not self.long_url:
        return None
      response = urlfetch.fetch(
        url = 'http://tinyarro.ws/api-create.php?utfpure=1\&url=' + self.long_url,
        follow_redirects = False,
        deadline = 10,
        allow_truncated = True,
        method = 'GET',
      )
      if response.status_code == 200:
        self.shorter_url = response.content.decode('utf-8')
      else:
        logger.error("tinyarro.ws request failed")
        return self.short_url
      self.put()
    return self.shorter_url
    

class _Counter(db.Model):
  name = db.StringProperty(required=True)
  num_tweets = db.IntegerProperty(required=True, default=0)
  
  def recount(self):
    self.num_tweets = self._get_count()
    return self.num_tweets
  
  @classmethod
  def get_by_name(cls, name, count=None):
    entity = cls.get_by_key_name('x' + name)
    if entity:
      if count:
        entity.num_tweets = count
      return entity
    entity = cls(name=name, key_name = 'x' + name)
    if count:
      entity.num_tweets = count
    else:
      entity.recount()
      if entity.num_tweets == 0:
        return None
    return entity

class Tweeter(_Counter):
  def _get_count(self):
    return _count(Tweet, 'from_user', self.name)

class Author(_Counter):
  def _get_count(self):
    return _count(Article, 'author', self.name)

def get_origins():
  return Origin.all().fetch(16)

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