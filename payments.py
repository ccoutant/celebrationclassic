from google.appengine.ext import db

class Payments(db.Model):
	gateway_url = db.StringProperty()
	relay_url = db.StringProperty()
	receipt_url = db.StringProperty()
	api_login_id = db.StringProperty()
	transaction_key = db.StringProperty()
	test_mode = db.BooleanProperty()

def get_payments_info(t):
	payments_info = Payments.all().ancestor(t).get()
	if not payments_info:
		payments_info = Payments()
	return payments_info
