from google.appengine.ext import ndb

class Payments(ndb.Model):
	gateway_url = ndb.StringProperty()
	relay_url = ndb.StringProperty()
	receipt_url = ndb.StringProperty()
	api_login_id = ndb.StringProperty()
	transaction_key = ndb.StringProperty()
	test_mode = ndb.BooleanProperty()

def get_payments_info(t):
	payments_info = Payments.query(ancestor = t.key).get()
	if not payments_info:
		payments_info = Payments()
	return payments_info
