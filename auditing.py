from google.appengine.api import users
from google.appengine.ext import ndb

class AuditEntry(ndb.Model):
	timestamp = ndb.DateTimeProperty(auto_now_add = True)
	user = ndb.StringProperty()
	tournament = ndb.StringProperty()
	sponsor_id = ndb.IntegerProperty()
	tribute_id = ndb.IntegerProperty()
	desc = ndb.StringProperty()
	data = ndb.TextProperty()
	ipaddr = ndb.StringProperty()
	location = ndb.StringProperty()

def get_audit_entries():
	return AuditEntry.query()

def audit(tournament, desc, sponsor_id = 0, tribute_id = 0, data = None, request = None):
	current_user = users.get_current_user()
	user = current_user.email() if current_user else "Guest"
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
	e = AuditEntry(user = user,
				   tournament = tname,
				   sponsor_id = sponsor_id,
				   tribute_id = tribute_id,
				   desc = desc,
				   data = data,
				   ipaddr = ipaddr,
				   location = location)
	e.put()
