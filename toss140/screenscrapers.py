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
    author = mo_author.group(1)
    author = re.sub(r'\s+\(contributor\)$', '', author)
    r['author'] = author
  
  return r

def scrape_times(content):
  r = {}

  mo_date = re.search(r'Article Published Date : (\d\d-[A-Z][a-z][a-z]-\d\d\d\d)', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), "%d-%b-%Y").date()
  else:
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

  # At the time of writing there's no space between the comma and the year,
  # but that seems like something they might fix, so we allow for spaces there.
  mo_date = re.search(r'<p class="date">\s*([A-Z][a-z]+ [A-Z][a-z]+ \d+),\s*(\d\d\d\d)', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1) + ' ' + mo_date.group(2), '%A %B %d %Y').date()

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
  
  # Stephen Glover is special
  elif re.search(r'<meta name="divclassbody" content="stephen-glover" />', content):
    r['author'] = 'Stephen Glover'
    mo = re.search(r'''Last updated at \d\d?:\d\d? [AP]M on (\d\d)(st|nd|rd|th)( [A-Z][a-z]+ \d\d\d\d)''', content)
    if mo:
      r['date'] = datetime.datetime.strptime(mo.group(1) + mo.group(3), '%d %B %Y').date()
  
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

def scrape_independent(content):
  # Only works for /opinion/commentators at the moment
  r = {}
  
  mo_date = re.search(r'<meta name="icx_pubdate" content="(\d\d/\d\d/\d\d\d\d)"/>', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), '%d/%m/%Y').date()
  
  if re.search(r'''var contextName = 'independent_www_opinion_commentators';''', content):
    mo_commentator = re.search(r'<meta name="icx_section" content="([^"]+)"/>', content)
    if mo_commentator:
      r['author'] = mo_commentator.group(1)
  
  return r

def scrape_telegraph(content):
  r = {}
  
  mo_author = re.search(r'<meta name="author" content="By ([^"]+\S)\s*" />', content)
  if mo_author:
    r['author'] = mo_author.group(1)
  
  mo_date = re.search(r'meta name="DC.date.issued" content="(\d\d\d\d-\d\d-\d\d)" />', content)
  if mo_author:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), '%Y-%m-%d').date()

  mo_title = re.search(r'(?s)<title>\s*(.*?)\s* - Telegraph</title>', content)
  if mo_title:
    r['title'] = mo_title.group(1)

  return r

def scrape_telegraph_blogs(content):
  r = {}
  
  mo_author = re.search(r'<span class="byAuthor">By <a[^>]+>([^<]+)', content)
  if mo_author:
    r['author'] = mo_author.group(1)
  
  mo_date = re.search(r'meta name="DC.date.issued" content="(\d\d\d\d-\d\d-\d\d)" />', content)
  if mo_author:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), '%Y-%m-%d').date()

  mo_title = re.search(r'(?s)<title>\s*(.*?)\s* - Telegraph Blogs</title>', content)
  if mo_title:
    r['title'] = mo_title.group(1)

  return r

def scrape_newscientist(content):
  r = {}

  mo_author = re.search(r'<meta name="rbauthors" content="([^"]+\S)\s*" />', content)
  if mo_author:
    r['author'] = mo_author.group(1)

  mo_date = re.search(r'<meta name="rbpubdate" content="(\d\d\d\d-\d\d-\d\d)', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), '%Y-%m-%d').date()

  mo_title = re.search(r'<meta name="rbtitle" content="([^"]+\S)\s*" />', content)
  if mo_title:
    r['title'] = mo_title.group(1)

  return r

def scrape_irishtimes(content):
  r = {}
  
  mo_author = re.search(r'writes ([A-Z]+ )?\n<strong>([^<]+)</strong>&#160;\.</p>', content)
  if mo_author:
    if mo_author.group(1):
      author_allcaps = mo_author.group(1) + mo_author.group(2)
    else:
      author_allcaps = mo_author.group(2)
    r['author'] = re.sub(r'[A-Z]+', lambda m: unicode.capitalize(m.group(0)), author_allcaps)
  
  # <span class="date-info">Friday, July 17, 2009</span>
  mo_date = re.search(r'<span class="date-info">([A-Z][a-z]+, [A-Z][a-z]+ \d\d?, \d\d\d\d)</span>', content)
  if mo_date:
    r['date'] = datetime.datetime.strptime(mo_date.group(1), '%A, %B %d, %Y').date()
    
  mo_title = re.search(r'''var it_headline = '(.*)';''', content)
  if mo_title:
    r['title'] = mo_title.group(1)
  
  return r

scrapers = {
  "guardian.co.uk":     scrape_guardian,
  "independent.co.uk":  scrape_independent,
  "news.bbc.co.uk":     scrape_bbc,
  "timesonline.co.uk":  scrape_times,
  "dailyexpress.co.uk": scrape_express,
  "dailymail.co.uk":    scrape_mail,
  "telegraph.co.uk":    scrape_telegraph,
  "blogs.telegraph.co.uk": scrape_telegraph_blogs,
  "news.cnet.com":      scrape_cnet,
  "newscientist.com":   scrape_newscientist,
  "irishtimes.com":     scrape_irishtimes,
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