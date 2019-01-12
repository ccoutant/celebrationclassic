from google.appengine.api import users
from google.appengine.ext import db

class AuditEntry(db.Model):
	timestamp = db.DateTimeProperty(auto_now_add = True)
	user = db.StringProperty()
	tournament = db.StringProperty()
	sponsor_id = db.IntegerProperty()
	tribute_id = db.IntegerProperty()
	desc = db.StringProperty()
	data = db.TextProperty()

def get_audit_entries():
	root = db.Key.from_path('Root', 'CC')
	return AuditEntry.all().ancestor(root)

def audit(tournament, desc, sponsor_id = 0, tribute_id = 0, data = None):
	root = db.Key.from_path('Root', 'CC')
	current_user = users.get_current_user()
	tname = tournament.name if tournament else ""
	e = AuditEntry(parent = root,
				   user = current_user.email() if current_user else "Guest",
				   tournament = tname,
				   sponsor_id = sponsor_id,
				   tribute_id = tribute_id,
				   desc = desc,
				   data = data)
	e.put()
