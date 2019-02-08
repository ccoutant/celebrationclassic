from google.appengine.ext import ndb

class Sponsor(ndb.Model):
	sponsor_id = ndb.IntegerProperty(default = 0)
	first_name = ndb.StringProperty(default = '')
	last_name = ndb.StringProperty(default = '')
	sort_name = ndb.StringProperty(default = '')
	company = ndb.StringProperty(default = '')
	address = ndb.StringProperty(default = '')
	city = ndb.StringProperty(default = '')
	state = ndb.StringProperty(default = '')
	zip = ndb.StringProperty(default = '')
	phone = ndb.StringProperty(default = '')
	fax = ndb.StringProperty(default = '')
	email = ndb.StringProperty(default = '')
	anonymous = ndb.BooleanProperty(default = False)
	printed_names = ndb.StringProperty(default = '')
	sponsorships = ndb.KeyProperty(repeated = True)
	num_golfers = ndb.IntegerProperty(default = 0)
	num_dinners = ndb.IntegerProperty(default = 0)
	additional_donation = ndb.IntegerProperty(default = 0)
	payment_due = ndb.IntegerProperty(default = 0)
	discount = ndb.IntegerProperty(default = 0)
	discount_type = ndb.StringProperty(default = '')
	go_golfers = ndb.IntegerProperty(default = 0)
	go_discount_code = ndb.StringProperty(default = '')
	payment_made = ndb.IntegerProperty(default = 0)
	payment_type = ndb.StringProperty(default = '')
	transaction_code = ndb.StringProperty(default = '')
	auth_code = ndb.StringProperty(default = '')
	pairing = ndb.StringProperty(default = '')
	dinner_seating = ndb.StringProperty(default = '')
	timestamp = ndb.DateTimeProperty(auto_now_add = True)
	confirmed = ndb.BooleanProperty(default = False) # Set after registration Step 2 completed.
	ok_to_share_email = ndb.BooleanProperty(default = False)
	golfer_keys = ndb.KeyProperty(repeated = True)
	dinner_keys = ndb.KeyProperty(repeated = True)

class Team(ndb.Model):
	name = ndb.StringProperty(default = '')
	starting_hole = ndb.StringProperty(default = '')
	flight = ndb.IntegerProperty(default = 1)
	golfers = ndb.KeyProperty(repeated = True)
	pairing = ndb.StringProperty(default = '')

class Golfer(ndb.Model):
	tournament = ndb.KeyProperty()
	sponsor = ndb.KeyProperty()
	sequence = ndb.IntegerProperty(default = 0)
	active = ndb.BooleanProperty(default = False)
	sort_name = ndb.StringProperty(default = '')
	first_name = ndb.StringProperty(default = '')
	last_name = ndb.StringProperty(default = '')
	gender = ndb.StringProperty(default = '')
	company = ndb.StringProperty(default = '')
	address = ndb.StringProperty(default = '')
	city = ndb.StringProperty(default = '')
	state = ndb.StringProperty(default = '')
	zip = ndb.StringProperty(default = '')
	phone = ndb.StringProperty(default = '')
	email = ndb.StringProperty(default = '')
	average_score = ndb.StringProperty(default = '')
	ghin_number = ndb.StringProperty(default = '')
	has_index = ndb.BooleanProperty(default = False)
	handicap_index = ndb.FloatProperty(default = 0.0)
	shirt_size = ndb.StringProperty(default = '')
	dinner_choice = ndb.StringProperty(default = '')
	team = ndb.KeyProperty()
	cart = ndb.IntegerProperty(default = 0)
	tees = ndb.IntegerProperty(default = 0) # 1 = Red, 2 = White, 3 = Blue
	index_info_modified = ndb.BooleanProperty(default = False)

	def get_handicap_index(self):
		if self.has_index:
			return self.handicap_index
		try:
			return float(self.average_score) * 0.8253 - 61.15
		except:
			return None

class DinnerGuest(ndb.Model):
	tournament = ndb.KeyProperty()
	sponsor = ndb.KeyProperty()
	sequence = ndb.IntegerProperty(default = 0)
	active = ndb.BooleanProperty(default = False)
	first_name = ndb.StringProperty(default = '')
	last_name = ndb.StringProperty(default = '')
	dinner_choice = ndb.StringProperty(default = '')

class TributeAd(ndb.Model):
	first_name = ndb.StringProperty(default = '')
	last_name = ndb.StringProperty(default = '')
	address = ndb.StringProperty(default = '')
	city = ndb.StringProperty(default = '')
	state = ndb.StringProperty(default = '')
	zip = ndb.StringProperty(default = '')
	phone = ndb.StringProperty(default = '')
	email = ndb.StringProperty(default = '')
	ad_size = ndb.IntegerProperty(default = 0)
	go_campaign = ndb.BooleanProperty(default = False)
	printed_names = ndb.StringProperty(default = '')
	payment_due = ndb.IntegerProperty(default = 0)
	payment_made = ndb.IntegerProperty(default = 0)
	payment_type = ndb.StringProperty(default = '')
	transaction_code = ndb.StringProperty(default = '')
	auth_code = ndb.StringProperty(default = '')
	timestamp = ndb.DateTimeProperty(auto_now_add = True)
