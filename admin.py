#!/usr/bin/env python

import os
import cgi
import logging
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template

# Sponsorship information.

class Sponsorship(db.Model):
	name = db.StringProperty()
	level = db.StringProperty()
	sequence = db.IntegerProperty()
	price = db.IntegerProperty()
	unique = db.BooleanProperty()
	sold = db.BooleanProperty()

class Sponsorships(webapp.RequestHandler):
	# Show the form.
	def get(self):
		q = Sponsorship.all()
		q.order("sequence")
		sponsorships = q.fetch(30)
		self.response.out.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
	"http://www.w3.org/TR/html4/loose.dtd">
<html>
<head><title>Edit Sponsorship List</title></head>
<body>
<h1>Edit Sponsorship List</h1>
<form action="/admin/sponsorships" method="post">
<table border="0" cellspacing="0" cellpadding="5">
<tr><th>Order</th><th>Name</th><th>Level</th><th>Price</th><th>Unique</th><th>Sold</th><th>Delete</th></tr>
""")
		seq = 1
		maxsequence = 0
		lastlevel = "Premier"
		for s in sponsorships:
			self.response.out.write('<tr>\n')
			self.response.out.write('<td>%d</td>\n' % s.sequence)
			self.response.out.write('<td>%s<input type="hidden" name="name%d" value="%s"></td>\n' % (cgi.escape(s.name), seq, cgi.escape(s.name)))
			self.response.out.write('<td>%s</td>\n' % s.level)
			self.response.out.write('<td>%d\n' % s.price)
			self.response.out.write('<td><input type="checkbox" name="unique%d" value="u" %s></td>\n' % (seq, "checked" if s.unique else ""))
			self.response.out.write('<td><input type="checkbox" name="sold%d" value="s" %s></td>\n' % (seq, "checked" if s.sold else ""))
			self.response.out.write('<td><input type="checkbox" name="delete%d" value="d"></td>\n' % seq)
			self.response.out.write('</tr>\n')
			seq += 1
			if s.sequence > maxsequence:
				maxsequence = s.sequence
			lastlevel = s.level
		self.response.out.write('<tr>\n')
		self.response.out.write('<td><input type="text" size="4" name="seq" value="%d"></td>\n' % (maxsequence + 1))
		self.response.out.write('<td><input type="text" size="12" name="name" value=""></td>\n')
		self.response.out.write('<td>')
		self.response.out.write('<select name="level">')
		self.response.out.write('<option label="Premier" value="Premier" %s></option>' % ("selected" if lastlevel == "Premier" else ""))
		self.response.out.write('<option label="Executive" value="Executive" %s></option>' % ("selected" if lastlevel == "Executive" else ""))
		self.response.out.write('<option label="Pro" value="Pro" %s></option>' % ("selected" if lastlevel == "Pro" else ""))
		self.response.out.write('<option label="Angel" value="Angel" %s></option>' % ("selected" if lastlevel == "Angel" else ""))
		self.response.out.write('</select>\n')
		self.response.out.write('</td>\n')
		self.response.out.write('<td><input type="text" size="8" name="price" value=""></td>\n')
		self.response.out.write('<td><input type="checkbox" name="unique" value="u"></td>\n')
		self.response.out.write('<td><input type="checkbox" name="sold" value="s"></td>\n')
		self.response.out.write('<td></td>\n')
		self.response.out.write('</tr>\n')
		self.response.out.write('</table>\n')
		self.response.out.write('<input type="hidden" name="count" value="%d">\n' % seq)
		self.response.out.write('<input type="submit" value="Submit">\n')
		self.response.out.write('</form></body></html>\n')

	# Process the submitted info.
	def post(self):
		count = int(self.request.get('count'))
		for i in range(1, count):
			name = self.request.get('name%d' % i)
			q = Sponsorship.all()
			q.filter("name = ", name)
			s = q.fetch(1)[0]
			if self.request.get('delete%d' % i) == 'd':
				s.delete()
			else:
				unique = True if self.request.get('unique%d' % i) == 'u' else False
				sold = True if self.request.get('sold%d' % i) == 's' else False
				if unique != s.unique or sold != s.sold:
					s.unique = unique
					s.sold = sold
					s.put()
		name = self.request.get('name')
		level = self.request.get('level')
		sequence = int(self.request.get('seq'))
		price = int(self.request.get('price'))
		unique = True if self.request.get('unique') == 'u' else False
		sold = True if self.request.get('sold') == 's' else False
		if name and sequence and price:
			s = Sponsorship(name = name, level = level, sequence = sequence, price = price, unique = unique, sold = sold)
			s.put()
		self.redirect('/admin/sponsorships')

def main():
	logging.getLogger().setLevel(logging.INFO)
	application = webapp.WSGIApplication([('/admin/sponsorships', Sponsorships)],
										 debug=True)
	util.run_wsgi_app(application)

if __name__ == '__main__':
	main()
