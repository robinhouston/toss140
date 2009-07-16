import htmlentitydefs
import logging
import os
import re
import traceback
import urllib

import dateutil.parser
from django.utils import simplejson
from google.appengine.api import memcache
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp
import wsgiref.handlers

import data
import screenscrapers
import toss # FIXME only needed for date_before, date_after and VERSION: move them to data?


# DeadlineExceededError can live in two different places 
try: 
  # When deployed 
  from google.appengine.runtime import DeadlineExceededError 
except ImportError: 
  # In the development server 
  from google.appengine.runtime.apiproxy_errors import DeadlineExceededError 


def new_tweets_from_origin(origin):
  url = origin.api_url + 'search.json?q=%23' + origin.tag + '&rpp=100&since_id=' + str(origin.max_id)
  results = []
  while 1:
    logging.info("Fetching URL: %s", url)
    raw_result = simplejson.load(urllib.urlopen(url))
    logging.debug(raw_result)
    results.extend(raw_result["results"])
    if 'next_page' not in raw_result:
      break
    url = api_url + 'search.json' + raw_result['next_page']

  return results

def store_tweet(tweet):
  logging.info("Storing tweet: %s", tweet)
  raw_text = html_unescape(tweet['text'])
  short_url = extract_url(raw_text)
  twid = long(tweet['id'])
  to_user_id = None
  try:
    to_user_id = long(tweet.get('to_user_id'))
  except ValueError:
    pass

  t = data.Tweet(
    key_name = 't' + str(twid),
    id = twid,
    created_at = dateutil.parser.parse(tweet['created_at']),
    from_user = tweet['from_user'],
    from_user_id = long(tweet['from_user_id']),
    to_user = tweet.get('to_user'),
    to_user_id = to_user_id,
    iso_language_code = tweet['iso_language_code'],
    source = html_unescape(tweet['source']),
    origin = data.Origin.get(tweet['origin_key']),
    raw_text = raw_text,
    text = '-', # Filled in by the index(t) call below
    short_url = short_url,
    long_url  = short_url, # Replaced by index(t)
    is_retweet = False,
  )
  index(t)
  return t

def extract_url(raw_text):
  mo_url = re.search(r'http://\S+', raw_text)
  if mo_url:
    url = re.sub(r'''[.,;:"'!]$''', '', mo_url.group())
    if re.match(r'http://(www\.)?toss140\.net', url):
      return None
    return url
  else:
    return None

def text_from_raw_text(raw_text):
  text = re.sub(r'#(toss140|fb)\b', '', raw_text)
  text = re.sub(r'http://\S+', '', text)
  text = re.sub(r'^\s*(@\S+\s*)?|(\s*[:-])?\s+$', '', text)
  text = re.sub(r'\s+', ' ', text)
  text = re.sub(r'''^(["'])(.*)\1$''', r'\2', text)

  return text

def index(tweet):
  tweet.text = text_from_raw_text(tweet.raw_text)
  tweet.is_retweet = bool(re.search(r'(?i)\bRT\b|\(via @', tweet.text))
  
  if tweet.short_url is not None:
    fh_url = urllib.urlopen(tweet.short_url)
    tweet.long_url = fh_url.geturl()
    tweet.article = article(fh_url)
    fh_url.close()

  tweet.put()
  refresh_caches(tweet)

def article(fh):
  url = fh.geturl()
  article = data.Article.get_by_key_name(url)

  if article is None:
    host, path = re.match(r'(?i)^http://([^/]+)(/?.*)', url).groups()
    site = data.get_site(host)
    title = None

    content = fh.read(32767).decode('utf-8')
    mo = re.search(r'(?s)<title>(.*?)</title>', content)
    if mo:
      title = mo.group(1)
      logging.debug("title: %s", title)    

    if title:
      title = re.sub(r'^\s+|\s+$', '', title)
      title = re.sub(r'\s+', ' ', title)
      title = re.sub(r'\s*\|.*', '', title)

    logging.info("Creating new article for %s", url)
    args = screenscrapers.scrape(host, content)
    if 'title' not in args:
      logging.debug("scraper found no title, so using: %s", title)
      args['title'] = title
    article = data.Article(parent=site, key_name=url, url=url, **args)
    article.put()

  return article

def clear_cache(key, value=None):
  if value is None:
    memcache_key = key
  else:
    memcache_key = key + '=' + value
  memcache_key = 'v' + toss.VERSION + ':' + memcache_key
  logging.debug("Clearing memcache key '%s'", memcache_key)
  memcache.delete(memcache_key)
  memcache.delete('admin:' + memcache_key)

def refresh_caches(tweet):
  '''Clear any cached pages that have changed as a result of the addition of this tweet.'''
  clear_cache("front")
  clear_cache("timeline")
  clear_cache("recent")
  
  clear_cache("tweeter", tweet.from_user)
  
  if tweet.short_url is None:
    clear_cache("linkless")
  
  if tweet.article:
    clear_cache("organ", tweet.article.parent().name)
    if tweet.article.author:
      clear_cache("author", tweet.article.author)
    if tweet.article.date:
      clear_cache("date", str(tweet.article.date))
      date_before = toss.date_before(tweet.article.date)
      if date_before is not None:
        clear_cache("date", str(date_before))
      date_after = toss.date_after(tweet.article.date)
      if date_after is not None:
        clear_cache("date", str(date_after))

