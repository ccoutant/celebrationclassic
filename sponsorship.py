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
	sponsorships = memcache.get('2019/' + level)
	if sponsorships is not None:
		return sponsorships
	root = tournament.get_tournament()
	q = Sponsorship.all()
	q.ancestor(root)
	if level != "all":
		q.filter("level = ", level)
	q.order("sequence")
	sponsorships = q.fetch(30)
	if not sponsorships:
		s = Sponsorship(parent = root, name = level, level = level, sequence = 1, price = 1000, unique = False, sold = False, golfers_included = 4)
		sponsorships.append(s)
	memcache.add('2019/' + level, sponsorships, 60*60*24)
	return sponsorships

def clear_sponsorships_cache():
	memcache.delete_multi(["2019/all","2019/Double Eagle","2019/Hole in One","2019/Eagle","2019/Under Par","2019/Angel"])
