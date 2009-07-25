import base64
import hashlib
import hmac
import os
import time
import urllib


# url escape
def escape(s):
    # escape '/' too
    return urllib.quote(s, safe='~')

def urlencode(params):
  '''Similar to urllib.urlencode, but using %20 rather than + for a space
  to conform the the OAuth specification.'''
  a = []
  for k, v in params:
    a.append(escape(k) + '=' + escape(v))
  return str.join('&', a)

class OAuth(object):
  def __init__(self, consumer_key, consumer_secret):
    self.consumer_key = consumer_key
    self.consumer_secret = consumer_secret

  def _signature(self, url, params, method='POST', secret=''):
    key = self.consumer_secret + '&' + secret
    string_to_sign = method + '&' + escape(url) + '&' + escape(urlencode(params))
    return base64.b64encode(hmac.new(key, string_to_sign, hashlib.sha1).digest())

  def _params(self, url, token=None, secret='', *args):
    params = [
      ("oauth_consumer_key", self.consumer_key),
      ("oauth_nonce", base64.urlsafe_b64encode(os.urandom(32))),
      ("oauth_signature_method", "HMAC-SHA1"),
      ("oauth_timestamp", str(int(time.time()))),
    ]

    if token:
      params.append(("oauth_token", token))
    params += args
    params.append( ("oauth_signature", self._signature(url, params, secret=secret)) )
    return urllib.urlencode(params)

  def oauth_request(self, url, *args, **kwargs):
    f = urllib.urlopen(url, self._params(url, *args, **kwargs))
    return f.read()
