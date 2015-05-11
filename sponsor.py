from google.appengine.ext import db

class Sponsor(db.Model):
	id = db.IntegerProperty(default = 0)
	first_name = db.StringProperty(default = '')
	last_name = db.StringProperty(default = '')
	sort_name = db.StringProperty(default = '')
	company = db.StringProperty(default = '')
	address = db.StringProperty(default = '')
	city = db.StringProperty(default = '')
	state = db.StringProperty(default = '')
	zip = db.StringProperty(default = '')
	phone = db.StringProperty(default = '')
	fax = db.StringProperty(default = '')
	email = db.StringProperty(default = '')
	anonymous = db.BooleanProperty(default = False)
	printed_names = db.StringProperty(default = '')
	sponsorships = db.ListProperty(db.Key)
	num_golfers = db.IntegerProperty(default = 0)
	num_dinners = db.IntegerProperty(default = 0)
	additional_donation = db.IntegerProperty(default = 0)
	payment_due = db.IntegerProperty(default = 0)
	discount = db.IntegerProperty(default = 0)
	discount_type = db.StringProperty(default = '')
	go_golfers = db.IntegerProperty(default = 0)
	go_discount_code = db.StringProperty(default = '')
	payment_made = db.IntegerProperty(default = 0)
	payment_type = db.StringProperty(default = '')
	transaction_code = db.StringProperty(default = '')
	auth_code = db.StringProperty(default = '')
	pairing = db.StringProperty(default = '')
	dinner_seating = db.StringProperty(default = '')
	timestamp = db.DateTimeProperty(auto_now_add = True)
	confirmed = db.BooleanProperty(default = False) # Set after registration Step 2 completed.
	ok_to_share_email = db.BooleanProperty(default = False)

class Team(db.Model):
	name = db.StringProperty(default = '')
	starting_hole = db.StringProperty(default = '')
	flight = db.IntegerProperty(default = 1)
	golfers = db.ListProperty(db.Key)
	pairing = db.StringProperty(default = '')

class Golfer(db.Model):
	sequence = db.IntegerProperty(default = 0)
	active = db.BooleanProperty(default = False)
	sort_name = db.StringProperty(default = '')
	first_name = db.StringProperty(default = '')
	last_name = db.StringProperty(default = '')
	gender = db.StringProperty(default = '')
	company = db.StringProperty(default = '')
	address = db.StringProperty(default = '')
	city = db.StringProperty(default = '')
	state = db.StringProperty(default = '')
	zip = db.StringProperty(default = '')
	phone = db.StringProperty(default = '')
	email = db.StringProperty(default = '')
	average_score = db.StringProperty(default = '')
	ghin_number = db.StringProperty(default = '')
	has_index = db.BooleanProperty(default = False)
	handicap_index = db.FloatProperty(default = 0.0)
	shirt_size = db.StringProperty(default = '')
	dinner_choice = db.StringProperty(default = '')
	team = db.ReferenceProperty(Team)
	cart = db.IntegerProperty(default = 0)
	tees = db.IntegerProperty(default = 0) # 1 = Red, 2 = White, 3 = Blue
	index_info_modified = db.BooleanProperty(default = False)

	def get_handicap_index(self):
		if self.has_index:
			return self.handicap_index
		try:
			return float(self.average_score) * 0.8253 - 61.15
		except:
			return None

class DinnerGuest(db.Model):
	sequence = db.IntegerProperty(default = 0)
	active = db.BooleanProperty(default = False)
	first_name = db.StringProperty(default = '')
	last_name = db.StringProperty(default = '')
	dinner_choice = db.StringProperty(default = '')

class TributeAd(db.Model):
	first_name = db.StringProperty(default = '')
	last_name = db.StringProperty(default = '')
	address = db.StringProperty(default = '')
	city = db.StringProperty(default = '')
	state = db.StringProperty(default = '')
	zip = db.StringProperty(default = '')
	phone = db.StringProperty(default = '')
	email = db.StringProperty(default = '')
	ad_size = db.IntegerProperty(default = 0)
	printed_names = db.StringProperty(default = '')
	payment_due = db.IntegerProperty(default = 0)
	payment_made = db.IntegerProperty(default = 0)
	payment_type = db.StringProperty(default = '')
	transaction_code = db.StringProperty(default = '')
	auth_code = db.StringProperty(default = '')
	timestamp = db.DateTimeProperty(auto_now_add = True)
