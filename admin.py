#!/usr/bin/env python

import os
import re
import quopri
import cgi
import logging
import webapp2
import datetime
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
import uploadedfile
import tz
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
		caps = capabilities.get_current_user_caps()
		q = capabilities.Capabilities.all()
		q.ancestor(root)
		q.order("email")
		allcaps = q.fetch(30)
		template_values = {
			'capabilities': caps,
			'allcaps': allcaps
			}
		self.response.out.write(render_to_string('users.html', template_values))

	# Process the submitted info.
	def post(self):
		if not users.is_current_user_admin():
			self.redirect(users.create_login_url('/admin/users'))
			return
		root = tournament.get_tournament()
		count = int(self.request.get('count'))
		for i in range(1, count + 1):
			email = self.request.get('email%d' % i)
			q = capabilities.Capabilities.all()
			q.ancestor(root)
			q.filter("email = ", email)
			u = q.get()
			must_update = False
			if u.can_edit_tournament_properties is None:
				u.can_edit_tournament_properties = False
				must_update = True
			us = True if self.request.get('us%d' % i) == 'u' else False
			vr = True if self.request.get('vr%d' % i) == 'v' else False
			ar = True if self.request.get('ar%d' % i) == 'a' else False
			ua = True if self.request.get('ua%d' % i) == 'u' else False
			ec = True if self.request.get('ec%d' % i) == 'e' else False
			et = True if self.request.get('et%d' % i) == 't' else False
			if (must_update or
					us != u.can_update_sponsorships or
					vr != u.can_view_registrations or
					ar != u.can_add_registrations or
					ua != u.can_update_auction or
					ec != u.can_edit_content or
					et != u.can_edit_tournament_properties):
				u.can_update_sponsorships = us
				u.can_view_registrations = vr
				u.can_add_registrations = ar
				u.can_update_auction = ua
				u.can_edit_content = ec
				u.can_edit_tournament_properties = et
				u.put()
		email = self.request.get('email')
		us = True if self.request.get('us') == 'u' else False
		vr = True if self.request.get('vr') == 'v' else False
		ar = True if self.request.get('ar') == 'a' else False
		ua = True if self.request.get('ua') == 'u' else False
		ec = True if self.request.get('ec') == 'e' else False
		et = True if self.request.get('et') == 't' else False
		if email:
			u = capabilities.Capabilities(parent = root,
										  email = email,
										  can_update_sponsorships = us,
										  can_view_registrations = vr,
										  can_add_registrations = ar,
										  can_update_auction = ua,
										  can_edit_content = ec,
										  can_edit_tournament_properties = et)
			u.put()
		memcache.flush_all()
		self.redirect('/admin/users')

# Tournament properties

