from google.appengine.ext import db, webapp

import sponsorship

register = webapp.template.create_template_register()

def get_sponsorship_name(value):
	ss = db.get(value)
	return ss.name

register.filter(get_sponsorship_name)
