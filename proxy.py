#!/usr/bin/env python

import logging
import datetime
import webapp2
from google.appengine.ext import db
from google.appengine.api import users, urlfetch

HTTP_DATE_FMT = "%a, %d %b %Y %H:%M:%S GMT"

class CachedFile(db.Model):
	name = db.StringProperty(required = True)
	content_type = db.StringProperty()
	content = db.BlobProperty()
	last_modified = db.DateTimeProperty(required = True, auto_now = True)

class CacheHandler(webapp2.RequestHandler):
	def get(self):
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url(self.request.uri))
			return
		objs = CachedFile.all()
		self.response.out.write('<html>\n')
		self.response.out.write('<body>\n')
		self.response.out.write('<h1>Cached Files</h1>\n')
		self.response.out.write('<ul>\n')
		for obj in objs:
			self.response.out.write('<li><a href="%s">%s</a> %s (%d bytes)</li>\n' % (obj.name, obj.name, obj.content_type, len(obj.content)))
		self.response.out.write('</ul>\n')
		self.response.out.write('<form action="/clearcache" method="post">')
		self.response.out.write('<input type="submit" value="Clear Cache">')
		self.response.out.write('</form>\n')
		self.response.out.write('</body>\n')
		self.response.out.write('</html>\n')

class ClearCacheHandler(webapp2.RequestHandler):
	def post(self):
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url(self.request.uri))
			return
		objs = CachedFile.all()
		for obj in objs:
			obj.delete()
		self.response.out.write('<html>\n')
		self.response.out.write('<body>\n')
		self.response.out.write('<h1>Cache Cleared</h1>\n')
		self.response.out.write('<p><a href="/cache">Cache</a></p>\n')
		self.response.out.write('</body>\n')
		self.response.out.write('</html>\n')

class ProxyHandler(webapp2.RequestHandler):
	def get(self, name):
		query = CachedFile.all()
		query.filter("name = ", name)
		cached = query.get()
		if cached:
			ctype = cached.content_type
			content = cached.content
			logging.debug("Found cached object for %s, Content-Type %s, length %d" % (name, ctype, len(content)))
		else:
			url = 'http://www1.shirhadash.org/celebrationclassic/' + name
			result = urlfetch.fetch(url)
			if result.status_code != 200:
				self.error(result.status_code)
				self.response.out.write('<html><head>\n')
				self.response.out.write('<title>404 Not Found</title>\n')
				self.response.out.write('</head><body>\n')
				self.response.out.write('<h1>Not Found</h1>\n')
				self.response.out.write('<p>The requested URL %s was not found on this server.</p>\n' % name)
				self.response.out.write('</body></html>\n')
				return
			ctype = result.headers['Content-Type']
			content = db.Blob(result.content)
			cached = CachedFile(name = name, content_type = ctype, content = content)
			cached.put()
			logging.debug("Saved cached object for %s, Content-Type %s, length %d" % (name, ctype, len(content)))
		last_modified = cached.last_modified.strftime(HTTP_DATE_FMT)
		self.response.headers['Last-Modified'] = last_modified
		self.response.headers['Content-Type'] = str(ctype)
		self.response.headers['Cache-Control'] = 'public, max-age=900;'
		modified = True
		if 'If-Modified-Since' in self.request.headers:
			try:
				last_seen = datetime.datetime.strptime(self.request.headers['If-Modified-Since'].strip(), HTTP_DATE_FMT)
				if last_seen >= cached.last_modified.replace(microsecond=0):
					modified = False
			except ValueError:
				pass
		if modified:
			self.response.out.write(content)
		else:
			self.response.set_status(304)

app = webapp2.WSGIApplication([('/cache', CacheHandler),
							   ('/clearcache', ClearCacheHandler),
							   (r'/(images/.*)', ProxyHandler),
							   (r'/(photos/.*)', ProxyHandler),
							   (r'/([^/]+\.html)', ProxyHandler),
							   (r'/([^/]+\.css)', ProxyHandler)],
							  debug=True)