class ManageTournament(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_tournament_properties:
			self.redirect(users.create_login_url(self.request.uri))
			return
		t = tournament.get_tournament()
		template_values = {
			'capabilities': caps,
			'tournament': t
			}
		self.response.out.write(render_to_string('tournament.html', template_values))

	# Process the submitted info.
	def post(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_tournament_properties:
			self.redirect(users.create_login_url('/admin/tournament'))
			return
		q = tournament.Tournament.all()
		q.filter("name = ", "cc2015")
		t = q.get()
		golf_month = int(self.request.get("golf_month"))
		golf_day = int(self.request.get("golf_day"))
		golf_year = int(self.request.get("golf_year"))
		t.golf_date = datetime.date(golf_year, golf_month, golf_day)
		dinner_month = int(self.request.get("dinner_month"))
		dinner_day = int(self.request.get("dinner_day"))
		dinner_year = int(self.request.get("dinner_year"))
		t.dinner_date = datetime.date(dinner_year, dinner_month, dinner_day)
		early_bird_month = int(self.request.get("early_bird_month"))
		early_bird_day = int(self.request.get("early_bird_day"))
		early_bird_year = int(self.request.get("early_bird_year"))
		t.early_bird_deadline = datetime.date(early_bird_year, early_bird_month, early_bird_day)
		deadline_month = int(self.request.get("deadline_month"))
		deadline_day = int(self.request.get("deadline_day"))
		deadline_year = int(self.request.get("deadline_year"))
		t.deadline = datetime.date(deadline_year, deadline_month, deadline_day)
		t.golf_price_early = int(self.request.get("golf_price_early"))
		t.golf_price_late = int(self.request.get("golf_price_late"))
		t.dinner_price_early = int(self.request.get("dinner_price_early"))
		t.dinner_price_late = int(self.request.get("dinner_price_late"))
		t.golf_sold_out = (self.request.get("golf_sold_out") == "y")
		t.dinner_sold_out = (self.request.get("dinner_sold_out") == "y")
		t.course_rating = float(self.request.get("course_rating"))
		t.course_slope = float(self.request.get("course_slope"))
		t.put()
		memcache.flush_all()
		tournament.set_tournament_cache(t)
		self.redirect('/admin/tournament')

# Sponsorship information.

class Sponsorships(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_sponsorships:
			self.redirect(users.create_login_url(self.request.uri))
			return
		sponsorships = sponsorship.get_sponsorships("all")
		next_seq = 1
		for s in sponsorships:
			next_seq = s.sequence + 1
			last_level = s.level
		template_values = {
			'capabilities': caps,
			'next_seq': next_seq,
			'last_level': last_level,
			'sponsorships': sponsorships
			}
		self.response.out.write(render_to_string('sponsorships.html', template_values))

	# Process the submitted info.
	def post(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_sponsorships:
			self.redirect(users.create_login_url('/admin/sponsorships'))
			return
		sponsorship.clear_sponsorships_cache()
		count = int(self.request.get('count'))
		for i in range(1, count + 1):
			name = self.request.get('name%d' % i)
			q = sponsorship.Sponsorship.all()
			q.filter("name = ", name)
			s = q.get()
			if self.request.get('delete%d' % i) == 'd':
				s.delete()
			else:
				try:
					price = int(self.request.get('price%s' % i))
				except:
					price = s.price
				try:
					golfers_included = int(self.request.get('golfers_included%d' % i))
				except:
					golfers_included = s.golfers_included
				unique = True if self.request.get('unique%d' % i) == 'u' else False
				sold = True if self.request.get('sold%d' % i) == 's' else False
				if price != s.price or golfers_included != s.golfers_included or unique != s.unique or sold != s.sold:
					s.price = price
					s.golfers_included = golfers_included
					s.unique = unique
					s.sold = sold
					s.put()
		name = self.request.get('name')
		level = self.request.get('level')
		sequence = self.request.get('seq')
		price = self.request.get('price')
		golfers_included = self.request.get('golfers_included')
		if golfers_included is None:
			golfers_included = 1
		unique = True if self.request.get('unique') == 'u' else False
		sold = True if self.request.get('sold') == 's' else False
		if name and sequence and price:
			root = tournament.get_tournament()
			s = sponsorship.Sponsorship(parent = root, name = name, level = level, sequence = int(sequence), price = int(price), golfers_included = int(golfers_included), unique = unique, sold = sold)
			s.put()
		self.redirect('/admin/sponsorships')

class ViewGolfer(object):
	def __init__(self, t, s, g, count):
		self.sponsor_id = s.id
		self.sponsor_name = s.first_name + " " + s.last_name
		self.golfer = g
		if g.first_name or g.last_name:
			self.golfer_name = g.first_name + " " + g.last_name
		else:
			self.golfer_name = "(%s #%d)" % (s.last_name, g.sequence)
		self.count = count
		self.pairing = s.pairing if g.sequence == s.num_golfers else ''
		if g.has_index:
			self.course_handicap = min(36, int(round(g.handicap_index * t.course_slope / 113.0)))
		elif g.average_score:
			try:
				handicap_index = float(g.average_score) * 0.8253 - 61.15
				self.course_handicap = min(36, int(round(handicap_index * t.course_slope / 113.0)))
			except:
				self.course_handicap = 36
		else:
			self.course_handicap = 0

class ViewDinner(object):
	def __init__(self, s, first_name, last_name, choice, sequence, count):
		self.sponsor_id = s.id
		self.sponsor_name = s.first_name + " " + s.last_name
		if first_name or last_name:
			self.guest_name = first_name + " " + last_name
		else:
			self.guest_name = "(%s #%d)" % (s.last_name, sequence)
		self.dinner_choice = choice
		self.sequence = sequence
		self.count = count
		self.seating = s.dinner_seating if sequence == s.num_golfers + s.num_dinners else ''

class ViewRegistrations(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("timestamp")
		sponsors = q.fetch(limit = None)
		for s in sponsors:
			golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
			no_dinners = 0
			for g in golfers:
				if g.dinner_choice == 'No Dinner':
					no_dinners += 1
			s.adjusted_dinners = s.num_golfers - no_dinners + s.num_dinners
			s.net_due = s.payment_due - s.payment_made
			if s.discount:
				s.net_due -= s.discount
		template_values = {
			'sponsors': sponsors,
			'incomplete': '',
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewsponsors.html', template_values))

class ViewIncomplete(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
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
				if g.first_name and g.last_name and (g.ghin_number or g.average_score) and g.shirt_size:
					golfers_complete += 1
				if g.dinner_choice:
					ndinners += 1
				if g.dinner_choice == 'No Dinner':
					no_dinners += 1
			guests = DinnerGuest.all().ancestor(s.key()).fetch(s.num_dinners)
			for g in guests:
				if g.first_name and g.last_name and g.dinner_choice:
					ndinners += 1
			s.adjusted_dinners = s.num_golfers - no_dinners + s.num_dinners
			s.net_due = s.payment_due - s.payment_made
			if s.discount:
				s.net_due -= s.discount
			if (s.net_due == 0 and
				  (golfers_complete < s.num_golfers or ndinners < s.num_golfers + s.num_dinners)):
				sponsors.append(s)
		nav = []
		template_values = {
			'sponsors': sponsors,
			'incomplete': 'incomplete',
			'nav': nav,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewsponsors.html', template_values))

class ViewUnpaid(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
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
			s.adjusted_dinners = s.num_golfers - no_dinners + s.num_dinners
			s.net_due = s.payment_due - s.payment_made
			if s.discount:
				s.net_due -= s.discount
			if s.net_due > 0:
				sponsors.append(s)
		nav = []
		template_values = {
			'sponsors': sponsors,
			'incomplete': 'unpaid',
			'nav': nav,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewsponsors.html', template_values))

class ViewUnconfirmed(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", False)
		q.order("timestamp")
		sponsors = q.fetch(100)
		for s in sponsors:
			s.adjusted_dinners = s.num_golfers + s.num_dinners
			s.net_due = s.payment_due - s.payment_made
			if s.discount:
				s.net_due -= s.discount
		nav = []
		template_values = {
			'sponsors': sponsors,
			'incomplete': 'unconfirmed',
			'nav': nav,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewsponsors.html', template_values))

class ViewGolfers(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		html = memcache.get('2015/admin/view/golfers')
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
				all_golfers.append(ViewGolfer(root, s, g, counter))
				counter += 1
			for i in range(len(golfers) + 1, s.num_golfers + 1):
				g = Golfer(parent = s, sequence = i, name = '', gender = '',
						   company = '', address = '', city = '', phone = '', email = '',
						   golf_index = '', average_score = '', ghin_number = '',
						   shirt_size = '', dinner_choice = '')
				all_golfers.append(ViewGolfer(root, s, g, counter))
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
		memcache.add('2015/admin/view/golfers', html, 60*60*24)
		self.response.out.write(html)

class ViewDinners(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		html = memcache.get('2015/admin/view/dinners')
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
					all_dinners.append(ViewDinner(s, g.first_name, g.last_name, g.dinner_choice, g.sequence, counter))
					counter += 1
			for i in range(len(golfers) + 1, s.num_golfers + 1):
				all_dinners.append(ViewDinner(s, '', '', '', i, counter))
				counter += 1
			guests = DinnerGuest.all().ancestor(s.key()).order("sequence").fetch(s.num_dinners)
			for g in guests:
				all_dinners.append(ViewDinner(s, g.first_name, g.last_name, g.dinner_choice, g.sequence + s.num_golfers, counter))
				counter += 1
			for i in range(len(guests) + 1, s.num_dinners + 1):
				all_dinners.append(ViewDinner(s, '', '', '', i + s.num_golfers, counter))
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
		memcache.add('2015/admin/view/dinners', html, 60*60*24)
		self.response.out.write(html)

def csv_encode(val):
	val = re.sub(r'"', '""', str(val or ''))
	return '"%s"' % val

class DownloadRegistrationsCSV(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("timestamp")
		csv = []
		csv.append(','.join(['ID', 'first_name', 'last_name', 'company',
							 'address', 'city', 'state', 'zip', 'email', 'phone',
							 'sponsorships', 'num_golfers', 'num_dinners', 'payment_due',
							 'payment_paid', 'payment_type', 'trans_code']))
		for s in q:
			sponsorships = []
			for sskey in s.sponsorships:
				ss = db.get(sskey)
				sponsorships.append(ss.name)
			csv.append(','.join([csv_encode(x)
								 for x in [s.id, s.first_name, s.last_name, s.company, s.address,
										   s.city, s.state, s.zip, s.email, s.phone,
										   ','.join(sponsorships),
										   s.num_golfers, s.num_golfers + s.num_dinners,
										   s.payment_due, s.payment_made,
										   s.payment_type, s.transaction_code]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=registrations.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

class DownloadGolfersCSV(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("timestamp")
		csv = []
		csv.append(','.join(['first_name', 'last_name', 'gender', 'company',
							 'address', 'city', 'state', 'zip', 'email', 'phone',
							 'ghin_number', 'avg_score', 'shirt_size',
							 'contact_first_name', 'contact_last_name']))
		for s in q:
			q = Golfer.all().ancestor(s.key())
			golfers = q.fetch(s.num_golfers)
			for g in golfers:
				csv.append(','.join([csv_encode(x)
									 for x in [g.first_name, g.last_name, g.gender, g.company,
											   g.address, g.city, g.state, g.zip, g.email, g.phone,
											   g.ghin_number, g.average_score, g.shirt_size,
											   s.first_name, s.last_name]]))
			for i in range(len(golfers) + 1, s.num_golfers + 1):
				csv.append(','.join([csv_encode(x)
									 for x in ['n/a', 'n/a', '', '', '', '', '', '', '', '',
											   '', '', '', '', s.first_name, s.last_name]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=golfers.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

class DownloadDinnersCSV(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("timestamp")
		csv = []
		csv.append(','.join(['first_name', 'last_name', 'dinner_choice',
							 'contact_first_name', 'contact_last_name']))
		for s in q:
			q = Golfer.all().ancestor(s.key())
			golfers = q.fetch(s.num_golfers)
			for g in golfers:
				if g.dinner_choice != 'No Dinner':
					csv.append(','.join([csv_encode(x) for x in [g.first_name, g.last_name,
																 g.dinner_choice,
																 s.first_name, s.last_name]]))
			for i in range(len(golfers) + 1, s.num_golfers + 1):
				csv.append(','.join([csv_encode(x) for x in ['n/a', 'n/a', '',
															 s.first_name, s.last_name]]))
			q = DinnerGuest.all().ancestor(s.key())
			guests = q.fetch(s.num_dinners)
			for g in guests:
				csv.append(','.join([csv_encode(x) for x in [g.first_name, g.last_name,
															 g.dinner_choice,
															 s.first_name, s.last_name]]))
			for i in range(len(guests) + 1, s.num_dinners + 1):
				csv.append(','.join([csv_encode(x) for x in ['n/a', 'n/a', '',
															 s.first_name, s.last_name]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=dinners.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

# Reminder E-mails

incomplete_email_template = """
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

unpaid_email_template = """
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
			body_template = incomplete_email_template
		elif what == 'unpaid':
			body_template = unpaid_email_template
		else:
			self.error(404)
			self.response.out.write('<html><head>\n')
			self.response.out.write('<title>404 Not Found</title>\n')
			self.response.out.write('</head><body>\n')
			self.response.out.write('<h1>Not Found</h1>\n')
			self.response.out.write('<p>The requested page "/admin/mail/%s" was not found on this server.</p>\n' % what)
			self.response.out.write('</body></html>\n')
			return
		selected_items = self.request.get_all('selected_items')
		num_sent = 0
		for id in selected_items:
			q = Sponsor.all()
			q.ancestor(root)
			q.filter('id = ', int(id))
			s = q.get()
			if s:
				body = body_template % (s.first_name, s.id)
				logging.info("sending mail to %s (id %s)" % (s.email, s.id))
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

class DeleteFile(webapp2.RequestHandler):
	def post(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_content:
			self.redirect(users.create_login_url('/admin/edit'))
			return
		if self.request.get('delete-photos'):
			items_to_delete = self.request.get_all('delete-photo')
		else:
			items_to_delete = self.request.get_all('delete-file')
		for path in items_to_delete:
			q = uploadedfile.UploadedFile.all()
			q.ancestor(root)
			q.filter("path =", path)
			item = q.get()
			if item:
				blobstore.delete(item.blob.key())
				item.delete()
		self.redirect("/admin/edit")

class UploadFile(blobstore_handlers.BlobstoreUploadHandler):
	def post(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_content:
			self.redirect(users.create_login_url('/admin/edit'))
			return
		upload_files = self.get_uploads('file')
		if upload_files:
			blob_key = upload_files[0].key()
			filename = upload_files[0].filename
			if self.request.get('upload-photo'):
				item = uploadedfile.UploadedFile(parent = root, name = filename,
												 path = "/photos/%s" % filename,
												 blob = blob_key)
				item.put()
			elif self.request.get('upload-file'):
				item = uploadedfile.UploadedFile(parent = root, name = filename,
												 path = "/files/%s" % filename,
												 blob = blob_key)
				item.put()
			else:
				blobstore.delete(blob_key)
		self.redirect("/admin/edit")

def show_edit_form(name, caps, response):
	page = detailpage.get_detail_page(name, True)
	logging.info("showing %s, version %d, draft %s, preview %s" %
				 (page.name, page.version, "yes" if page.draft else "no", "yes" if page.preview else "no"))
	template_values = {
		'page': page,
		'timestamp': page.last_modified.replace(tzinfo=tz.utc).astimezone(tz.pacific),
		'capabilities': caps
		}
	response.out.write(render_to_string('admineditpage.html', template_values))

class EditPageHandler(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_content:
			self.redirect(users.create_login_url('/admin/edit'))
			return
		pages = []
		for name in detailpage.detail_page_list():
			path = name if name != "home" else ""
			published_version = detailpage.get_published_version(name)
			draft_version = detailpage.get_draft_version(name)
			page = {
				'name': name,
				'path': path,
				'published_version': published_version,
				'draft_version': draft_version,
				'is_draft': draft_version > published_version
				}
			pages.append(page)
		photos = []
		files = []
		q = uploadedfile.UploadedFile.all()
		q.ancestor(t)
		q.order("name")
		for item in q:
			if item.path.startswith('/photos/'):
				photos.append(item)
			elif item.path.startswith('/files/'):
				files.append(item)
		template_values = {
			'pages': pages,
			'photos': photos,
			'files': files,
			'upload_url': blobstore.create_upload_url('/admin/upload-file'),
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

app = webapp2.WSGIApplication([('/admin/sponsorships', Sponsorships),
							   ('/admin/users', ManageUsers),
							   ('/admin/tournament', ManageTournament),
							   ('/admin/auction', ManageAuction),
							   ('/admin/upload-auction', UploadAuctionItem),
							   ('/admin/upload-file', UploadFile),
							   ('/admin/delete-file', DeleteFile),
							   ('/admin/view/registrations', ViewRegistrations),
							   ('/admin/view/incomplete', ViewIncomplete),
							   ('/admin/view/unpaid', ViewUnpaid),
							   ('/admin/view/unconfirmed', ViewUnconfirmed),
							   ('/admin/view/golfers', ViewGolfers),
							   ('/admin/view/dinners', ViewDinners),
							   ('/admin/csv/registrations', DownloadRegistrationsCSV),
							   ('/admin/csv/golfers', DownloadGolfersCSV),
							   ('/admin/csv/dinners', DownloadDinnersCSV),
							   ('/admin/mail/(.*)', SendEmail),
							   ('/admin/edit', EditPageHandler),
							   ('/admin/logout', Logout)],
							  debug=dev_server)
