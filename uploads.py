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
			self.send_blob(item.blob)
		else:
			self.error(404)

app = webapp2.WSGIApplication([('(/photos/.*)', ServeFileHandler),
							   ('(/files/.*)', ServeFileHandler)],
							  debug=True)
