from google.appengine.ext import db

class Sponsor(db.Model):
	id = db.IntegerProperty(default = 0)
	name = db.StringProperty(default = '')
	company = db.StringProperty(default = '')
	address = db.StringProperty(default = '')
	city = db.StringProperty(default = '')
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
	payment_made = db.IntegerProperty(default = 0)
	payment_type = db.StringProperty(default = '')
	transaction_code = db.StringProperty(default = '')
	pairing = db.StringProperty(default = '')
	dinner_seating = db.StringProperty(default = '')
	timestamp = db.DateTimeProperty(auto_now_add = True)
	confirmed = db.BooleanProperty(default = False) # Set after registration Step 2 completed.

class Golfer(db.Model):
	sequence = db.IntegerProperty(default = 0)
	name = db.StringProperty(default = '')
	gender = db.StringProperty(default = '')
	title = db.StringProperty(default = '')
	company = db.StringProperty(default = '')
	address = db.StringProperty(default = '')
	city = db.StringProperty(default = '')
	phone = db.StringProperty(default = '')
	email = db.StringProperty(default = '')
	golf_index = db.StringProperty(default = '') # Not collected any more.
	best_score = db.StringProperty(default = '') # Actually, average score.
	ghn_number = db.StringProperty(default = '') # Should be ghin_number.
	shirt_size = db.StringProperty(default = '')
	dinner_choice = db.StringProperty(default = '')

class DinnerGuest(db.Model):
	sequence = db.IntegerProperty(default = 0)
	name = db.StringProperty(default = '')
	dinner_choice = db.StringProperty(default = '')
