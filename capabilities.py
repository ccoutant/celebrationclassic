from google.appengine.api import users, memcache
from google.appengine.ext import db

import tournament

# Users who can update parts of the site.

class Capabilities(db.Model):
	email = db.EmailProperty()
	can_update_sponsorships = db.BooleanProperty(default = False)
	can_view_registrations = db.BooleanProperty(default = False)
	can_add_registrations = db.BooleanProperty(default = False)
	can_update_auction = db.BooleanProperty(default = False)
	can_edit_content = db.BooleanProperty(default = False)
	can_edit_tournament_properties = db.BooleanProperty(default = False)
	can_edit_payment_processor = db.BooleanProperty(default = False)

def get_current_user_caps():
	user = users.get_current_user()
	if not user:
		return Capabilities(email = None)
	email = user.email()
	caps = memcache.get('2019/caps/' + email.lower())
	if caps is not None:
		return caps
	else:
		t = tournament.get_tournament()
		q = Capabilities.all()
		q.ancestor(t)
		q.filter("email = ", email.lower())
		caps = q.get()
		if caps:
			memcache.add('2019/caps/' + email.lower(), caps, 60*60)
			return caps
		return Capabilities(email = None)
