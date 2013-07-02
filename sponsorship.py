from google.appengine.ext import db
from google.appengine.api import memcache

import tournament

# Sponsorship information.

class Sponsorship(db.Model):
	name = db.StringProperty()
	level = db.StringProperty()
	sequence = db.IntegerProperty()
	price = db.IntegerProperty()
	unique = db.BooleanProperty()
	sold = db.BooleanProperty()

# Get a list of sponsorships.

def get_sponsorships(level):
	sponsorships = memcache.get(level)
	if sponsorships is not None:
		return sponsorships
	root = tournament.get_tournament()
	q = Sponsorship.all()
	q.ancestor(root)
	if level != "all":
		q.filter("level = ", level)
	q.order("sequence")
	sponsorships = q.fetch(30)
	memcache.add(level, sponsorships, 60*60*24)
	return sponsorships

def clear_sponsorships_cache():
	memcache.delete_multi(["all","Double Eagle","Hole in One","Eagle","Under Par","Angel"])
