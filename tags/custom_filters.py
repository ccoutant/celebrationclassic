from google.appengine.ext import db, webapp
from django.utils.safestring import mark_safe

import sponsorship

import markdown2

register = webapp.template.create_template_register()

@register.filter
def get_sponsorship_name(value):
	ss = db.get(value)
	return ss.name

@register.filter
def markdown(value):
	return mark_safe(markdown2.markdown(value))
