#!/usr/bin/env python

import logging
import webapp2
from google.appengine.ext import db, blobstore
from google.appengine.ext.webapp import blobstore_handlers

import uploadedfile

class ServeFileHandler(blobstore_handlers.BlobstoreDownloadHandler):
	def get(self, name):
		query = uploadedfile.UploadedFile.all()
		query.filter("path = ", name)
		item = query.get()
		if item:
			if item.blob:
				self.send_blob(item.blob)
			else:
				self.response.headers['Content-Type'] = 'image/jpeg'
				self.response.headers['Cache-Control'] = 'public, max-age=86400;'
				self.response.out.write(item.contents)
		else:
			self.error(404)
			self.response.out.write('<html><head>\n')
			self.response.out.write('<title>404 Not Found</title>\n')
			self.response.out.write('</head><body>\n')
			self.response.out.write('<h1>Not Found</h1>\n')
			self.response.out.write('<p>The requested page "%s" was not found on this server.</p>\n' % name)
			self.response.out.write('</body></html>\n')

app = webapp2.WSGIApplication([('(/photos/.*)', ServeFileHandler),
							   ('(/files/.*)', ServeFileHandler)],
							  debug=True)