def update_stats(origin, n, max_id):
  db.run_in_transaction(_update_stats, origin_key=origin.key(), n=n, max_id=max_id)

def _update_stats(origin_key, n, max_id):
  logging.debug("Updating stats: n=%d, max_id=%d", n, max_id)

  origin = data.Origin.get(origin_key)
  origin.count += n
  if max_id > origin.max_id:
    origin.max_id = max_id
  else:
    logging.warn("New max_id (%d) is no larger than existing (%d) for %s",
      max_id, origin.max_id, origin_key.name())

  origin.put()

##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.
# @author Fredrik Lundh (http://effbot.org/zone/re-sub.htm#unescape-html)
def html_unescape(text):
  def fixup(m):
    text = m.group(0)
    if text[:2] == "&#":
      # character reference
      try:
        if text[:3] == "&#x":
          return unichr(int(text[3:-1], 16))
        else:
          return unichr(int(text[2:-1]))
      except ValueError:
        pass
    else:
      # named entity
      try:
        text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
      except KeyError:
        pass
    return text # leave as is
  return re.sub("&#?\w+;", fixup, text)



class UpdateHandler(webapp.RequestHandler):
  '''Called periodically to fetch new summaries from twitter (etc.)
  
  Each new summary is placed into the 'add-tweet' task queue, and the
  AddTweetHandler is then called separately for each one.
  '''
  _queue   = taskqueue.Queue(name='add-tweet')
  
  def get(self):
    self.response.headers['Content-type'] = 'text/plain';
    for origin in data.get_origins():
      try:
        tweets = new_tweets_from_origin(origin)
      except Exception:
        logging.error("Failed to fetch updates from %s: %s", origin.key().name(), traceback.format_exc())
        continue

      max_id = 1
      for tweet in tweets:
        if tweet['id'] < origin.max_id:
          logging.warn("Found tweet with id %d, less than since_id %d" % (tweet['id'], origin.max_id))
          continue
        tweet['origin_key'] = origin.key()
        if tweet['id'] > max_id:
          max_id = tweet['id']
        task = taskqueue.Task(url='/do/add-tweet', countdown=0, method='POST', params=tweet)
        self._queue.add(task)
    
      if len(tweets) > 0:
        update_stats(origin, n=len(tweets), max_id=max_id)
      
      message = "Queued %d tweets from %s" % (len(tweets), origin.key().name())
      if len(tweets) > 0:
        logging.info(message)
      else:
        logging.debug(message)
      self.response.out.write(message + "\n")

class AddTweetHandler(webapp.RequestHandler):
  _queue   = taskqueue.Queue(name='retweet')

  def post(self):
    tweet = {}
    for k, v in self.request.params.iteritems():
      tweet[str(k)] = unicode(v)
    logging.debug("add-tweet: storing %s", tweet)
    stored_tweet = store_tweet(tweet)
    
    task = taskqueue.Task(
      url='/do/retweet', countdown=0, method='POST',
      params={'key': stored_tweet.key()}
    )
    self._queue.add(task)

class IndexTweetsHandler(webapp.RequestHandler):
  
  _queue   = taskqueue.Queue(name='index-tweet')
  
  def get(self):
    for tweet in data.Tweet.all():
      task = taskqueue.Task(url='/do/index-tweet', countdown=0, method='POST', params={"key": tweet.key()})
      self._queue.add(task)

class IndexTweetHandler(webapp.RequestHandler):
  def post(self):
    key = self.request.get("key")
    tweet = data.Tweet.get(key)
    index(tweet)
  
  def get(self):
    self.post()
    ref = os.environ.get('HTTP_REFERER')
    if ref:
      if '?' in ref:
        self.redirect(ref + '&refresh=1')
      else:
        self.redirect(ref + '?refresh=1')
    else:
      self.redirect('/?refresh=1')

class ReTweetHandler(webapp.RequestHandler):
  def post(self):
    key = self.request.get("key")
    tweet = data.Tweet.get(key)
    status = re.sub(r'#toss140', '', tweet.raw_text)
    status = re.sub(r' +', ' ', status)
    status = status[: 138 - len(tweet.from_user)] + ' @' + tweet.from_user
    post_data = urllib.urlencode({"status": status, "in_reply_to_status_id": tweet.id})
    for destination in data.Destination.all():
      fh = urllib.urlopen(destination.url_with_auth(), post_data)
      logging.debug(fh.read())
      fh.close()

def main():
  application = webapp.WSGIApplication([
    ('/do/update',       UpdateHandler),
    ('/do/add-tweet',    AddTweetHandler),
    ('/do/index-tweets', IndexTweetsHandler),
    ('/do/index-tweet',  IndexTweetHandler),
    ('/do/retweet',      ReTweetHandler),
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
