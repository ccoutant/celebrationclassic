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
	golfers_included = db.IntegerProperty()

# Get a list of sponsorships.

def get_sponsorships(level):
	root = tournament.get_tournament()
	sponsorships = memcache.get('%s/%s' % (root.name, level))
	if sponsorships is not None:
		return sponsorships
	q = Sponsorship.all()
	q.ancestor(root)
	if level != "all":
		q.filter("level = ", level)
	q.order("sequence")
	sponsorships = q.fetch(30)
	if not sponsorships:
		s = Sponsorship(parent = root, name = level, level = level, sequence = 1, price = 1000, unique = False, sold = False, golfers_included = 4)
		sponsorships.append(s)
	memcache.add('%s/%s' % (root.name, level), sponsorships, 60*60*24)
	return sponsorships

def clear_sponsorships_cache():
	root = tournament.get_tournament()
	memcache.delete_multi(["%s/all" % root.name,
						   "%s/Double Eagle" % root.name,
						   "%s/Hole in One" % root.name,
						   "%s/Eagle" % root.name,
						   "%s/Birdie" % root.name,
						   "%s/Angel" % root.name])
