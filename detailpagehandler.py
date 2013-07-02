#!/usr/bin/env python

import logging
import datetime
import webapp2
from google.appengine.ext import db
from google.appengine.api import users, memcache, urlfetch
from django.template.loaders.filesystem import Loader
from django.template.loader import render_to_string

import tournament
import detailpage
import capabilities

HTTP_DATE_FMT = "%a, %d %b %Y %H:%M:%S GMT"

class PageHandler(webapp2.RequestHandler):
	def get(self, name):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		page = detailpage.get_detail_page(name, False)
		if page is None:
			self.error(404)
			self.response.out.write('<html><head>\n')
			self.response.out.write('<title>404 Not Found</title>\n')
			self.response.out.write('</head><body>\n')
			self.response.out.write('<h1>Not Found</h1>\n')
			self.response.out.write('<p>The requested URL %s.html was not found on this server.</p>\n' % name)
			self.response.out.write('</body></html>\n')
			return
		last_modified = page.last_modified.strftime(HTTP_DATE_FMT)
		self.response.headers['Last-Modified'] = last_modified
		self.response.headers['Content-Type'] = 'text/html'
		self.response.headers['Cache-Control'] = 'public, max-age=900;'
		modified = True
		if 'If-Modified-Since' in self.request.headers:
			try:
				last_seen = datetime.datetime.strptime(self.request.headers['If-Modified-Since'].strip(), HTTP_DATE_FMT)
				if last_seen >= page.last_modified.replace(microsecond=0):
					modified = False
			except ValueError:
				pass
		if modified:
			template_values = {
				'page': page,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('detailpage.html', template_values))
		else:
			self.response.set_status(304)

app = webapp2.WSGIApplication([(r'/(.*)\.html', PageHandler)],
							  debug=True)
