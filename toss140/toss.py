import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.api import memcache

import os

import data

DEBUG = True
FRONT_TEMPLATE = os.path.join(os.path.dirname(__file__), 'templates', 'front.tmpl')


class MainHandler(webapp.RequestHandler):

  def get(self):
    admin = users.is_current_user_admin()
    memcache_key = "front_page.ordinary"
    if admin:
      memcache_key = "front_page.admin"
    
    content = memcache.get(memcache_key)
    if content is None:
      tweets = data.Tweet.all().order("-created_at")
      template_args = {
        "debug": DEBUG,
        "tweets": tweets,
        "admin": admin,
      }
      content = template.render(FRONT_TEMPLATE, template_args)
      memcache.add(key=memcache_key, value=content, time=900)
      
    self.response.out.write(content)


def main():
  application = webapp.WSGIApplication([('/', MainHandler)], debug=DEBUG)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
