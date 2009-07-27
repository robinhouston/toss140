from collections import defaultdict
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
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext import webapp
import wsgiref.handlers

import data
import screenscrapers


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

def store_tweet(tweet, ignore_link = False):
  logging.info("Storing tweet: %s", tweet)
  raw_text = html_unescape(tweet['text'])
  if ignore_link:
    short_url = None
  else:
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

def _simple_fetch(url, method = 'GET'):
  logging.info('Fetching ' + url)
  return urlfetch.fetch(
    url = url,
    follow_redirects = False,
    deadline = 10,
    allow_truncated = True,
    method = method,
  )

def _fetch(url):
  response = _simple_fetch(url)
  while response.status_code in range(300, 399):
    location = response.headers['Location']
    if location[0] == '/':
      mo_url = re.match(r'(https?://[^/]+)', url)
      if mo_url:
        url = mo_url.group(1) + location
      else:
        raise Exception("Don't know what to do with location: " + location)
    else:
      url = location
    if url is None:
      raise Exception('Found a redirect response with no Location')
    response = _fetch(url)

  if response.status_code not in (200, 300):
    raise Exception('Error response ' + response.status_code + ' from ' + url)
  
  setattr(response, 'url', url)
  return response

def index(tweet):
  tweet.text = text_from_raw_text(tweet.raw_text)
  tweet.is_retweet = bool(re.search(r'(?i)\bRT\b|\(via @', tweet.text))
  
  if tweet.short_url is not None:
    response = _fetch(tweet.short_url)
    if re.match(r'^http://digg.com/', response.url):
      mo_url = re.search(r'<h1 id="title">\s*<a href="([^"]+)', response.content)
      if mo_url:
        response = _fetch(mo_url.group(1))
      else:
        raise Exception('Failed to find target URL in digg page ' + response.url)
    tweet.long_url = response.url
    tweet.article = article(response)

  tweet.put()
  refresh_caches(tweet)
  update_counters(tweet)

def article(response):
  url = response.url
  article = data.Article.get_by_key_name(url)

  if article is None:
    host, path = re.match(r'(?i)^http://([^/]+)(/?.*)', url).groups()
    site = data.get_site(host)
    title = None

    try:
      content = response.content.decode('utf-8')
    except UnicodeDecodeError:
      logging.debug("Content could not be interpreted as UTF-8, trying ISO-8859-1")
      content = response.content.decode('ISO-8859-1')

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

def refresh_caches(tweet):
  '''Clear any cached pages that have changed as a result of the addition of this tweet.
  
  (Actually the current implementation just flushes the whole cache.)'''
  memcache.flush_all()

def update_counters(tweet):
  logging.info("Updating count for tweeter %s", tweet.from_user)
  tweeter = data.Tweeter.get_by_name(tweet.from_user)
  tweeter.recount()
  tweeter.put()
  
  if tweet.article:
    logging.info("Updating count for article")
    article = tweet.article
    article.recount()
    article.put()
    
    site = article.parent()
    logging.info("Updating count for site %s", site.name)
    site.recount()
    site.put()

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
  _retweet_queue   = taskqueue.Queue(name='retweet')
  _retry_queue     = taskqueue.Queue(name='add-tweet-retry')

  def post(self):
    tweet = {}
    for k, v in self.request.params.iteritems():
      tweet[str(k)] = unicode(v)
    logging.debug("add-tweet: storing %s", tweet)
    try:
      stored_tweet = store_tweet(tweet)
    except Exception:
      if 'retries' in tweet:
        tweet['retries'] = long(tweet['retries']) + 1
      else:
        tweet['retries'] = 1

      if tweet['retries'] > 10:
        logging.exception("Failed after 10 attempts, storing without link")
        store_tweet(tweet, ignore_link = True)
      else:
        logging.exception("Failed to store tweet; requeuing in the retry queue (%d)" %  tweet['retries'])
        task = taskqueue.Task(
          url='/do/add-tweet', countdown = 300 * tweet['retries'],
          method='POST', params=tweet
        )
        self._retry_queue.add(task)

      return
    
    task = taskqueue.Task(
      url='/do/retweet', countdown=0, method='POST',
      params={'key': stored_tweet.key()}
    )
    self._retweet_queue.add(task)

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

    if tweet.is_retweet or not tweet.short_url:
      return
    
    suffix = ' ' + tweet.short_url + ' @' + tweet.from_user
    if len(tweet.text) + len(suffix) <= 140:
      truncated_text = tweet.text
    else:
      truncated_text = tweet.text[: 140 - len(suffix) - 1] + u'\u2026'

    for destination in data.Destination.all():
      destination.post(truncated_text + suffix)

class RecountHandler(webapp.RequestHandler):
  def get(self, what, who):
    who = urllib.unquote(who)

    if what == 'author':
      author = data.Author.get_by_name(who)
      if not author:
        self.error(404)
        return
      n = author.recount()
      author.put()

    elif what == 'organ':
      site = data.Site.all().filter('name =', who).get()
      if not site:
        self.error(404)
        return
      n = site.recount()
      site.put()

    elif what == 'tweeter':
      tweeter = data.Tweeter.get_by_name(who)
      if not tweeter:
        self.error(404)
        return
      n = tweeter.recount()
      tweeter.put()
    
    self.response.headers["Content-Type"] = "text/plain"
    self.response.out.write("%s '%s' has %d summaries\n" % (what, who, n))

class CountHandler(webapp.RequestHandler):
  def get(self):
    authors, tweeters, articles, sites = map(defaultdict, [lambda: 0] * 4)
    for tweet in data.Tweet.all():
      if tweet.is_retweet:
        continue
      article = tweet.article
      if not article:
        continue
      site = article.parent()
      
      if article.author:
        authors[article.author] += 1 
      tweeters[tweet.from_user] += 1
      articles[article.key()] += 1
      sites[site.key()] += 1
    
    self.response.headers["Content-Type"] = "text/plain; charset=utf-8"

    self.response.out.write("Authors:\n")
    for author_name, count in authors.items():
      self.response.out.write("\t%s: %d\n" % (author_name, count))
      data.Author.get_by_name(name=author_name, count=count).put()

    self.response.out.write("\nTweeters:\n")
    for tweeter_name, count in tweeters.items():
      self.response.out.write("\t%s: %d\n" % (tweeter_name, count))
      data.Tweeter.get_by_name(name=tweeter_name, count=count).put()
    
    self.response.out.write("\nArticles:\n")
    for article_key, count in articles.items():
      article = data.Article.get(article_key)
      self.response.out.write("\t%s, %s, %s: %d\n" % (article.author, article.parent().name, str(article.date), count))
      article.num_tweets = count
      article.put()

    self.response.out.write("\nSites:\n")
    for site_key, count in sites.items():
      site = data.Site.get(site_key)
      self.response.out.write("\t%s: %d\n" % (site.name, count))
      site.num_tweets = count
      site.put()

def main():
  application = webapp.WSGIApplication([
    ('/do/update',       UpdateHandler),
    ('/do/add-tweet',    AddTweetHandler),
    ('/do/index-tweets', IndexTweetsHandler),
    ('/do/index-tweet',  IndexTweetHandler),
    ('/do/retweet',      ReTweetHandler),
    ('/do/recount/(author|organ|tweeter)/(.+)', RecountHandler),
    ('/do/count',        CountHandler),
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
