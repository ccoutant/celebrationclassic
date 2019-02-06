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
	ipaddr = db.StringProperty()
	location = db.StringProperty()

def get_audit_entries():
	root = db.Key.from_path('Root', 'CC')
	return AuditEntry.all().ancestor(root)

def audit(tournament, desc, sponsor_id = 0, tribute_id = 0, data = None, request = None):
	root = db.Key.from_path('Root', 'CC')
	current_user = users.get_current_user()
	tname = tournament.name if tournament else ""
	if request:
		ipaddr = request.remote_addr
		location = "%s / %s / %s / %s" % (request.headers.get("X-AppEngine-CityLatLong"),
									 request.headers.get("X-AppEngine-Country"),
									 request.headers.get("X-AppEngine-Region"),
									 request.headers.get("X-AppEngine-City"))
	else:
		ipaddr = ""
		location = ""
	e = AuditEntry(parent = root,
				   user = current_user.email() if current_user else "Guest",
				   tournament = tname,
				   sponsor_id = sponsor_id,
				   tribute_id = tribute_id,
				   desc = desc,
				   data = data,
				   ipaddr = ipaddr,
				   location = location)
	e.put()
