import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import memcache

import logging
import os
import re
import urllib

import data

DEBUG = True
FETCH_SIZE = 20

FRONT_TEMPLATE     = os.path.join(os.path.dirname(__file__), 'templates', 'front.tmpl')
AUTHOR_TEMPLATE    = os.path.join(os.path.dirname(__file__), 'templates', 'author.tmpl')
TWEETER_TEMPLATE   = os.path.join(os.path.dirname(__file__), 'templates', 'tweeter.tmpl')
ORGAN_TEMPLATE     = os.path.join(os.path.dirname(__file__), 'templates', 'organ.tmpl')
TIMELINE_TEMPLATE  = os.path.join(os.path.dirname(__file__), 'templates', 'timeline.tmpl')


def tweets_by_site_name(site_name):
  site = data.Site.all().filter('name =', site_name).get()
  if site is None:
    raise NotFound
  return tweets_by_site(site)

def tweets_by_site(site):
  articles = data.Article.all().ancestor(site).order('-date').fetch(FETCH_SIZE)
  logging.debug("Fetched %d articles with site '%s'", len(articles), site.name)
  tweets = []
  for article in articles:
    for tweet in data.Tweet.all().filter('article =', article).order('-created_at'):
      if not tweet.is_retweet:
        tweets.append(tweet)
  return tweets

def tweets_by_author(author):
  articles = data.Article.all().filter('author =', author).order('-date').fetch(FETCH_SIZE)
  logging.debug("Fetched %d articles with author '%s'", len(articles), author)
  tweets = []
  for article in articles:
    for tweet in data.Tweet.all().filter('article =', article).order('-created_at'):
      if not tweet.is_retweet:
        tweets.append(tweet)
  return tweets

def tweets_by_tweeter(tweeter):
  return data.Tweet.all().filter('from_user =', tweeter).order('-created_at').fetch(FETCH_SIZE)

def tweets_grouped_by_article():
  articles = data.Article.all().order('-date').fetch(FETCH_SIZE)
  logging.debug("Fetched %d articles for timeline", len(articles))
  r = []
  for article in articles:
    r.append({
      "article": article,
      "tweets":  data.Tweet.all().filter('article =', article).order('-created_at').fetch(FETCH_SIZE)
    })
  return r

def recent_tweets():
  return data.Tweet.all().order("-created_at").fetch(FETCH_SIZE)

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
  def get(self, *args):
    admin = self.request.get('admin')
    if admin and not users.is_current_user_admin():
      self.redirect("/login?r=" + urllib.urlencode(self.request.uri))
    
    memcache_key = self.memcache_key(*args)
    if admin:
      memcache_key = 'admin:' + memcache_key
    
    if self.request.get("refresh"):
      memcache.delete(memcache_key)
      self.redirect(re.sub(r'[?&]refresh.*', '', self.request.uri))

    content = memcache.get(memcache_key)
    if content is None:
      logging.info("Rebuilding page for " + self.request.uri)
      template_path = self.template_path()
      try:
        template_args = self.template_args(*args)
      except NotFound:
        self.error(404)
        return
      
      template_args['debug'] = DEBUG
      template_args['admin'] = admin
      template_args['this_page'] = self.request.uri
      if admin:
        template_args['logout_url'] = users.create_logout_url(self.request.uri)
      content = template.render(template_path, template_args)
      memcache.add(key=memcache_key, value=content, time=900)

    self.response.out.write(content)
    

class FrontHandler(PageHandler):
  def template_path(self):
    return FRONT_TEMPLATE
  
  def memcache_key(self):
    return "front"

  def template_args(self):
      logging.info("Rebuilding front page")
      return {
        "recent":   recent_tweets(),
        "timeline": tweets_grouped_by_article(),
      }

class AuthorHandler(PageHandler):
  def memcache_key(self, author):
    return "author=" + author

  def template_path(self):
    return AUTHOR_TEMPLATE
    
  def template_args(self, author):
    author_decoded = urllib.unquote(author)
    return {
      "author": author_decoded,
      "tweets": tweets_by_author(author_decoded),
    }

class TweeterHandler(PageHandler):
  def memcache_key(self, tweeter):
    return "tweeter=" + tweeter

  def template_path(self):
    return TWEETER_TEMPLATE

  def template_args(self, tweeter):
    tweeter_decoded = urllib.unquote(tweeter)
    return {
      "tweeter": tweeter_decoded,
      "tweets":  tweets_by_tweeter(tweeter_decoded),
    }

class OrganHandler(PageHandler):
  def memcache_key(self, organ):
    return "organ=" + organ
    
  def template_path(self):
    return ORGAN_TEMPLATE

  def template_args(self, organ):
    organ_decoded = urllib.unquote(organ)

    return {
      "organ": organ_decoded,
      "tweets": tweets_by_site_name(organ_decoded),
    }

class TimelineHandler(PageHandler):
  def memcache_key(self):
    return "timeline"
    
  def template_path(self):
    return TIMELINE_TEMPLATE

  def template_args(self):
    return {
      "list": tweets_grouped_by_article(),
    }


def main():
  application = webapp.WSGIApplication([
    ('/login',           LoginHandler),
    ('/',                FrontHandler),
    ('/author/([^/]+)',  AuthorHandler),
    ('/tweeter/([^/]+)', TweeterHandler),
    ('/organ/([^/]+)',   OrganHandler),
    ('/timeline',        TimelineHandler),
  ], debug=DEBUG)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
