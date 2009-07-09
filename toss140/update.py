import logging

import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.api.labs import taskqueue

import data
import twitter

# DeadlineExceededError can live in two different places 
try: 
  # When deployed 
  from google.appengine.runtime import DeadlineExceededError 
except ImportError: 
  # In the development server 
  from google.appengine.runtime.apiproxy_errors import DeadlineExceededError 


class UpdateHandler(webapp.RequestHandler):
  
  _queue   = taskqueue.Queue(name='add-tweet')
  
  def get(self):
    tweets = twitter.new_tweets()
    max_id = 1
    for tweet in tweets:
      if tweet['id'] > max_id:
        max_id = tweet['id']
      task = taskqueue.Task(url='/do/add-tweet', countdown=0, method='POST', params=tweet)
      self._queue.add(task)
    
    stats = {"n": len(tweets), "max_id": max_id}
    if stats['n'] > 0:
      twitter.update_stats(**stats)
  
    self.response.out.write("Queued %d tweets\n" % stats['n'])

class AddTweetHandler(webapp.RequestHandler):
  def post(self):
    tweet = {}
    for k, v in self.request.params.iteritems():
      tweet[str(k)] = unicode(v)
    logging.debug("add-tweet: storing %s", tweet)
    twitter.store_tweet(tweet)

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
    twitter.index(tweet)
    tweet.put()
  
  def get(self):
    self.post()
    self.redirect('/')

def main():
  application = webapp.WSGIApplication([
    ('/do/update', UpdateHandler),
    ('/do/add-tweet', AddTweetHandler),
    ('/do/index-tweets', IndexTweetsHandler),
    ('/do/index-tweet',  IndexTweetHandler),
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
