import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import memcache

import base64
import datetime
import logging
import os
import re
import urllib

import data
import oauth

DEBUG = True
FETCH_SIZE = 20
DAYS_PER_PAGE = 7

TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')

ABOUT_TEMPLATE     = os.path.join(TEMPLATES, 'about.tmpl')
TIMELINE_TEMPLATE  = os.path.join(TEMPLATES, 'timeline.tmpl')
ATOM_TEMPLATE      = os.path.join(TEMPLATES, 'atom.tmpl')
RECENT_TEMPLATE    = os.path.join(TEMPLATES, 'recent.tmpl')

AUTHOR_TEMPLATE    = os.path.join(TEMPLATES, 'author.tmpl')
TWEETER_TEMPLATE   = os.path.join(TEMPLATES, 'tweeter.tmpl')
ORGAN_TEMPLATE     = os.path.join(TEMPLATES, 'organ.tmpl')
DATE_TEMPLATE      = os.path.join(TEMPLATES, 'date.tmpl')
TOP_TEMPLATE       = os.path.join(TEMPLATES, 'top_%s.tmpl')
LINKLESS_TEMPLATE  = os.path.join(TEMPLATES, 'linkless.tmpl')

VERSION, MINOR_VERSION = os.environ.get('CURRENT_VERSION_ID').split('.')


"""Load custom Django template filters and tags"""
webapp.template.register_template_library('template_extensions')


def articles_by_site(site, n=FETCH_SIZE):
  return data.Article.all().ancestor(site).order('-date').order('-added_at').fetch(n)

def articles_by_author(author, n=FETCH_SIZE):
  return data.Article.all().filter('author =', author).order('-date').order('-added_at').fetch(n)

def articles_on_date(date, n=FETCH_SIZE):
  logging.info("fetching articles for date = %s", str(date))
  return data.Article.all().filter('date =', date).order("-date").order('-added_at').fetch(n)

def _for_days(d, it):
  articles = []
  prev_date = None
  article_index = 0

  for article in it:
    if article.date != prev_date:
      article_index += 1
      if article_index > d:
        break
    articles.append(article)
    prev_date = article.date

  return articles

def latest_articles(d=DAYS_PER_PAGE):
  '''Fetch the latest articles.
  
  Get all the articles published in the last d days, counting only days
  for which we have at least one article. The articles are returned in
  reverse chronological order.
  '''
  return _for_days(d=d, it=data.Article.all().order('-date').order('-added_at'))

def articles_till_date(date, d=DAYS_PER_PAGE):
  return _for_days(d=d, it=data.Article.all().filter('date <=', date).order('-date').order('-added_at'))

def articles_since_date(date, d=DAYS_PER_PAGE):
  return _for_days(d=d, it=data.Article.all().filter('date >=', date).order('date').order('added_at'))[::-1]

def date_before(date):
  article_before = data.Article.all().filter('date <', date).order("-date").get()
  if article_before is None:
    return None
  else:
    return article_before.date

def date_after(date):
  article_after = data.Article.all().filter('date >', date).order("date").get()
  if article_after is None:
    return None
  else:
    return article_after.date


def recent_tweets(n=FETCH_SIZE):
  tweets = []
  for tweet in data.Tweet.all().order("-created_at"):
    if tweet.long_url and not tweet.is_retweet:
      tweets.append(tweet)
      if len(tweets) == n:
        break
  return tweets

def tweets_by_tweeter(tweeter, n=FETCH_SIZE):
  return data.Tweet.all().filter('from_user =', tweeter).order('-created_at').fetch(n)

def tweets_without_link(n=FETCH_SIZE):
  return data.Tweet.all().filter("long_url =", None).order("-created_at").fetch(n)

def parse_iso_date(datestr):
  mo = re.match(r'^(\d\d\d\d)-(\d\d)-(\d\d)$', datestr)
  if not mo:
    raise NotFound
  return datetime.date(*map(int, mo.groups()))

class AdminLoginHandler(webapp.RequestHandler):
  # This handler just redirects to the supplied URL.
  # The point is that /adminlogin as specified as login: admin in app.yaml,
  # so App Engine will make the user log in before we even get here.
  def get(self):
    url = self.request.get("r")
    if not url:
      url = '/'
    self.redirect(url)

class LoginHandler(webapp.RequestHandler):
  def get(self):
    callback = self.request.get('r') or '/'
    dest = data.Destination.all().get()
    token, secret = dest.request_token()
    nonce = base64.urlsafe_b64encode(os.urandom(33))
    data.OAuthRequestToken(key_name = 'x' + token, secret=secret, callback=callback).put()
    params = {
      "oauth_token": token,
      "oauth_callback": re.sub(r'/login.*', '/authorized', self.request.url)
    }
    self.redirect("http://twitter.com/oauth/authenticate?" + urllib.urlencode(params))

