from google.appengine.ext import ndb

class UploadedFile(ndb.Model):
	name = ndb.StringProperty(required = True)
	path = ndb.StringProperty()
	contents = ndb.BlobProperty()
	last_modified = ndb.DateTimeProperty(required = True, auto_now = True)
