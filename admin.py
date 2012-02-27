#!/usr/bin/env python

import cgi
import logging
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template, util
from google.appengine.api import users, memcache

import capabilities
import sponsorship
from sponsor import Sponsor, Golfer, DinnerGuest

webapp.template.register_template_library('tags.custom_filters')

# Logout

class Logout(webapp.RequestHandler):
	def get(self):
		self.redirect(users.create_logout_url('/'))

# Users who can update parts of the site.

class ManageUsers(webapp.RequestHandler):
	# Show the form.
	def get(self):
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url(self.request.uri))
			return
		q = capabilities.Capabilities.all()
		caps = q.fetch(30)
		self.response.out.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
	"http://www.w3.org/TR/html4/loose.dtd">
<html>
<head><title>Edit User List</title></head>
<body>
<h1>Edit User List</h1>
<form action="/admin/users" method="post">
<table border="0" cellspacing="0" cellpadding="5">
<tr><th>Email</th><th>Name</th><th>Update Sponsorships</th><th>View Registrations</th><th>Add Registrations</th></tr>
""")
		seq = 1
		for u in caps:
			self.response.out.write('<tr>\n')
			self.response.out.write('<td>%s<input type="hidden" name="email%d" value="%s"></td>\n' % (cgi.escape(u.email), seq, cgi.escape(u.email)))
			self.response.out.write('<td>%s</td>\n' % users.User(u.email).nickname())
			self.response.out.write('<td><input type="checkbox" name="us%d" value="u" %s></td>\n' % (seq, "checked" if u.can_update_sponsorships else ""))
			self.response.out.write('<td><input type="checkbox" name="vr%d" value="v" %s></td>\n' % (seq, "checked" if u.can_view_registrations else ""))
			self.response.out.write('<td><input type="checkbox" name="ar%d" value="a" %s></td>\n' % (seq, "checked" if u.can_add_registrations else ""))
			self.response.out.write('</tr>\n')
			seq += 1
		self.response.out.write('<tr>\n')
		self.response.out.write('<td><input type="text" size="12" name="email" value=""></td>\n')
		self.response.out.write('<td></td>\n')
		self.response.out.write('<td><input type="checkbox" name="us" value="u"></td>\n')
		self.response.out.write('<td><input type="checkbox" name="vr" value="v"></td>\n')
		self.response.out.write('<td><input type="checkbox" name="ar" value="a"></td>\n')
		self.response.out.write('</tr>\n')
		self.response.out.write('</table>\n')
		self.response.out.write('<input type="hidden" name="count" value="%d">\n' % seq)
		self.response.out.write('<input type="submit" value="Save">\n')
		self.response.out.write('</form></body></html>\n')

	# Process the submitted info.
	def post(self):
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url(self.request.uri))
			return
		count = int(self.request.get('count'))
		for i in range(1, count):
			email = self.request.get('email%d' % i)
			q = capabilities.Capabilities.all()
			q.filter("email = ", email)
			u = q.get()
			us = True if self.request.get('us%d' % i) == 'u' else False
			vr = True if self.request.get('vr%d' % i) == 'v' else False
			ar = True if self.request.get('ar%d' % i) == 'a' else False
			if us != u.can_update_sponsorships or vr != u.can_view_registrations or ar != u.can_add_registrations:
				s.can_update_sponsorships = us
				s.can_view_registrations = vr
				s.can_add_registrations = ar
				s.put()
		email = self.request.get('email')
		us = True if self.request.get('us') == 'u' else False
		vr = True if self.request.get('vr') == 'v' else False
		ar = True if self.request.get('ar') == 'a' else False
		if email:
			u = capabilities.Capabilities(email = email, can_update_sponsorships = us, can_view_registrations = vr, can_add_registrations = ar)
			u.put()
		memcache.flush_all()
		self.redirect('/admin/users')

# Sponsorship information.

class Sponsorships(webapp.RequestHandler):
	# Show the form.
	def get(self):
		user = capabilities.get_current_user_caps()
		if user is None or not user.can_update_sponsorships:
			self.redirect(users.create_login_url(self.request.uri))
			return
		sponsorships = sponsorship.get_sponsorships("all")
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
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url(self.request.uri))
			return
		count = int(self.request.get('count'))
		for i in range(1, count):
			name = self.request.get('name%d' % i)
			q = sponsorship.Sponsorship.all()
			q.filter("name = ", name)
			s = q.get()
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
		sequence = self.request.get('seq')
		price = self.request.get('price')
		unique = True if self.request.get('unique') == 'u' else False
		sold = True if self.request.get('sold') == 's' else False
		if name and sequence and price:
			s = sponsorship.Sponsorship(name = name, level = level, sequence = int(sequence), price = int(price), unique = unique, sold = sold)
			s.put()
		memcache.flush_all()
		self.redirect('/admin/sponsorships')

class ViewGolfer(object):
	def __init__(self, s, g, count):
		self.sponsor_id = s.id
		self.sponsor_name = s.name
		self.golfer = g
		self.count = count

class ViewDinner(object):
	def __init__(self, s, name, choice, sequence, count):
		self.sponsor_id = s.id
		self.sponsor_name = s.name
		self.name = name
		self.dinner_choice = choice
		self.sequence = sequence
		self.count = count

class ViewRegistrations(webapp.RequestHandler):
	def get(self, what):
		user = capabilities.get_current_user_caps()
		if user is None or not user.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		q = Sponsor.all()
		q.order("timestamp")
		sponsors = q.fetch(20)
		if what == "sponsors":
			self.response.out.write(template.render('viewsponsors.html', {'sponsors': sponsors}))
		elif what == "golfers":
			all_golfers = []
			counter = 1
			for s in sponsors:
				q = Golfer.all().ancestor(s.key())
				golfers = q.fetch(s.num_golfers)
				for g in golfers:
					all_golfers.append(ViewGolfer(s, g, counter))
					counter += 1
				for i in range(len(golfers) + 1, s.num_golfers + 1):
					g = Golfer(parent = s, sequence = i, name = '', gender = '', title = '',
							   company = '', address = '', city = '', phone = '', email = '',
							   golf_index = '', best_score = '', ghn_number = '',
							   shirt_size = '', dinner_choice = '')
					all_golfers.append(ViewGolfer(s, g, counter))
					counter += 1
			self.response.out.write(template.render('viewgolfers.html', {'golfers': all_golfers}))
		elif what == "guests":
			all_dinners = []
			counter = 1
			for s in sponsors:
				q = Golfer.all().ancestor(s.key())
				golfers = q.fetch(s.num_golfers)
				for g in golfers:
					all_dinners.append(ViewDinner(s, g.name, g.dinner_choice, g.sequence, counter))
					counter += 1
				for i in range(len(golfers) + 1, s.num_golfers + 1):
					all_dinners.append(ViewDinner(s, '', '', i, counter))
					counter += 1
				q = DinnerGuest.all().ancestor(s.key())
				guests = q.fetch(s.num_dinners)
				for g in guests:
					all_dinners.append(ViewDinner(s, g.name, g.dinner_choice, g.sequence + s.num_golfers, counter))
					counter += 1
				for i in range(len(guests) + 1, s.num_dinners + 1):
					all_dinners.append(ViewDinner(s, '', '', i + s.num_golfers, counter))
					counter += 1
			self.response.out.write(template.render('viewguests.html', {'dinners': all_dinners}))

def main():
	logging.getLogger().setLevel(logging.DEBUG)
	application = webapp.WSGIApplication([('/admin/sponsorships', Sponsorships),
										  ('/admin/users', ManageUsers),
										  ('/admin/view/(.*)', ViewRegistrations),
										  ('/admin/logout', Logout)],
										 debug=True)
	util.run_wsgi_app(application)

if __name__ == '__main__':
	main()
