from google.appengine.ext import db

class Payments(db.Model):
	gateway_url = db.StringProperty()
	api_login_id = db.StringProperty()
	transaction_key = db.StringProperty()

def get_payments_info(t):
	return Payments.all().ancestor(t).get()
