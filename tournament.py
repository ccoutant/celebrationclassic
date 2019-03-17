import os
import datetime
import logging
from google.appengine.ext import ndb
from google.appengine.api import memcache

class Tournament(ndb.Model):
	name = ndb.StringProperty()
	published = ndb.BooleanProperty(default = False)
	accepting_registrations = ndb.BooleanProperty(default = False)
	golf_date = ndb.DateProperty()
	dinner_date = ndb.DateProperty()
	early_bird_deadline = ndb.DateProperty() # For Golf
	dinner_early_bird_deadline = ndb.DateProperty() # For dinner-only
	deadline = ndb.DateProperty()
	tribute_deadline = ndb.DateProperty()
	golf_price_early = ndb.IntegerProperty(default = 0)
	golf_price_late = ndb.IntegerProperty(default = 0)
	dinner_price_early = ndb.IntegerProperty(default = 0)
	dinner_price_late = ndb.IntegerProperty(default = 0)
	limit_golfers = ndb.IntegerProperty(default = 0)
	limit_dinners = ndb.IntegerProperty(default = 0)
	golf_sold_out = ndb.BooleanProperty(default = False)
	dinner_sold_out = ndb.BooleanProperty(default = False)
	wait_list_email = ndb.StringProperty(default = "")
	dinner_choices = ndb.StringProperty(default = "Beef,Chicken,Fish,Vegetarian")
	go_discount_codes = ndb.StringProperty(default = "")
	red_course_rating = ndb.FloatProperty(default = 72.0)
	red_course_slope = ndb.FloatProperty(default = 113.0)
	white_course_rating = ndb.FloatProperty(default = 72.0)
	white_course_slope = ndb.FloatProperty(default = 113.0)
	blue_course_rating = ndb.FloatProperty(default = 72.0)
	blue_course_slope = ndb.FloatProperty(default = 113.0)
	timestamp = ndb.DateTimeProperty(auto_now_add = True)

def new_tournament(name):
	tdate = datetime.date.today() + datetime.timedelta(180)
	early_bird = tdate - datetime.timedelta(42)
	deadline = tdate - datetime.timedelta(14)
	t = Tournament(name = name,
				   golf_date = tdate,
				   dinner_date = tdate,
				   early_bird_deadline = tdate - datetime.timedelta(42),
				   dinner_early_bird_deadline = tdate - datetime.timedelta(42),
				   deadline = tdate - datetime.timedelta(14),
				   tribute_deadline = tdate - datetime.timedelta(28),
				   golf_price_early = 400,
				   golf_price_late = 450,
				   dinner_price_early = 100,
				   dinner_price_late = 125)
	return t

def get_tournament(name = None):
	# logging.debug(os.environ['CURRENT_VERSION_ID'])
	if name:
		q = Tournament.query()
		q = q.filter(Tournament.name == name)
		t = q.get()
		if t is not None:
			return t
		t = new_tournament(name)
	else:
		t = memcache.get("t")
		if t is not None:
			return t
		q = Tournament.query()
		q = q.filter(Tournament.published == True)
		q = q.order(-Tournament.timestamp)
		t = q.get()
		if t is None:
			t = new_tournament("new")
		memcache.set("t", t, 60*60*24)
	return t

def set_tournament_cache(t):
	memcache.set("t", t, 60*60*24)

def clear_tournament_cache():
	memcache.delete("t")

class Counters(ndb.Model):
	golfer_count = ndb.IntegerProperty(default = 0)
	dinner_count = ndb.IntegerProperty(default = 0)

def get_counters(t):
	key = ndb.Key("Counters", "counters", parent = t.key)
	counters = key.get()
	if counters is None:
		counters = Counters(parent = t.key, id = "counters")
		if t.key:
			counters.put()
	return counters

@ndb.transactional
def update_counters(t, delta_golfers, delta_dinners):
	key = ndb.Key("Counters", "counters", parent = t.key)
	counters = key.get()
	if counters is None:
		counters = Counters(parent = t, id = "counters")
	counters.golfer_count += delta_golfers
	counters.dinner_count += delta_dinners
	counters.put()
