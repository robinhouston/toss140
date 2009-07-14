import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import memcache

import datetime
import logging
import os
import re
import urllib

import data

DEBUG = True
FETCH_SIZE = 20

TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')

FRONT_TEMPLATE     = os.path.join(TEMPLATES, 'front.tmpl')
ABOUT_TEMPLATE     = os.path.join(TEMPLATES, 'about.tmpl')
TIMELINE_TEMPLATE  = os.path.join(TEMPLATES, 'timeline.tmpl')
RECENT_TEMPLATE    = os.path.join(TEMPLATES, 'recent.tmpl')

AUTHOR_TEMPLATE    = os.path.join(TEMPLATES, 'author.tmpl')
TWEETER_TEMPLATE   = os.path.join(TEMPLATES, 'tweeter.tmpl')
ORGAN_TEMPLATE     = os.path.join(TEMPLATES, 'organ.tmpl')
DATE_TEMPLATE      = os.path.join(TEMPLATES, 'date.tmpl')
LINKLESS_TEMPLATE  = os.path.join(TEMPLATES, 'linkless.tmpl')


def articles_by_site_name(site_name):
  site = data.Site.all().filter('name =', site_name).get()
  if site is None:
    raise NotFound
  return articles_by_site(site)

def articles_by_site(site):
  return data.Article.all().ancestor(site).order('-date').fetch(FETCH_SIZE)

def articles_by_author(author):
  return data.Article.all().filter('author =', author).order('-date').fetch(FETCH_SIZE)

def tweets_by_tweeter(tweeter):
  return data.Tweet.all().filter('from_user =', tweeter).order('-created_at').fetch(FETCH_SIZE)

def _articles():
  return data.Article.all().order('-date').fetch(FETCH_SIZE)

def articles_by_date(date):
  logging.info("date = %s", str(date))
  return data.Article.all().filter('date =', date).order("-date").fetch(FETCH_SIZE)

def articles_up_to_date(date):
  return data.Article.all().filter('date <=', date).order("-date").fetch(FETCH_SIZE)

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

def _tweets():
  return data.Tweet.all().order("-created_at").fetch(FETCH_SIZE)

def tweets_without_link():
  return data.Tweet.all().filter("long_url =", None).order("-created_at").fetch(FETCH_SIZE)

def parse_iso_date(datestr):
  mo = re.match(r'^(\d\d\d\d)-(\d\d)-(\d\d)$', datestr)
  if not mo:
    raise NotFound
  return datetime.date(*map(int, mo.groups()))

class LoginHandler(webapp.RequestHandler):
  # This handler just redirects to the supplied URL.
  # The point is that /login as specified as login: admin in app.yaml,
  # so App Engine will make the user log in before we even get here.
  def get(self):
    url = self.request.get("r")
    if not url:
      url = '/'
    self.redirect(url)

class NotFound(Exception):
  '''Raised by a page handler if the requested resource is not found'''

class PageHandler(webapp.RequestHandler):
  '''Superclass for our page handlers.'''
  
  def _unquote(self, string):
    if string is None:
      return None
    else:
      return urllib.unquote(string)
  
  def get(self, *args):
    args = map(self._unquote, args)
    admin = self.request.get('admin')
    if admin and not users.is_current_user_admin():
      self.redirect("/login?r=" + urllib.quote(self.request.uri))
    
    memcache_key = self.memcache_key(*args)
    if admin:
      memcache_key = 'admin:' + memcache_key

    # At least on the dev server, self.request.uri contains the
    # URI of the original request, NOT of the target of the redirect,
    # even when we're processing the target of the redirect. (A bug?)
    uri = re.sub(r'[?&]refresh.*', '', self.request.uri)
    if self.request.get("refresh"):
      memcache.delete(memcache_key)
      self.redirect(uri)


    content = memcache.get(memcache_key)
    if content is None:
      logging.info("Rebuilding page for " + uri)
      template_path = self.template_path()
      try:
        template_args = self.template_args(*args)
      except NotFound:
        self.error(404)
        return
      
      template_args['debug'] = DEBUG
      template_args['admin'] = admin
      template_args['this_page'] = uri
      if admin:
        template_args['q'] = '?admin=1'
        template_args['refresh_url'] = uri + '&refresh=1'
        template_args['logout_url']  = users.create_logout_url(self.request.uri)
      else:
        template_args['q'] = ''
      content = template.render(template_path, template_args)
      memcache.add(key=memcache_key, value=content, time=self.memcache_time(*args))

    self.response.out.write(content)
  
  def memcache_time(*args):
    '''The default is no timeout.'''
    return 0

class AuthorHandler(PageHandler):
  def memcache_key(self, author):
    return "author=" + author

  def template_path(self):
    return AUTHOR_TEMPLATE
    
  def template_args(self, author):
    return {
      "author":   author,
      "articles": articles_by_author(author),
    }

class TweeterHandler(PageHandler):
  def memcache_key(self, tweeter):
    return "tweeter=" + tweeter

  def template_path(self):
    return TWEETER_TEMPLATE

  def template_args(self, tweeter):
    return {
      "tweeter": tweeter,
      "tweets":  tweets_by_tweeter(tweeter),
    }

class OrganHandler(PageHandler):
  def memcache_key(self, organ):
    return "organ=" + organ
    
  def template_path(self):
    return ORGAN_TEMPLATE

  def template_args(self, organ):
    return {
      "organ":    organ,
      "articles": articles_by_site_name(organ),
    }

class TimelineHandler(PageHandler):
  def memcache_key(self, date):
    if date is None:
      return "timeline"
    else:
      return "timeline=" + date
  
  def memcache_time(self, date):
    # Set an explicit timeout on the timeline-to-date page, because it's
    # tricky to expire these manually when a tweet is added. (How do you
    # know which keys are affected?)
    if date:
      return 900
    else:
      return 0
    
  def template_path(self):
    return TIMELINE_TEMPLATE

  def template_args(self, datestr):
    if datestr is None:
      articles = _articles()
      date = None
    else:
      date = parse_iso_date(datestr)
      articles = articles_up_to_date(date)
    return {
      "articles": articles,
      "date": date,
    }

class RecentHandler(PageHandler):
  def memcache_key(self):
    return "recent"

  def template_path(self):
    return RECENT_TEMPLATE

  def template_args(self):
    return {
      "tweets": _tweets(),
    }

class DateHandler(PageHandler):
  def memcache_key(self, date):
    return "date=" + date

  def template_path(self):
    return DATE_TEMPLATE

  def template_args(self, datestr):
    date = parse_iso_date(datestr)
    articles = articles_by_date(date)
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

class FrontHandler(PageHandler):
  def template_path(self):
    return FRONT_TEMPLATE

  def memcache_key(self):
    return "front"

  def template_args(self):
      logging.info("Rebuilding front page")
      return {
        "tweets":   _tweets(),
        "articles": _articles(),
        "front":    True,
      }


def main():
  application = webapp.WSGIApplication([
    ('/login',              LoginHandler),
                            
    ('/',                   FrontHandler),
    ('/about',              AboutHandler),
    ('/timeline(?:/(.+))?', TimelineHandler),
    ('/recent',             RecentHandler),
                            
    ('/author/([^/]+)',     AuthorHandler),
    ('/tweeter/([^/]+)',    TweeterHandler),
    ('/organ/([^/]+)',      OrganHandler),
    ('/date/([^/]+)',       DateHandler),
    ('/linkless',           LinklessHandler),
  ], debug=DEBUG)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
