import datetime
from google.appengine.ext import db
from google.appengine.api import memcache

class Tournament(db.Model):
	name = db.StringProperty()
	published = db.BooleanProperty(default = False)
	accepting_registrations = db.BooleanProperty(default = False)
	golf_date = db.DateProperty()
	dinner_date = db.DateProperty()
	early_bird_deadline = db.DateProperty()
	deadline = db.DateProperty()
	tribute_deadline = db.DateProperty()
	golf_price_early = db.IntegerProperty(default = 0)
	golf_price_late = db.IntegerProperty(default = 0)
	dinner_price_early = db.IntegerProperty(default = 0)
	dinner_price_late = db.IntegerProperty(default = 0)
	golf_sold_out = db.BooleanProperty(default = False)
	dinner_sold_out = db.BooleanProperty(default = False)
	dinner_choices = db.StringProperty(default = "Beef,Chicken,Fish,Vegetarian")
	go_discount_codes = db.StringProperty(default = "")
	red_course_rating = db.FloatProperty(default = 72.0)
	red_course_slope = db.FloatProperty(default = 113.0)
	white_course_rating = db.FloatProperty(default = 72.0)
	white_course_slope = db.FloatProperty(default = 113.0)
	blue_course_rating = db.FloatProperty(default = 72.0)
	blue_course_slope = db.FloatProperty(default = 113.0)
	timestamp = db.DateTimeProperty(auto_now_add = True)

def new_tournament(name):
	tdate = datetime.date.today() + datetime.timedelta(180)
	early_bird = tdate - datetime.timedelta(42)
	deadline = tdate - datetime.timedelta(14)
	t = Tournament(name = name,
				   golf_date = tdate,
				   dinner_date = tdate,
				   early_bird_deadline = tdate - datetime.timedelta(42),
				   deadline = tdate - datetime.timedelta(14),
				   tribute_deadline = tdate - datetime.timedelta(28),
				   golf_price_early = 400,
				   golf_price_late = 450,
				   dinner_price_early = 100,
				   dinner_price_late = 125)
	return t

def get_tournament(name = None):
	if name:
		q = Tournament.all()
		q.filter("name = ", name)
		t = q.get()
		if t is not None:
			return t
		t = new_tournament(name)
	else:
		t = memcache.get("t")
		if t is not None:
			return t
		q = Tournament.all()
		q.filter("published = ", True)
		q.order("-timestamp")
		t = q.get()
		if t is None:
			t = new_tournament("new")
	return t

def set_tournament_cache(t):
	memcache.add("t", t, 60*60*24)

def clear_tournament_cache():
	memcache.delete("t")
