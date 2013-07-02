from google.appengine.ext import db
from django.utils.safestring import mark_safe
from django.template import Library
import sponsorship
import markdown2

register = Library()

@register.filter
def get_sponsorship_name(value):
	ss = db.get(value)
	return ss.name

@register.filter
def markdown(value):
	return mark_safe(markdown2.markdown(value))
