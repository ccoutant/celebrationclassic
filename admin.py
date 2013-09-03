#!/usr/bin/env python

import os
import re
import quopri
import cgi
import logging
import webapp2
from google.appengine.ext import db, blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import users, memcache, images, mail
from django.template.loaders.filesystem import Loader
from django.template.loader import render_to_string

import tournament
import capabilities
import sponsorship
import auctionitem
import detailpage
from sponsor import Sponsor, Golfer, DinnerGuest

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

# Logout

class Logout(webapp2.RequestHandler):
	def get(self):
		self.redirect(users.create_logout_url('/'))

# Users who can update parts of the site.

class ManageUsers(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url(self.request.uri))
			return
		root = tournament.get_tournament()
		q = capabilities.Capabilities.all()
		q.ancestor(root)
		q.order("email")
		caps = q.fetch(30)
		self.response.out.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
	"http://www.w3.org/TR/html4/loose.dtd">
<html>
<head><title>Edit User List</title></head>
<body>
<h1>Edit User List</h1>
<form action="/admin/users" method="post">
<table border="0" cellspacing="0" cellpadding="10">
<tr valign="bottom"><th>Email</th><th>Name</th><th>Update<br>Sponsorships</th><th>View<br>Registrations</th><th>Add<br>Registrations</th><th>Update<br>Auction</th><th>Edit<br>Content</th></tr>
""")
		seq = 1
		for u in caps:
			self.response.out.write('<tr>\n')
			self.response.out.write('<td align="center">%s<input type="hidden" name="email%d" value="%s"></td>\n' % (cgi.escape(u.email), seq, cgi.escape(u.email)))
			self.response.out.write('<td align="center">%s</td>\n' % users.User(u.email).nickname())
			self.response.out.write('<td align="center"><input type="checkbox" name="us%d" value="u" %s></td>\n' % (seq, "checked" if u.can_update_sponsorships else ""))
			self.response.out.write('<td align="center"><input type="checkbox" name="vr%d" value="v" %s></td>\n' % (seq, "checked" if u.can_view_registrations else ""))
			self.response.out.write('<td align="center"><input type="checkbox" name="ar%d" value="a" %s></td>\n' % (seq, "checked" if u.can_add_registrations else ""))
			self.response.out.write('<td align="center"><input type="checkbox" name="ua%d" value="u" %s></td>\n' % (seq, "checked" if u.can_update_auction else ""))
			self.response.out.write('<td align="center"><input type="checkbox" name="ec%d" value="e" %s></td>\n' % (seq, "checked" if u.can_edit_content else ""))
			self.response.out.write('</tr>\n')
			seq += 1
		self.response.out.write('<tr>\n')
		self.response.out.write('<td align="center"><input type="text" size="30" name="email" value=""></td>\n')
		self.response.out.write('<td align="center"></td>\n')
		self.response.out.write('<td align="center"><input type="checkbox" name="us" value="u"></td>\n')
		self.response.out.write('<td align="center"><input type="checkbox" name="vr" value="v"></td>\n')
		self.response.out.write('<td align="center"><input type="checkbox" name="ar" value="a"></td>\n')
		self.response.out.write('<td align="center"><input type="checkbox" name="ua" value="u"></td>\n')
		self.response.out.write('<td align="center"><input type="checkbox" name="ec" value="e"></td>\n')
		self.response.out.write('</tr>\n')
		self.response.out.write('</table>\n')
		self.response.out.write('<input type="hidden" name="count" value="%d">\n' % seq)
		self.response.out.write('<input type="submit" value="Save">\n')
		self.response.out.write('</form></body></html>\n')

	# Process the submitted info.
	def post(self):
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url('/admin/users'))
			return
		root = tournament.get_tournament()
		count = int(self.request.get('count'))
		for i in range(1, count):
			email = self.request.get('email%d' % i)
			q = capabilities.Capabilities.all()
			q.ancestor(root)
			q.filter("email = ", email)
			u = q.get()
			us = True if self.request.get('us%d' % i) == 'u' else False
			vr = True if self.request.get('vr%d' % i) == 'v' else False
			ar = True if self.request.get('ar%d' % i) == 'a' else False
			ua = True if self.request.get('ua%d' % i) == 'u' else False
			ec = True if self.request.get('ec%d' % i) == 'e' else False
			if (us != u.can_update_sponsorships or
					vr != u.can_view_registrations or
					ar != u.can_add_registrations or
					ua != u.can_update_auction or
					ec != u.can_edit_content):
				u.can_update_sponsorships = us
				u.can_view_registrations = vr
				u.can_add_registrations = ar
				u.can_update_auction = ua
				u.can_edit_content = ec
				u.put()
		email = self.request.get('email')
		us = True if self.request.get('us') == 'u' else False
		vr = True if self.request.get('vr') == 'v' else False
		ar = True if self.request.get('ar') == 'a' else False
		ua = True if self.request.get('ua') == 'u' else False
		ec = True if self.request.get('ec') == 'e' else False
		if email:
			u = capabilities.Capabilities(parent = root,
										  email = email,
										  can_update_sponsorships = us,
										  can_view_registrations = vr,
										  can_add_registrations = ar,
										  can_update_auction = ua,
										  can_edit_content = ec)
			u.put()
		memcache.flush_all()
		self.redirect('/admin/users')

# Sponsorship information.

class Sponsorships(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_sponsorships:
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
		lastlevel = "Double Eagle"
		for s in sponsorships:
			self.response.out.write('<tr>\n')
			self.response.out.write('<td align="center">%d</td>\n' % s.sequence)
			self.response.out.write('<td align="center">%s<input type="hidden" name="name%d" value="%s"></td>\n' % (cgi.escape(s.name), seq, cgi.escape(s.name)))
			self.response.out.write('<td align="center">%s</td>\n' % s.level)
			self.response.out.write('<td align="center">%d\n' % s.price)
			self.response.out.write('<td align="center"><input type="checkbox" name="unique%d" value="u" %s></td>\n' % (seq, "checked" if s.unique else ""))
			self.response.out.write('<td align="center"><input type="checkbox" name="sold%d" value="s" %s></td>\n' % (seq, "checked" if s.sold else ""))
			self.response.out.write('<td align="center"><input type="checkbox" name="delete%d" value="d"></td>\n' % seq)
			self.response.out.write('</tr>\n')
			seq += 1
			if s.sequence > maxsequence:
				maxsequence = s.sequence
			lastlevel = s.level
		self.response.out.write('<tr>\n')
		self.response.out.write('<td align="center"><input type="text" size="4" name="seq" value="%d"></td>\n' % (maxsequence + 1))
		self.response.out.write('<td align="center"><input type="text" size="12" name="name" value=""></td>\n')
		self.response.out.write('<td align="center">')
		self.response.out.write('<select name="level">')
		self.response.out.write('<option label="Double Eagle" value="Double Eagle" %s></option>' % ("selected" if lastlevel == "Double Eagle" else ""))
		self.response.out.write('<option label="Hole in One" value="Hole in One" %s></option>' % ("selected" if lastlevel == "Hole in One" else ""))
		self.response.out.write('<option label="Eagle" value="Eagle" %s></option>' % ("selected" if lastlevel == "Eagle" else ""))
		self.response.out.write('<option label="Under Par" value="Under Par" %s></option>' % ("selected" if lastlevel == "Under Par" else ""))
		self.response.out.write('<option label="Angel" value="Angel" %s></option>' % ("selected" if lastlevel == "Angel" else ""))
		self.response.out.write('</select>\n')
		self.response.out.write('</td>\n')
		self.response.out.write('<td align="center"><input type="text" size="8" name="price" value=""></td>\n')
		self.response.out.write('<td align="center"><input type="checkbox" name="unique" value="u"></td>\n')
		self.response.out.write('<td align="center"><input type="checkbox" name="sold" value="s"></td>\n')
		self.response.out.write('<td align="center"></td>\n')
		self.response.out.write('</tr>\n')
		self.response.out.write('</table>\n')
		self.response.out.write('<input type="hidden" name="count" value="%d">\n' % seq)
		self.response.out.write('<input type="submit" value="Submit">\n')
		self.response.out.write('</form></body></html>\n')

	# Process the submitted info.
	def post(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_sponsorships:
			self.redirect(users.create_login_url('/admin/sponsorships'))
			return
		sponsorship.clear_sponsorships_cache()
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
			root = tournament.get_tournament()
			s = sponsorship.Sponsorship(parent = root, name = name, level = level, sequence = int(sequence), price = int(price), unique = unique, sold = sold)
			s.put()
		self.redirect('/admin/sponsorships')

class ViewGolfer(object):
	def __init__(self, s, g, count):
		self.sponsor_id = s.id
		self.sponsor_name = s.name
		self.golfer = g
		self.count = count
		self.pairing = s.pairing if g.sequence == s.num_golfers else ''

class ViewDinner(object):
	def __init__(self, s, name, choice, sequence, count):
		self.sponsor_id = s.id
		self.sponsor_name = s.name
		self.name = name
		self.dinner_choice = choice
		self.sequence = sequence
		self.count = count
		self.seating = s.dinner_seating if sequence == s.num_golfers + s.num_dinners else ''

class ViewRegistrations(webapp2.RequestHandler):
	def get(self, what):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		if what == "sponsors":
			if self.request.get('start'):
				start = int(self.request.get('start'))
			else:
				start = 0
			lim = 50
			q = Sponsor.all()
			q.ancestor(root)
			q.filter("confirmed =", True)
			q.order("timestamp")
			sponsors = q.fetch(lim, offset = start)
			for s in sponsors:
				golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
				no_dinners = 0
				for g in golfers:
					if g.dinner_choice == 'No Dinner':
						no_dinners += 1
				s.adjusted_dinners = s.num_golfers - no_dinners + s.num_dinners
			count = q.count()
			nav = []
			i = 0
			while i < count:
				if i == start:
					nav.append('<b>%d-%d</b>' % (i+1, min(count, i+lim)))
				else:
					nav.append('<a href="%s?start=%d">%d-%d</a>' % (self.request.path, i, i+1, min(count, i+lim)))
				i += lim
			template_values = {
				'sponsors': sponsors,
				'incomplete': False,
				'nav': nav,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('viewsponsors.html', template_values))
		elif what == "incomplete":
			q = Sponsor.all()
			q.ancestor(root)
			q.filter("confirmed =", True)
			q.order("timestamp")
			sponsors = []
			for s in q:
				golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
				golfers_complete = 0
				ndinners = 0
				no_dinners = 0
				for g in golfers:
					if g.name and (g.ghn_number or g.best_score) and g.shirt_size:
						golfers_complete += 1
					if g.dinner_choice:
						ndinners += 1
					if g.dinner_choice == 'No Dinner':
						no_dinners += 1
				guests = DinnerGuest.all().ancestor(s.key()).fetch(s.num_dinners)
				for g in guests:
					if g.name and g.dinner_choice:
						ndinners += 1
				if s.payment_made > 0 and (golfers_complete < s.num_golfers or ndinners < s.num_golfers + s.num_dinners):
					s.adjusted_dinners = s.num_golfers - no_dinners + s.num_dinners
					sponsors.append(s)
			nav = []
			template_values = {
				'sponsors': sponsors,
				'incomplete': 'incomplete',
				'nav': nav,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('viewsponsors.html', template_values))
		elif what == "unpaid":
			q = Sponsor.all()
			q.ancestor(root)
			q.filter("confirmed =", True)
			q.order("timestamp")
			sponsors = []
			for s in q:
				golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
				no_dinners = 0
				for g in golfers:
					if g.dinner_choice == 'No Dinner':
						no_dinners += 1
				if s.payment_made == 0:
					s.adjusted_dinners = s.num_golfers - no_dinners + s.num_dinners
					sponsors.append(s)
			nav = []
			template_values = {
				'sponsors': sponsors,
				'incomplete': 'unpaid',
				'nav': nav,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('viewsponsors.html', template_values))
		elif what == "unconfirmed":
			q = Sponsor.all()
			q.ancestor(root)
			q.filter("confirmed =", False)
			q.order("timestamp")
			sponsors = q.fetch(100)
			for s in sponsors:
				s.adjusted_dinners = s.num_golfers + s.num_dinners
			nav = []
			template_values = {
				'sponsors': sponsors,
				'incomplete': 'unconfirmed',
				'nav': nav,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('viewsponsors.html', template_values))
		elif what == "golfers":
			html = memcache.get('/admin/view/golfers')
			if html:
				self.response.out.write(html)
				return
			all_golfers = []
			counter = 1
			q = Sponsor.all()
			q.ancestor(root)
			q.filter("confirmed =", True)
			q.order("timestamp")
			for s in q:
				golfers = Golfer.all().ancestor(s.key()).order("sequence").fetch(s.num_golfers)
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
			shirt_sizes = { }
			for g in all_golfers:
				key = g.golfer.shirt_size if g.golfer.shirt_size else 'unspecified'
				if not key in shirt_sizes:
					shirt_sizes[key] = 0
				shirt_sizes[key] += 1
			template_values = {
				'golfers': all_golfers,
				'shirt_sizes': shirt_sizes,
				'capabilities': caps
				}
			html = render_to_string('viewgolfers.html', template_values)
			memcache.add('/admin/view/golfers', html, 60*60*24)
			self.response.out.write(html)
		elif what == "guests":
			html = memcache.get('/admin/view/guests')
			if html:
				self.response.out.write(html)
				return
			all_dinners = []
			counter = 1
			q = Sponsor.all()
			q.ancestor(root)
			q.filter("confirmed =", True)
			q.order("timestamp")
			for s in q:
				golfers = Golfer.all().ancestor(s.key()).order("sequence").fetch(s.num_golfers)
				for g in golfers:
					if g.dinner_choice != 'No Dinner':
						all_dinners.append(ViewDinner(s, g.name, g.dinner_choice, g.sequence, counter))
						counter += 1
				for i in range(len(golfers) + 1, s.num_golfers + 1):
					all_dinners.append(ViewDinner(s, '', '', i, counter))
					counter += 1
				guests = DinnerGuest.all().ancestor(s.key()).order("sequence").fetch(s.num_dinners)
				for g in guests:
					all_dinners.append(ViewDinner(s, g.name, g.dinner_choice, g.sequence + s.num_golfers, counter))
					counter += 1
				for i in range(len(guests) + 1, s.num_dinners + 1):
					all_dinners.append(ViewDinner(s, '', '', i + s.num_golfers, counter))
					counter += 1
			dinner_choices = { }
			for d in all_dinners:
				key = d.dinner_choice if d.dinner_choice else 'unspecified'
				if not key in dinner_choices:
					dinner_choices[key] = 0
				dinner_choices[key] += 1
			template_values = {
				'dinners': all_dinners,
				'dinner_choices': dinner_choices,
				'capabilities': caps
				}
			html = render_to_string('viewguests.html', template_values)
			memcache.add('/admin/view/guests', html, 60*60*24)
			self.response.out.write(html)
		else:
			self.error(404)

def csv_encode(val):
	val = re.sub(r'"', '""', str(val or ''))
	return '"%s"' % val

class DownloadCSV(webapp2.RequestHandler):
	def get(self, what):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		if what == "sponsors":
			q = Sponsor.all()
			q.ancestor(root)
			q.order("timestamp")
			csv = []
			csv.append(','.join(['ID', 'contact', 'company', 'address', 'city', 'email', 'phone',
								 'sponsorships', 'num_golfers', 'num_dinners', 'payment_due',
								 'payment_paid', 'payment_type', 'trans_code']))
			for s in q:
				sponsorships = []
				for sskey in s.sponsorships:
					ss = db.get(sskey)
					sponsorships.append(ss.name)
				csv.append(','.join([csv_encode(x)
									 for x in [s.id, s.name, s.company, s.address,
											   s.city, s.email, s.phone, ','.join(sponsorships),
											   s.num_golfers, s.num_golfers + s.num_dinners,
											   s.payment_due, s.payment_made,
											   s.payment_type, s.transaction_code]]))
		elif what == "golfers":
			q = Sponsor.all()
			q.ancestor(root)
			q.order("timestamp")
			csv = []
			csv.append(','.join(['contact', 'name', 'gender', 'title', 'company', 'address', 'city',
								 'email', 'phone', 'ghin_number', 'avg_score', 'shirt_size']))
			for s in q:
				q = Golfer.all().ancestor(s.key())
				golfers = q.fetch(s.num_golfers)
				for g in golfers:
					csv.append(','.join([csv_encode(x)
										 for x in [s.name, g.name, g.gender, g.company, g.title,
												   g.address, g.city, g.email, g.phone,
												   g.ghn_number, g.best_score, g.shirt_size]]))
				for i in range(len(golfers) + 1, s.num_golfers + 1):
					csv.append(','.join([csv_encode(x)
										 for x in [s.name, 'n/a', '', '', '', '', '', '', '',
												   '', '', '', '']]))
		elif what == "guests":
			q = Sponsor.all()
			q.ancestor(root)
			q.order("timestamp")
			csv = []
			csv.append(','.join(['contact', 'name', 'dinner_choice']))
			for s in q:
				q = Golfer.all().ancestor(s.key())
				golfers = q.fetch(s.num_golfers)
				for g in golfers:
					if g.dinner_choice != 'No Dinner':
						csv.append(','.join([csv_encode(x) for x in [s.name, g.name, g.dinner_choice]]))
				for i in range(len(golfers) + 1, s.num_golfers + 1):
					csv.append(','.join([csv_encode(x) for x in [s.name, 'n/a', '']]))
				q = DinnerGuest.all().ancestor(s.key())
				guests = q.fetch(s.num_dinners)
				for g in guests:
					csv.append(','.join([csv_encode(x) for x in [s.name, g.name, g.dinner_choice]]))
				for i in range(len(guests) + 1, s.num_dinners + 1):
					csv.append(','.join([csv_encode(x) for x in [s.name, '', '']]))
		else:
			self.error(404)
			return
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=%s.csv' % what
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

# Reminder E-mails

class SendEmail(webapp2.RequestHandler):
	def post(self, what):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		subject = "Your Celebration Classic Registration"
		sender = users.get_current_user().email()
		if what == 'incomplete':
			body_template = """
