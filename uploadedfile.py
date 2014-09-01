from google.appengine.ext import db, blobstore

class UploadedFile(db.Model):
	name = db.StringProperty(required = True)
	path = db.StringProperty()
	blob = blobstore.BlobReferenceProperty()
	last_modified = db.DateTimeProperty(required = True, auto_now = True)
