import re
import datetime
import logging

def scrape_guardian(content):
  r = {}
  
  mo_date = re.search(r'<meta name="DC.date.issued" content="(\d\d\d\d)-(\d\d)-(\d\d)">', content)
  if mo_date:
    r['date'] = datetime.date(*map(int,mo_date.groups()))
  
  mo_author = re.search(r'''s\['prop6'\]="(.*)";''', content)
  if mo_author:
    r['author'] = mo_author.group(1)
  
  return r

def scrape_times(content):
  r = {}

  mo_date = re.search(r'Article Published Date : ([A-Z][a-z][a-z] \d\d?, \d\d\d\d)', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), "%b %d, %Y").date()

  mo_author = re.search(r'''Print Author name from By Line associated with the article -->\s*<span class="small"></span><span class="byline">\s*(.*)''', content)
  if mo_author:
    r['author'] = mo_author.group(1)

  return r

def scrape_bbc(content):
  r = {}

  mo_title = re.search(r'(?s)<title>(.*?)\s*</title>', content)
  if mo_title:
    r['title'] = re.sub(r'.*\|\s*', '', mo_title.group(1))
  
  mo_date = re.search(r'<meta name="OriginalPublicationDate" content="(\d\d\d\d)/(\d\d)/(\d\d)', content)
  if mo_date:
    r['date'] = datetime.date(*map(int,mo_date.groups()))
  
  mo_author = re.search(r'''<span class="byl">\s*By (.*)''', content)
  if mo_author:
    r['author'] = mo_author.group(1)
  
  return r

def scrape_express(content):
  r = {}

  mo_title = re.search(r'(?s)<title>(.*?)\s*</title>', content)
  if mo_title:
    r['title'] = re.sub(r'.*::\s*', '', mo_title.group(1))

  mo_date = re.search(r'<span class="datetime">([A-Z][a-z]+ \d\d?)(st|nd|rd|th)( [A-Z][a-z]+ \d\d\d\d)', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1) + mo_date.group(3), '%A %d %B %Y').date()

  mo_author = re.search(r'''By <span class="bold">([^<]+)''', content)
  if mo_author:
    r['author'] = mo_author.group(1)

  return r

def scrape_mail(content):
  r = {}

  mo = re.search(r'''class="author" rel="nofollow">([^<]+)</a><br>\s*Last updated at \d\d?:\d\d? [AP]M on (\d\d)(st|nd|rd|th)( [A-Z][a-z]+ \d\d\d\d)''', content)
  if mo:
    r['author'] = mo.group(1)
    r['date'] = datetime.datetime.strptime(mo.group(2) + mo.group(4), '%d %B %Y').date()

  return r

def scrape_cnet(content):
  r = {}

  mo_date = re.search(r'<div class="datestamp">\s*([A-Z][a-z]+ \d\d?, \d\d\d\d)', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), '%B %d, %Y').date()

  mo_author = re.search(r'''<div class="postByline">\s*<span class="author">\s*by\s+<a[^>]+>\s*([^<]+)''', content)
  if mo_author:
    r['author'] = mo_author.group(1)

  return r


scrapers = {
  "guardian.co.uk":     scrape_guardian,
  "news.bbc.co.uk":     scrape_bbc,
  "timesonline.co.uk":  scrape_times,
  "dailyexpress.co.uk": scrape_express,
  "dailymail.co.uk":    scrape_mail,
  "news.cnet.com":      scrape_cnet,
}

def scrape(host, content):
  host = re.sub(r'^www\.', '', host.lower())
  scraper = scrapers.get(host)
  if scraper is None:
    logging.info("No scraper found for %s", host)
    return {}
  else:
    metadata = scraper(content)
    logging.info("Scraped metadata: %s", metadata)
    return metadata