class LoginAuthorizedHandler(webapp.RequestHandler):
  def get(self):
    r = self.request
    token = r.get('oauth_token')
    verifier = r.get('oauth_verifier')
    oart = data.OAuthRequestToken.get_by_key_name('x' + token)
    if not oart:
      self.error(500)
      return
    secret = oart.secret
    oart.delete()
    dest = data.Destination.all().get()
    
    user = dest.user(token, secret)
    
    self.response.headers['Content-type'] = 'text/plain; charset=utf-8'
    self.response.headers['Set-Cookie'] = 'user=' + str(user.key().name())
    self.redirect(oart.callback)

class AuthorizedHandler(webapp.RequestHandler):
  def get(self, *args):
    return self.post(*args)
  def post(self, *args):
    user_key = self.request.cookies.get('user')
    if user_key:
      self.user = data.User.get_by_key_name(user_key)
    else:
      self.user = None

    if not self.user:
      url = self.request.url
      referer = os.environ.get('HTTP_REFERER')
      if referer:
        if '?' in url:
          url += '&'
        else:
          url += '?'
        url += 'ref=' + urllib.quote(referer)
      else:
        logging.info("No referer")
      self.redirect('/login?' + urllib.urlencode( {'r': url} ))
    
    else:
      referer = self.request.get('ref') or os.environ.get('HTTP_REFERER')
      self.dest = data.Destination.all().get()
      self.do(referer, *args)

  def tweet(self, message):
    self.user.tweet(message)

class RTHandler(AuthorizedHandler):
  def do(self, referer, tweet_key):
    logging.info('Retweeting ' + tweet_key)
    tweet = data.Tweet.get(tweet_key)
    text = tweet.text
    shorter_url = tweet.get_shorter_url()
    max_text_length = 140 - 17 - len(tweet.from_user) - len(shorter_url)
    if len(text) > max_text_length:
      logging.info('text is longer than %d chars, truncating', max_text_length)
      text = text[: max_text_length - 1] + u'\u2026'
    message = u'RT @%s \u201C%s\u201D %s #toss140' % (tweet.from_user, text, shorter_url) 
    logging.info(message)
    self.tweet(message)
    tweet.incr_retweets()
    self.redirect(referer)

class LogoutHandler(webapp.RequestHandler):
  def get(self):
    self.response.headers['Set-Cookie'] = 'user='
    self.redirect(os.environ.get('HTTP_REFERER'))

class NotFound(Exception):
  '''Raised by a page handler if the requested resource is not found'''

class PageHandler(webapp.RequestHandler):
  '''Superclass for our page handlers.'''
  
  def _unquote(self, string):
    if string is None:
      return None
    else:
      return urllib.unquote(string).decode('utf-8')
  
  def get(self, *args):
    args = map(self._unquote, args)
    user_key = self.request.cookies.get('user')
    if user_key:
      user = data.User.get_by_key_name(user_key)
    else:
      user = None
    admin = self.request.get('admin')
    if admin and not users.is_current_user_admin():
      self.redirect("/adminlogin?r=" + urllib.quote(self.request.uri))
    
    memcache_key = 'v' + VERSION + ':' + self.memcache_key(*args)

    # At least on the dev server, self.request.uri contains the
    # URI of the original request, NOT of the target of the redirect,
    # even when we're processing the target of the redirect. (A bug?)
    uri = re.sub(r'[?&]refresh.*', '', self.request.uri)
    if self.request.get("refresh"):
      memcache.delete(memcache_key)
      memcache.delete('admin:' + memcache_key)
      self.redirect(uri)

    if admin:
      memcache_key = 'admin:' + memcache_key

    template_path = self.template_path(*args)
    try:
      template_args = self.template_args(*args)
    except NotFound:
      self.error(404)
      return
    
    template_args['memcache_key'] = memcache_key
    template_args['memcache_time'] = self.memcache_time(*args)
    template_args['debug'] = DEBUG
    template_args['admin'] = admin
    template_args['user']  = user
    template_args['this_page'] = uri
    template_args['recent_tweets'] = recent_tweets(5)

    if admin:
      template_args['q'] = '?admin=1'
      template_args['refresh_url'] = uri + '&refresh=1'
      template_args['logout_url']  = users.create_logout_url(self.request.uri)
    else:
      template_args['q'] = ''

    self.response.headers['Content-type'] = self.content_type()
    self.response.out.write(template.render(template_path, template_args))
  
  def memcache_time(*args):
    '''The default is no timeout.'''
    return 0
  
  def content_type(self):
    '''The content type. Default is text/html.'''
    return 'text/html'

class AuthorHandler(PageHandler):
  def memcache_key(self, author):
    return "author=" + author

  def template_path(self, author):
    return AUTHOR_TEMPLATE
    
  def template_args(self, author):
    return {
      "author":   author,
      "articles": articles_by_author(author),
    }

