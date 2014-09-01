import datetime
from google.appengine.ext import db
from google.appengine.api import memcache

class Tournament(db.Model):
	name = db.StringProperty()
	golf_date = db.DateProperty()
	dinner_date = db.DateProperty()
	early_bird_deadline = db.DateProperty()
	golf_price_early = db.IntegerProperty()
	golf_price_late = db.IntegerProperty()
	dinner_price_early = db.IntegerProperty()
	dinner_price_late = db.IntegerProperty()
	golf_sold_out = db.BooleanProperty(default = False)
	dinner_sold_out = db.BooleanProperty(default = False)
	course_rating = db.FloatProperty(default = 72.0)
	course_slope = db.FloatProperty(default = 113.0)

def get_tournament():
	t = memcache.get("2015/tournament")
	if t is not None:
		return t
	q = Tournament.all()
	q.filter("name = ", "cc2015")
	t = q.get()
	if t is not None:
		memcache.add("2015/tournament", t, 60*60*24)
		return t
	t = Tournament(name = "cc2015",
				   golf_date = datetime.date(2015, 5, 18),
				   dinner_date = datetime.date(2015, 5, 318),
				   early_bird_deadline = datetime.date(2015, 3, 30),
				   golf_price_early = 400,
				   golf_price_late = 450,
				   dinner_price_early = 100,
				   dinner_price_late = 125)
	t.put()
	set_tournamend_cache(t)
	return t

def set_tournament_cache(t):
	memcache.add("2015/tournament", t, 60*60*24)

def clear_tournament_cache():
	memcache.delete("2015/tournament")
