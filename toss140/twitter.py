import htmlentitydefs
import logging
import re
import urllib

import dateutil.parser
from django.utils import simplejson
from google.appengine.ext import db
from BeautifulSoup import BeautifulSoup
import HTMLParser

import data
import screenscrapers


def new_tweets():
  global _stats, _n, _max_id
  _stats = data.get_stats()
  url = 'http://search.twitter.com/search.json?q=%23toss140&rpp=100&since_id=' + str(_stats.max_id)
  results = []
  while 1:
    logging.info("Fetching URL: %s", url)
    raw_result = simplejson.load(urllib.urlopen(url))
    logging.debug(raw_result)
    results.extend(raw_result["results"])
    if 'next_page' not in raw_result:
      break
    url = 'search.twitter.com/search.json' + raw_result['next_page']

  _n = len(results)
  _stats.max_id = raw_result["max_id"]
  
  return results

def store_tweet(tweet):
  logging.info("Storing tweet: %s", tweet)
  raw_text = html_unescape(tweet['text'])
  text = re.sub(r'#toss140', '', raw_text)

  mo_url = re.search(r'http://\S+', text)
  long_url = None
  if mo_url:
    url = mo_url.group()
    if mo_url.start() == 0:
      text = text[mo_url.end()+1:]
    else:
      text = text[:mo_url.start()-1] + text[mo_url.end()+1:]
    try:
      fh_url = urllib.urlopen(url)
      long_url = fh_url.geturl()
      logging.debug("%s -> %s", url, long_url)
      fh_url.close()
    except Exception, e:
      logging.warn("Error fetching %s: %s", url, e)
  else:
    url = None

  text = re.sub(r'^\s+(@\S+\s*)?|(\s*[:-])?\s+$', '', text)
  text = re.sub(r'\s+', ' ', text)
  
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
    raw_text = raw_text,
    text = text,
    short_url = url,
    long_url = long_url,
    is_retweet = bool(re.search(r'(?i)\bRT\b', text))
  )
  index(t)
  t.put()

def index(tweet):
  if tweet.long_url is None:
    return
  fh_url = None
  try:
    fh_url = urllib.urlopen(tweet.long_url)
  except Exception, e:
    logging.warn("Error indexing %s: %s", tweet.long_url, e)

  if fh_url:
    tweet.article = article(fh_url)
    fh_url.close()
  tweet.put()

def article(fh):
  url = fh.geturl()
  article = data.Article.get_by_key_name(url)

  if article is None:
    host, path = re.match(r'(?i)^http://([^/]+)(/?.*)', url).groups()
    site = data.get_site(host)
    title = None
    
    content = fh.read(32767)
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


def update_stats(n, max_id):
  db.run_in_transaction(_update_stats, n=n, max_id=max_id)

def _update_stats(n, max_id):
  logging.debug("Updating stats: n=%d, max_id=%d", n, max_id)

  stats = data.get_stats()
  stats.count += n
  if max_id > stats.max_id:
    stats.max_id = max_id
  else:
    logging.warn("New max_id (%d) is no larger than existing (%d)", max_id, stats.max_id)

  stats.put()

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
