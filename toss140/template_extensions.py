from django import template
from django.template.defaultfilters import stringfilter
from google.appengine.api import memcache
from google.appengine.ext import webapp

import logging
import urllib
 
register = webapp.template.create_template_register()

@register.filter
@stringfilter
def urlenc_uni(value):
  return urllib.quote(value.encode('utf-8'))

@register.tag
def cached(parser, token):
  nodelist = parser.parse(('endcached',))
  parser.delete_first_token()
  return CachedNode(nodelist)

class CachedNode(template.Node):
  def __init__(self, nodelist):
    self.nodelist = nodelist
  def render(self, context):
    memcache_key = context.get('memcache_key')
    memcache_time = context.get('memcache_time')
    output = memcache.get(memcache_key)
    if output:
      return output
    
    logging.info("Rebuilding page for key " + memcache_key)
    output = self.nodelist.render(context)
    memcache.add(key=memcache_key, value=output, time=memcache_time)
    
    return output