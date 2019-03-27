#!/usr/bin/env python

import os
import logging
import webapp2
import json
from google.appengine.api import urlfetch

from HTMLParser import HTMLParser

import tournament
import auditing

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

# Parser for the response from the NCGA GHIN number lookup widget.
# We scrape the HTML response for the golfer's name, GHIN number,
# club name, handicap index, and effective date.
# The last three items may be repeated.

class NCGAResponseParser(HTMLParser):
	def __init__(self):
		HTMLParser.__init__(self)
		self.current_tag = ""
		self.current_id = ""
		self.current_class = ""
		self.name = ""
		self.ghin = ""
		self.club = ""
		self.index = ""
		self.rows = []

	def handle_starttag(self, tag, attrs):
		if tag == "span":
			self.current_tag = tag
			dattrs = dict(attrs)
			if "id" in dattrs:
				self.current_id = dattrs["id"]
		elif tag == "td":
			self.current_tag = tag
			dattrs = dict(attrs)
			if "class" in dattrs:
				self.current_class = dattrs["class"]
		elif tag == "br":
			if self.current_tag == "td" and self.current_class == "ClubGridClub":
				self.club += "/"

	def handle_endtag(self, tag):
		if tag == "span" or tag == "td":
			self.current_tag = ""
			self.current_id = ""
			self.current_class = ""

	def handle_data(self, data):
		if self.current_tag == "span" and self.current_id == "ctl00_bodyMP_lblName":
			self.name = data.strip()
		elif self.current_tag == "span" and self.current_id == "ctl00_bodyMP_lblGHIN":
			self.ghin = data.strip()
		elif self.current_tag == "td" and self.current_class == "ClubGridClub":
			self.club += data.strip()
		elif self.current_tag == "td" and self.current_class == "ClubGridHandicapIndex":
			self.index = data.strip()
		elif self.current_tag == "td" and self.current_class == "ClubGridEffectiveDate":
			row = (self.club, self.index, data.strip())
			self.rows.append(row)
			self.club = ""
			self.index = ""

class GHINLookup(webapp2.RequestHandler):
	def get(self, ghin):
		t = tournament.get_tournament()
		url = 'http://widgets.ghin.com/HandicapLookupResults.aspx?ghinno=%s&showheader=0&showheadertext=0&showfootertext=0' % ghin
		logging.debug('Fetching %s' % url)
		try:
			result = urlfetch.fetch(url)
			if result.status_code == 200:
				content = result.content
			else:
				logging.debug('Returned status %d' % result.status_code)
				self.response.status_code = result.status_code
				return
		except urlfetch.Error:
			logging.exception('Caught exception fetching url')
			return
		parser = NCGAResponseParser()
		parser.feed(content)
		parser.close()
		response = {
			"name": parser.name,
			"ghin": parser.ghin,
			"rows": parser.rows
		}
		self.response.headers["Content-Type"] = "text/json; charset=utf-8"
		self.response.out.write(json.dumps(response))

app = webapp2.WSGIApplication([('/ghin-lookup/(.*)', GHINLookup)],
							  debug=dev_server)