Dear %s,

Thank you for registering for the Celebration Classic Dinner and Golf Tournament!
In order to prepare for this event, we need a little more information from you.
Please visit the following URL:

    http://www.celebrationclassic.org/register?id=%s

and check to make sure that you have provided all of the following information
for each golfer and dinner guest:

- Name
- GHIN number or average score (for golfers)
- Shirt size (for golfers)
- Dinner selection

If you have any questions, just reply to this email and we'll be glad to assist.
"""
		elif what == 'unpaid':
			body_template = """
Dear %s,

Thank you for registering for the Celebration Classic Dinner and Golf Tournament!
Our records show that you have not yet paid for this event.  Please visit the
following URL:

    http://www.celebrationclassic.org/register?id=%s

and choose a payment method at the bottom of the page. If you have already paid
by other means, or if we should cancel this registration, please reply to this
message and let us know.

Please also check to make sure that you have provided all of the following
information for each golfer and dinner guest:

- Name
- GHIN number or average score (for golfers)
- Shirt size (for golfers)
- Dinner selection

If you have any questions, just reply to this email and we'll be glad to assist.
"""
		else:
			self.error(404)
			return
		selected_items = self.request.get_all('selected_items')
		num_sent = 0
		for id in selected_items:
			q = Sponsor.all()
			q.ancestor(root)
			q.filter('id = ', int(id))
			s = q.get()
			if s:
				body = body_template % (s.name, s.id)
				logging.info("sending mail to %s (id %s)" % (s.name, s.id))
				mail.send_mail(sender=sender, to=s.email, subject=subject, body=body)
				num_sent += 1
		template_values = {
			'capabilities': caps,
			'num_sent': num_sent
			}
		self.response.out.write(render_to_string('emailack.html', template_values))

# Auction Items

class ManageAuction(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_auction:
			self.redirect(users.create_login_url(self.request.uri))
			return
		if self.request.get('key'):
			key = self.request.get('key')
			item = auctionitem.AuctionItem.get(key)
			template_values = {
				'item': item,
				'key': key,
				'upload_url': blobstore.create_upload_url('/admin/upload-auction'),
				'capabilities': caps
				}
			self.response.out.write(render_to_string('editauction.html', template_values))
		elif self.request.get('new'):
			auction_items = auctionitem.get_auction_items()
			if auction_items:
				seq = auction_items[-1].sequence + 1
			else:
				seq = 1
			item = auctionitem.AuctionItem(sequence = seq)
			template_values = {
				'item': item,
				'key': '',
				'upload_url': blobstore.create_upload_url('/admin/upload-auction'),
				'capabilities': caps
				}
			self.response.out.write(render_to_string('editauction.html', template_values))
		else:
			auction_items = auctionitem.get_auction_items()
			template_values = {
				'auction_items': auction_items,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('adminauction.html', template_values))

class UploadAuctionItem(blobstore_handlers.BlobstoreUploadHandler):
	# Process the submitted info.
	def post(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_auction:
			self.redirect(users.create_login_url('/admin/auction'))
			return
		auctionitem.clear_auction_item_cache()
		key = self.request.get('key')
		if key:
			item = auctionitem.AuctionItem.get(key)
		else:
			item = auctionitem.AuctionItem(parent = root)
		item.sequence = int(self.request.get('sequence'))
		desc = self.request.get('description')
		desc = desc.replace('\r\n', '\n')
		item.description = desc
		upload_files = self.get_uploads('file')
		if upload_files:
			if item.photo_blob:
				blobstore.delete(item.photo_blob.key())
			if item.thumbnail_id:
				auctionitem.Thumbnail.get_by_id(item.thumbnail_id).delete()
			item.photo_blob = upload_files[0].key()
			img = images.Image(blob_key = item.photo_blob)
			img.resize(width = 200)
			thumbnail = auctionitem.Thumbnail()
			thumbnail.image = img.execute_transforms(output_encoding = images.JPEG)
			thumbnail.put()
			item.thumbnail_id = thumbnail.key().id()
			item.thumbnail_width = img.width
			item.thumbnail_height = img.height
		item.put()
		self.redirect("/admin/auction")

def show_edit_form(name, caps, response):
	page = detailpage.get_detail_page(name, True)
	logging.info("showing %s, version %d, draft %s, preview %s" %
				 (page.name, page.version, "yes" if page.draft else "no", "yes" if page.preview else "no"))
	template_values = {
		'page': page,
		'capabilities': caps
		}
	response.out.write(render_to_string('admineditpage.html', template_values))

class EditPageHandler(webapp2.RequestHandler):
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_content:
			self.redirect(users.create_login_url('/admin/edit'))
			return
		pages = []
		for name in detailpage.detail_page_list():
			published_version = detailpage.get_published_version(name)
			draft_version = detailpage.get_draft_version(name)
			page = {
				'name': name,
				'published_version': published_version,
				'draft_version': draft_version,
				'is_draft': draft_version > published_version
				}
			pages.append(page)
		template_values = {
			'pages': pages,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('adminedit.html', template_values))

	def save(self, is_preview, is_draft):
		name = self.request.get('name')
		version = int(self.request.get('version'))
		was_draft = bool(int(self.request.get('draft')))
		was_preview = bool(int(self.request.get('preview')))
		title = self.request.get('pagetitle')
		content = self.request.get('pagecontent')
		t = tournament.get_tournament()
		if was_preview:
			q = detailpage.DetailPage.all()
			q.ancestor(t)
			q.filter("name = ", name)
			q.filter("version = ", version)
			page = q.get()
			logging.info("saving %s: name %s, version %d, draft %s, preview %s" %
						 (page.key().id(), name, version, "yes" if is_draft else "no", "yes" if is_preview else "no"))
			page.title = title
			page.content = content
			page.preview = is_preview
			page.draft = is_draft
			page.put()
		else:
			versions = detailpage.get_draft_version(name)
			version += 1
			page = detailpage.DetailPage(parent = t, name = name, version = version,
										 title = title, content = content,
										 draft = is_draft, preview = is_preview)
			logging.info("saving new: name %s, version %d, draft %s, preview %s" %
						 (name, version, "yes" if is_draft else "no", "yes" if is_preview else "no"))
			page.put()
		detailpage.set_version(name, version, is_preview or is_draft)

	def post(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_content:
			self.redirect(users.create_login_url('/admin/edit'))
			return
		for name in detailpage.detail_page_list():
			if self.request.get('edit' + name):
				show_edit_form(name, caps, self.response)
				return
		if self.request.get('previewbutton'):
			self.save(True, False)
			show_edit_form(self.request.get('name'), caps, self.response)
		elif self.request.get('savebutton'):
			self.save(False, True)
			self.redirect("/admin/edit")
		elif self.request.get('publishbutton'):
			self.save(False, False)
			self.redirect("/admin/edit")
		else:
			self.response.set_status(204, 'No submit button pressed')

# Upgrade database to initialize "confirmed" field in existing records.

class Upgrade(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url(self.request.uri))
			return
		if self.request.get('start'):
			start = int(self.request.get('start'))
		else:
			start = 0
		lim = 50
		q = Sponsor.all()
		q.ancestor(root)
		q.order("timestamp")
		sponsors = q.fetch(lim, offset = start)
		for s in sponsors:
			num_golfers = Golfer.all().ancestor(s.key()).count()
			num_dinners = DinnerGuest.all().ancestor(s.key()).count()
			if num_golfers + num_dinners > 0:
				s.confirmed = True
			else:
				s.confirmed = False
			s.put()
			s.adjusted_dinners = s.num_golfers + s.num_dinners
		count = q.count()
		nav = []
		i = 0
		while i < count:
			if i == start:
				nav.append('<b>%d-%d</b>' % (i+1, min(count, i+lim)))
			else:
				nav.append('<a href="%s?start=%d">%d-%d</a>' % (self.request.path, i, i+1, min(count, i+lim)))
			i += lim
		template_values = {
			'sponsors': sponsors,
			'incomplete': False,
			'nav': nav,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewsponsors.html', template_values))

app = webapp2.WSGIApplication([('/admin/sponsorships', Sponsorships),
							   ('/admin/users', ManageUsers),
							   ('/admin/auction', ManageAuction),
							   ('/admin/upload-auction', UploadAuctionItem),
							   ('/admin/view/(.*)', ViewRegistrations),
							   ('/admin/upgrade/set-confirm', Upgrade),
							   ('/admin/csv/(.*)', DownloadCSV),
							   ('/admin/mail/(.*)', SendEmail),
							   ('/admin/edit', EditPageHandler),
							   ('/admin/logout', Logout)],
							  debug=dev_server)
