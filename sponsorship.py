from google.appengine.ext import ndb
from google.appengine.api import memcache

import tournament

# Sponsorship information.

class Sponsorship(ndb.Model):
	name = ndb.StringProperty()
	level = ndb.StringProperty()
	sequence = ndb.IntegerProperty()
	price = ndb.IntegerProperty()
	unique = ndb.BooleanProperty()
	sold = ndb.BooleanProperty()
	golfers_included = ndb.IntegerProperty()

# Get a list of sponsorships.

def get_sponsorships(level):
	t = tournament.get_tournament()
	sponsorships = memcache.get('%s/%s' % (t.name, level))
	if sponsorships is not None:
		return sponsorships
	q = Sponsorship.query(ancestor = t.key)
	if level != "all":
		q = q.filter(Sponsorship.level == level)
	q = q.order(Sponsorship.sequence)
	sponsorships = q.fetch(30)
	if not sponsorships:
		s = Sponsorship(parent = t.key, name = level, level = level, sequence = 1, price = 1000, unique = False, sold = False, golfers_included = 4)
		sponsorships.append(s)
	memcache.add('%s/%s' % (t.name, level), sponsorships, 60*60*24)
	return sponsorships

def clear_sponsorships_cache():
	t = tournament.get_tournament()
	memcache.delete_multi(["%s/all" % t.name,
						   "%s/Double Eagle" % t.name,
						   "%s/Hole in One" % t.name,
						   "%s/Eagle" % t.name,
						   "%s/Birdie" % t.name,
						   "%s/Angel" % t.name])
