from google.appengine.ext import webapp

import logging
import urllib
 
register = webapp.template.create_template_register()

def urlenc_uni(value):
  return urllib.quote(value.encode('utf-8'))

register.filter(urlenc_uni)