class TweeterHandler(PageHandler):
  def memcache_key(self, tweeter):
    return "tweeter=" + tweeter

  def template_path(self, tweeter):
    return TWEETER_TEMPLATE

  def template_args(self, tweeter):
    return {
      "tweeter": tweeter,
      "tweets":  tweets_by_tweeter(tweeter),
    }

class OrganHandler(PageHandler):
  def memcache_key(self, organ):
    return "organ=" + organ
    
  def template_path(self, organ):
    return ORGAN_TEMPLATE

  def template_args(self, organ):
    site = data.Site.all().filter('name =', organ).get()
    if site is None:
      raise NotFound
    
    return {
      "site":     site,
      "articles": articles_by_site(site),
    }

class RecentHandler(PageHandler):
  def memcache_key(self):
    return "recent"

  def template_path(self):
    return RECENT_TEMPLATE

  def template_args(self):
    return {
      "tweets": recent_tweets(),
    }

class DateHandler(PageHandler):
  def memcache_key(self, date):
    return "date=" + date

  def template_path(self, date):
    return DATE_TEMPLATE

  def template_args(self, datestr):
    date = parse_iso_date(datestr)
    articles = articles_on_date(date)
    logging.info("Found %d articles on %s", len(articles), str(date))
    return {
      "date":      date,
      "date_prev": date_before(date),
      "date_next": date_after(date),
      "articles":  articles,
    }

class LinklessHandler(PageHandler):
  def memcache_key(self):
    return "linkless"

  def template_path(self):
    return LINKLESS_TEMPLATE

  def template_args(self):
    return {
      "tweets": tweets_without_link(),
    }

class AboutHandler(PageHandler):
  def template_path(self):
    return ABOUT_TEMPLATE

  def memcache_key(self):
    return "about"

  def template_args(self):
    return {}

class FeedHandler(PageHandler):
  def template_path(self):
    return ATOM_TEMPLATE

  def memcache_key(self):
    return "feed"

  def template_args(self):
    return {
      "tweets": recent_tweets(1000)
    }
  
  def content_type(self):
    return 'application/atom+xml'

class TopHandler(PageHandler):
  def memcache_key(self, what):
    return "top=" + what
  
  def template_path(self, what):
    return TOP_TEMPLATE % what
  
  def template_args(self, what):
    if what == 'tweeter':
      top_tweeters = data.Tweeter.all().order('-num_tweets').fetch(10)
      return { 'tweeters': top_tweeters }
    
    elif what == 'author':
      top_authors = data.Author.all().order('-num_tweets').fetch(10)
      return { 'authors': top_authors }
    
    elif what == 'organ':
      top_sites = data.Site.all().order('-num_tweets').fetch(10)
      return { 'sites': top_sites }

class lazy(object):
  def __init__(self, f, *args):
    self.f, self.args = f, args
  def __call__(self):
    if not self.value:
      self.value = self.f(*self.args)
    return self.value

class TimelineHandler(PageHandler):
  def memcache_key(self, direction=None, date=None):
    if date is None:
      return "timeline"
    else:
      return "timeline=" + direction + '-' + date

  def template_path(self, direction=None, datestr=None):
    return TIMELINE_TEMPLATE

  def template_args(self, direction=None, datestr=None):
    if datestr is None:
      articles = latest_articles()
      date = None
    else:
      date = parse_iso_date(datestr)
      if direction == 'till':
        articles = lazy(articles_till_date, date)
      elif direction == 'since':
        articles = lazy(articles_since_date, date)
      else:
        raise NotFound
    return {
      "articles": articles,
      "older":    lazy(lambda f: f(articles()[-1].date), date_before),
      "newer":    lazy(lambda f: f(articles()[0].date),  date_after),
      "date":     date,
      "front":    True,
    }

def main():
  application = webapp.WSGIApplication([
    ('/adminlogin',        AdminLoginHandler),
    ('/login',             LoginHandler),
    ('/logout',            LogoutHandler),
    ('/authorized',        LoginAuthorizedHandler),
    ('/rt/(.*)',           RTHandler),
                           
    ('/',                  TimelineHandler),
    ('/atom.xml',          FeedHandler),
    ('/about',             AboutHandler),
    ('/(since|till)/(.+)', TimelineHandler),
    ('/recent',            RecentHandler),
                           
    ('/author/([^/]+)',    AuthorHandler),
    ('/tweeter/([^/]+)',   TweeterHandler),
    ('/organ/([^/]+)',     OrganHandler),
    ('/date/([^/]+)',      DateHandler),
    ('/top/(.+)',          TopHandler),
    ('/linkless',          LinklessHandler),
  ], debug=DEBUG)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
