import logging
from google.appengine.api import users, memcache
from google.appengine.ext import db

import tournament
import auditing

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

	def to_string(self):
		return (("US" if self.can_update_sponsorships else "us") + "," +
				("VR" if self.can_view_registrations else "vr") + "," +
				("AR" if self.can_add_registrations else "ar") + "," +
				("UA" if self.can_update_auction else "ua") + "," +
				("EC" if self.can_edit_content else "ec") + "," +
				("ET" if self.can_edit_tournament_properties else "et") + "," +
				("PP" if self.can_edit_payment_processor else "pp"))

	def audit(self):
		auditing.audit(None, "Updated Admin " + self.email, data = self.to_string())

def all_caps():
	return Capabilities.all().ancestor(db.Key.from_path('Root', 'CC'))

def get_caps(email):
	caps = memcache.get('caps/' + email.lower())
	if caps is not None:
		return caps
	q = all_caps()
	q.filter("email = ", email.lower())
	caps = q.get()
	if caps:
		memcache.add('caps/' + email.lower(), caps, 60*60)
		return caps
	return Capabilities(email = None)

def get_current_user_caps():
	user = users.get_current_user()
	if not user:
		return Capabilities(email = None)
	caps = get_caps(user.email())
	# logging.debug("get_current_user_caps: " + caps.to_string())
	return caps

def add_user(email, can_update_sponsorships, can_view_registrations,
			 can_add_registrations, can_update_auction, can_edit_content,
			 can_edit_tournament_properties, can_edit_payment_processor):
	caps = Capabilities(parent = db.Key.from_path('Root', 'CC'),
						email = email.lower(),
						can_update_sponsorships = can_update_sponsorships,
						can_view_registrations = can_view_registrations,
						can_add_registrations = can_add_registrations,
						can_update_auction = can_update_auction,
						can_edit_content = can_edit_content,
						can_edit_tournament_properties = can_edit_tournament_properties,
						can_edit_payment_processor = can_edit_payment_processor)
	caps.put()
	auditing.audit(None, "Added Admin " + caps.email, data = caps.to_string())
