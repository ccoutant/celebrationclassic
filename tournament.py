import datetime
from google.appengine.ext import db
from google.appengine.api import memcache

class Tournament(db.Model):
	name = db.StringProperty()
	early_bird_deadline = db.DateProperty()
	golf_price_early = db.IntegerProperty()
	golf_price_late = db.IntegerProperty()
	dinner_price_early = db.IntegerProperty()
	dinner_price_late = db.IntegerProperty()

def get_tournament():
	t = memcache.get("tournament")
	if t is not None:
		return t
	q = Tournament.all()
	q.filter("name = ", "cc2013")
	t = q.get()
	if t is not None:
		memcache.add("tournament", t, 60*60*24)
		return t
	t = Tournament(name = "cc2013",
				   early_bird_deadline = datetime.date(2013, 9, 3),
				   golf_price_early = 400,
				   golf_price_late = 450,
				   dinner_price_early = 150,
				   dinner_price_late = 175)
	t.put()
	memcache.add("tournament", t, 60*60*24)
	return t

def clear_tournament_cache():
	memcache.delete("tournament")
