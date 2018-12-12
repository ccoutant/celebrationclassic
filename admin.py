#!/usr/bin/env python

import os
import re
import quopri
import cgi
import logging
import webapp2
import datetime
import hashlib
import json
from google.appengine.ext import db, blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import users, memcache, images, mail
from django.template.loaders.filesystem import Loader
from django.template.loader import render_to_string

import tournament
import payments
import capabilities
import sponsorship
import auctionitem
import detailpage
import uploadedfile
import tz
from sponsor import Sponsor, Team, Golfer, DinnerGuest, TributeAd

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

# Logout

def show_login_page(out, redirect_url):
	email = None
	user = users.get_current_user()
	if user:
		email = user.email()
		logging.info("User %s (%s) does not have required capability" % (email, user.nickname()))
	template_values = {
		'email': email,
		'login_url': users.create_login_url(redirect_url),
		'logout_url': users.create_logout_url(redirect_url)
		}
	out.write(render_to_string('login.html', template_values))

class Logout(webapp2.RequestHandler):
	def get(self):
		self.redirect(users.create_logout_url('/'))

# Users who can update parts of the site.

class ManageUsers(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, self.request.uri)
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
			show_login_page(self.response.out, '/admin/users')
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
			pp = True if self.request.get('pp%d' % i) == 'p' else False
			if (must_update or
					us != u.can_update_sponsorships or
					vr != u.can_view_registrations or
					ar != u.can_add_registrations or
					ua != u.can_update_auction or
					ec != u.can_edit_content or
					et != u.can_edit_tournament_properties or
					pp != u.can_edit_payment_processor):
				u.can_update_sponsorships = us
				u.can_view_registrations = vr
				u.can_add_registrations = ar
				u.can_update_auction = ua
				u.can_edit_content = ec
				u.can_edit_tournament_properties = et
				u.can_edit_payment_processor = pp
				u.put()
		email = self.request.get('email')
		us = True if self.request.get('us') == 'u' else False
		vr = True if self.request.get('vr') == 'v' else False
		ar = True if self.request.get('ar') == 'a' else False
		ua = True if self.request.get('ua') == 'u' else False
		ec = True if self.request.get('ec') == 'e' else False
		et = True if self.request.get('et') == 't' else False
		pp = True if self.request.get('pp') == 'p' else False
		if email:
			u = capabilities.Capabilities(parent = root,
										  email = email,
										  can_update_sponsorships = us,
										  can_view_registrations = vr,
										  can_add_registrations = ar,
										  can_update_auction = ua,
										  can_edit_content = ec,
										  can_edit_tournament_properties = et,
										  can_edit_payment_processor = pp)
			u.put()
		memcache.flush_all()
		self.redirect('/admin/users')

# Tournament properties

class ManageTournament(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_tournament_properties:
			show_login_page(self.response.out, self.request.uri)
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
			show_login_page(self.response.out, '/admin/tournament')
			return
		q = tournament.Tournament.all()
		q.filter("name = ", "cc2019")
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
		tribute_deadline_month = int(self.request.get("tribute_deadline_month"))
		tribute_deadline_day = int(self.request.get("tribute_deadline_day"))
		tribute_deadline_year = int(self.request.get("tribute_deadline_year"))
		t.tribute_deadline = datetime.date(tribute_deadline_year, tribute_deadline_month, tribute_deadline_day)
		t.golf_price_early = int(self.request.get("golf_price_early"))
		t.golf_price_late = int(self.request.get("golf_price_late"))
		t.dinner_price_early = int(self.request.get("dinner_price_early"))
		t.dinner_price_late = int(self.request.get("dinner_price_late"))
		t.golf_sold_out = (self.request.get("golf_sold_out") == "y")
		t.dinner_sold_out = (self.request.get("dinner_sold_out") == "y")
		t.go_discount_codes = self.request.get("go_discount_codes")
		t.red_course_rating = float(self.request.get("red_course_rating"))
		t.red_course_slope = float(self.request.get("red_course_slope"))
		t.white_course_rating = float(self.request.get("white_course_rating"))
		t.white_course_slope = float(self.request.get("white_course_slope"))
		t.blue_course_rating = float(self.request.get("blue_course_rating"))
		t.blue_course_slope = float(self.request.get("blue_course_slope"))
		t.put()
		memcache.flush_all()
		tournament.set_tournament_cache(t)
		self.redirect('/admin/tournament')

# Payment Gateway

class PaymentGateway(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_payment_processor:
			show_login_page(self.response.out, self.request.uri)
			return
		t = tournament.get_tournament()
		payments_info = payments.get_payments_info(t)
		template_values = {
			'capabilities': caps,
			'payments': payments_info
			}
		self.response.out.write(render_to_string('payments.html', template_values))

	# Process the submitted info.
	def post(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_payment_processor:
			show_login_page(self.response.out, self.request.uri)
			return
		t = tournament.get_tournament()
		payment_gateway = payments.Payments.all().ancestor(t).get()
		if payment_gateway is None:
			payment_gateway = payments.Payments(parent = t)
		payment_gateway.gateway_url = self.request.get("gateway_url")
		payment_gateway.relay_url = self.request.get("relay_url")
		payment_gateway.receipt_url = self.request.get("receipt_url")
		payment_gateway.api_login_id = self.request.get("api_login_id")
		payment_gateway.transaction_key = self.request.get("transaction_key")
		payment_gateway.test_mode = self.request.get("test_mode") == "true"
		payment_gateway.put()
		self.redirect('/admin/payments')

# Sponsorship information.

class Sponsorships(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_sponsorships:
			show_login_page(self.response.out, self.request.uri)
			return
		root = tournament.get_tournament()
		sponsorships = sponsorship.Sponsorship.all().ancestor(root).order("sequence").fetch(30)
		next_seq = 1
		last_level = "Double Eagle"
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
			show_login_page(self.response.out, '/admin/sponsorships')
			return
		root = tournament.get_tournament()
		sponsorship.clear_sponsorships_cache()
		count = int(self.request.get('count'))
		for i in range(1, count + 1):
			name = self.request.get('name%d' % i)
			q = sponsorship.Sponsorship.all()
			q.ancestor(root)
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
			s = sponsorship.Sponsorship(parent = root, name = name, level = level, sequence = int(sequence), price = int(price), golfers_included = int(golfers_included), unique = unique, sold = sold)
			s.put()
		self.redirect('/admin/sponsorships')

def get_tees(flight, gender):
	if gender == "F":
		return 1 # Red
	if flight == 2:
		return 3 # Blue
	return 2 # White

def calc_course_handicap(tournament, handicap_index, tees):
	slope = [tournament.red_course_slope, tournament.white_course_slope, tournament.blue_course_slope][tees - 1]
	return min(36, int(round(handicap_index * slope / 113.0)))

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
		self.pairing = s.pairing if g.sequence == s.num_golfers else '' # TODO: remove this
		self.team_name = g.team.name if g.team else ''
		if g.tees:
			self.tees = g.tees
		else:
			flight = 1
			if g.team:
				flight = g.team.flight
			self.tees = get_tees(flight, g.gender)
		handicap_index = g.get_handicap_index()
		if g.has_index:
			self.handicap_index_str = "%.1f" % handicap_index
			self.computed_index = ''
			self.course_handicap = calc_course_handicap(t, handicap_index, self.tees)
		elif handicap_index is not None:
			self.handicap_index_str = ''
			self.computed_index = "%.1f" % handicap_index
			self.course_handicap = calc_course_handicap(t, handicap_index, self.tees)
		else:
			self.handicap_index_str = ''
			self.computed_index = ''
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
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("sort_name")
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
			s.net_due = max(0, s.net_due)
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
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("sort_name")
		sponsors = []
		for s in q:
			golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
			golfers_complete = 0
			ndinners = 0
			no_dinners = 0
			for g in golfers:
				if g.first_name and g.last_name and g.gender and (g.ghin_number or g.average_score) and g.shirt_size:
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
			s.net_due = max(0, s.net_due)
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
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("sort_name")
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
			s.net_due = max(0, s.net_due)
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

class ViewDinnerSurvey(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("sort_name")
		sponsors = []
		for s in q:
			if s.num_golfers > 0 and s.email:
				sponsors.append(s)
		nav = []
		template_values = {
			'sponsors': sponsors,
			'nav': nav,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('dinnersurvey.html', template_values))

class ViewUnconfirmed(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
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
			s.net_due = max(0, s.net_due)
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
			show_login_page(self.response.out, self.request.uri)
			return
		html = memcache.get('2019/admin/view/golfers')
		if html:
			self.response.out.write(html)
			return
		all_golfers = []
		counter = 1
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("sort_name")
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
		memcache.add('2019/admin/view/golfers', html, 60*60*24)
		self.response.out.write(html)

class ViewGolfersByName(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		all_golfers = []
		q = Golfer.all()
		q.ancestor(root)
		q.filter("active =", True)
		q.order("sort_name")
		counter = 1
		for g in q:
			s = g.parent()
			all_golfers.append(ViewGolfer(root, s, g, counter))
			counter += 1
		template_values = {
			'golfers': all_golfers,
			'capabilities': caps
			}
		html = render_to_string('viewgolfersbyname.html', template_values)
		self.response.out.write(html)

class UpdateHandicap(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		start = 1
		if self.request.get('start'):
			start = int(self.request.get('start'))
		all_golfers = []
		q = Golfer.all()
		q.ancestor(root)
		q.filter("active =", True)
		q.order("sort_name")
		golfers = q.fetch(offset = start - 1, limit = 21)
		prev_page_offset = 0 if start == 1 else max(1, start - 20)
		next_page_offset = 0
		if len(golfers) == 21:
			next_page_offset = start + 20
			golfers = golfers[:20]
		counter = start
		for g in golfers:
			s = g.parent()
			vg = ViewGolfer(root, s, g, counter)
			h = hashlib.md5()
			h.update(g.ghin_number or '-')
			h.update(vg.handicap_index_str or '-')
			h.update(g.average_score or '-')
			h.update('t' if g.index_info_modified else 'f')
			vg.index_hash = h.hexdigest()
			all_golfers.append(vg)
			counter += 1
		template_values = {
			'golfers': all_golfers,
			'prev_page_offset': prev_page_offset,
			'this_page_offset': start,
			'next_page_offset': next_page_offset,
			'count': len(golfers),
			'capabilities': caps
			}
		html = render_to_string('viewgolfers-index.html', template_values)
		self.response.out.write(html)

	def post(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, '/admin/view/golfers/handicap')
			return
		prev_page_offset = int(self.request.get('prev_page_offset'))
		this_page_offset = int(self.request.get('this_page_offset'))
		next_page_offset = int(self.request.get('next_page_offset'))
		count = int(self.request.get('count'))
		for i in range(this_page_offset, this_page_offset + count):
			key = self.request.get('key_%d' % i)
			index_hash = self.request.get('hash_%d' % i)
			ghin_number = self.request.get('ghin_%d' % i)
			handicap_index = self.request.get('index_%d' % i)
			average_score = self.request.get('avg_score_%d' % i)
			modified_checkbox = self.request.get('modified_%d' % i)
			h = hashlib.md5()
			h.update(ghin_number or '-')
			h.update(handicap_index or '-')
			h.update(average_score or '-')
			h.update('t' if modified_checkbox else 'f')
			if h.hexdigest() == index_hash:
				continue
			try:
				g = Golfer.get(key)
			except:
				logging.error("Invalid key '%s'" % key)
				continue
			logging.info("Updating handicap info for golfer #%d" % i)
			g.ghin_number = ghin_number
			if handicap_index:
				try:
					val = float(handicap_index)
					if not g.has_index or val != g.handicap_index:
						g.handicap_index = val
						g.has_index = True
				except ValueError:
					logging.error("Invalid handicap index '%s'" % handicap_index)
			else:
				g.handicap_index = 0.0
				g.has_index = False
			g.average_score = average_score
			g.index_info_modified = False
			g.put()
		memcache.delete('2019/admin/view/golfers')
		if self.request.get('prevpage'):
			self.redirect('/admin/view/golfers/handicap?start=%d' % prev_page_offset)
		elif self.request.get('nextpage'):
			self.redirect('/admin/view/golfers/handicap?start=%d' % next_page_offset)
		else:
			self.redirect('/admin/view/golfers/handicap?start=%d' % this_page_offset)

class JsonBuilder:
	def __init__(self, root):
		self.root = root
		self.build_teams()
		self.build_golfers_and_groups()
		self.check_consistency()

	def build_teams(self):
		"""
		Build the list of teams, along with side data structures mapping golfers
		to teams and teams to golfers.
		golfers_by_team is an array indexed by (team_num - 1), where each element
		is an array of golfer IDs.
		teams_by_golfer_id_fwd is a table that maps each golfer id to a team,
		based on the forward links from the Team entity to Golfer entities.
		"""
		self.teams = []
		self.teams_by_id = {}
		self.golfers_by_team = []
		self.golfer_nums_by_id = {}
		self.teams_by_golfer_id_fwd = {}
		q = Team.all().ancestor(self.root).order("name")
		for t in q:
			t_id = t.key().id()
			team_num = len(self.teams) + 1
			team = {
				'team_num': team_num,
				'key': t_id,
				'name': t.name,
				'golfer_nums': [],
				'pairing_prefs': t.pairing or ''
			}
			self.teams.append(team)
			self.teams_by_id[t_id] = team_num
			golfer_ids = []
			if t.golfers:
				for g_key in t.golfers:
					g_id = g_key.id()
					golfer_ids.append(g_id)
					if g_id in self.teams_by_golfer_id_fwd:
						other_team_num = self.teams_by_golfer_id_fwd[g_id]
						other_team = teams[other_team_num - 1]
						logging.warning("Golfer %d is contained by teams \"%s\" and \"%s\"" % (g_id, other_team['name'], t.name))
					else:
						self.teams_by_golfer_id_fwd[g_id] = team_num
			self.golfers_by_team.append(golfer_ids)

	def build_golfers_and_groups(self):
		"""
		Build the list of golfers and the list of groups, along with a side data
		structure mapping golfers to teams.
		teams_by_golfer_id_rev is a table that maps each golfer id to a team,
		based on the reverse links from each Golfer entities to a Team entity.
		When there is disagreement, we use this mapping as the "truth".
		"""
		self.golfers = []
		self.groups = []
		self.teams_by_golfer_id_rev = {}
		q = Sponsor.all().ancestor(self.root).filter("confirmed =", True).order("sort_name")
		for s in q:
			q = Golfer.all().ancestor(s.key()).order("sequence")
			group_golfer_nums = []
			for g in q.fetch(s.num_golfers):
				g_id = g.key().id()
				golfer_num = len(self.golfers) + 1
				t = None
				team_num = 0
				try:
					t = g.team
				except:
					logging.warning("Dangling reference from golfer %s %s (sponsor id %d) to deleted team" % (g.first_name, g.last_name, s.id))
					g.team = None
					g.put()
				vg = ViewGolfer(self.root, s, g, golfer_num)
				if t:
					t_id = t.key().id()
					team_num = self.teams_by_id[t_id]
					if not g_id in self.teams_by_golfer_id_fwd:
						logging.warning("Golfer %s (sponsor id %d) refers to team \"%s\", but no team contains golfer" % (vg.golfer_name, s.id, t.name))
					elif self.teams_by_golfer_id_fwd[g_id] != team_num:
						other_team_num = self.teams_by_golfer_id_fwd[g_id]
						other_team = self.teams[other_team_num - 1]
						logging.warning("Golfer %s (sponsor id %d) refers to team \"%s\", but is contained by team \"%s\"" % (vg.golfer_name, s.id, t.name, other_team['name']))
				else:
					t_id = -1
				self.teams_by_golfer_id_rev[g_id] = team_num
				if g_id in self.teams_by_golfer_id_fwd:
					team_num = self.teams_by_golfer_id_fwd[g_id]
				else:
					team_num = 0
				h = hashlib.md5()
				h.update("%d:%d" % (t_id, g.cart))
				golfer = {
					'golfer_num': golfer_num,
					'group_num': len(self.groups) + 1,
					'team_num': team_num,
					'key': g_id,
					'golfer_name': vg.golfer_name,
					'course_handicap': vg.course_handicap,
					'cart': g.cart,
					'md5': h.hexdigest()
				}
				if team_num:
					team = self.teams[team_num - 1]
					team['golfer_nums'].append(golfer_num)
				else:
					group_golfer_nums.append(golfer_num)
				self.golfers.append(golfer)
			group = {
				'group_num': len(self.groups) + 1,
				'key': s.key().id(),
				'id': str(s.id),
				'first_name': s.first_name,
				'last_name': s.last_name,
				'golfer_nums': group_golfer_nums,
				'pairing_prefs': s.pairing
			}
			self.groups.append(group)

	def check_consistency(self):
		for t in range(1, len(self.teams) + 1):
			team = self.teams[t - 1]
			for g_id in self.golfers_by_team[t - 1]:
				if not g_id in self.teams_by_golfer_id_rev:
					logging.warning("Team %d \"%s\" (%d) contains golfer %d, but golfer does not exist" % (t, team['name'], team['key'], g_id))
				elif self.teams_by_golfer_id_rev[g_id] != t:
					logging.warning("Team %d \"%s\" (%d) contains golfer %d, but golfer does not refer to team" % (t, team['name'], team['key'], g_id))
			if not team['golfer_nums']:
				logging.warning("Empty team \"%s\" (%d)" % (team['name'], team['key']))

	def groups_json(self):
		return json.dumps(self.groups)

	def teams_json(self):
		return json.dumps(self.teams)

	def golfers_json(self):
		return json.dumps(self.golfers)

class TeamsUpdater:
	def __init__(self, root, golfers_json, groups_json, teams_json):
		self.root = root
		self.golfers = json.loads(golfers_json)
		self.groups = json.loads(groups_json)
		self.teams = json.loads(teams_json)

	def update_teams_pass1(self):
		self.team_entities = []
		self.golfers_by_id = {}
		for t in self.teams:
			team_id = t['key']
			if team_id:
				team = Team.get_by_id(int(team_id), parent = self.root)
				if not team:
					logging.error("no team with id %s" % team_id)
					continue
			else:
				team = Team(parent = self.root)
			team.name = t['name']
			team.pairing = t['pairing_prefs']
			self.team_entities.append((t['team_num'], team))
			for golfer_num in t['golfer_nums']:
				g_id = self.golfers[golfer_num - 1]['key']
				self.golfers_by_id[g_id] = (None, False)
				# logging.debug("Update teams pass 1: team %d golfer %d" % (t['team_num'], g_id))

	def update_golfers_pass1(self):
		for g in self.golfers:
			g_id = g['key']
			team_num = g['team_num']
			if team_num:
				t_id = self.teams[team_num - 1]['key']
				if not t_id:
					t_id = 0
			else:
				t_id = -1
			h = hashlib.md5()
			h.update("%d:%d" % (t_id, g['cart']))
			modified = h.hexdigest() != g['md5']
			# logging.debug("Update golfers pass 1: team %d golfer %d (%s)" % (g['team_num'], g_id, "modified" if modified else "not modified"))
			if modified or g_id in self.golfers_by_id:
				group_num = g['group_num']
				group = self.groups[group_num - 1]
				s_id = group['key']
				s = Sponsor.get_by_id(s_id, parent = self.root)
				if not s:
					logging.error("no sponsor with key %d" % s_id)
					continue
				golfer = Golfer.get_by_id(g_id, parent = s)
				if not golfer:
					logging.error("no golfer with key %d" % g_id)
					continue
				if g['team_num'] == 0:
					golfer.team = None
				golfer.cart = g['cart']
				self.golfers_by_id[g_id] = (golfer, modified)

	def update_teams_pass2(self):
		new_team_num = 1
		self.team_renumber = []
		for (team_num, team) in self.team_entities:
			t = self.teams[team_num - 1]
			golfers_in_team = []
			golfers_to_update = []
			for golfer_num in t['golfer_nums']:
				g = self.golfers[golfer_num - 1]
				g_id = g['key']
				(golfer, modified) = self.golfers_by_id[g_id]
				# logging.debug("Update teams pass 2: team %d golfer %d (%s)" % (team_num, g_id, "modified" if modified else "not modified"))
				golfers_in_team.append(golfer.key())
				if modified:
					golfers_to_update.append(golfer)
			team.golfers = golfers_in_team
			if len(team.golfers) == 0:
				self.team_renumber.append(0)
				t['key'] = ''
				try:
					team.delete()
					logging.warning("Deleting empty team %d \"%s\"" % (team_num, team.name))
				except:
					logging.warning("Empty team %d \"%s\" not saved" % (team_num, team.name))
			else:
				self.team_renumber.append(new_team_num)
				new_team_num += 1
				try:
					t_id = team.key().id()
					logging.info("Updating team %d \"%s\" with %d golfers" % (team_num, team.name, len(team.golfers)))
				except:
					logging.info("Adding new team %d \"%s\" with %d golfers" % (team_num, team.name, len(team.golfers)))
				team.put()
				t['key'] = team.key().id()
				for golfer in golfers_to_update:
					golfer.team = team

	def update_golfers_pass2(self):
		for g_id in self.golfers_by_id:
			(golfer, modified) = self.golfers_by_id[g_id]
			if modified:
				logging.info("Updating golfer %s %s (%d)" % (golfer.first_name, golfer.last_name, golfer.key().id()))
				golfer.put()

	def update_json(self):
		for g in self.golfers:
			team_num = g['team_num']
			if team_num:
				g['team_num'] = self.team_renumber[team_num - 1]
				t_id = self.teams[team_num - 1]['key']
			else:
				t_id = -1
			h = hashlib.md5()
			h.update("%d:%d" % (t_id, g['cart']))
			g['md5'] = h.hexdigest()
		new_teams = []
		for t in self.teams:
			team_num = t['team_num']
			new_team_num = self.team_renumber[team_num - 1]
			if new_team_num:
				t['team_num'] = new_team_num
				new_teams.append(t)
		self.teams = new_teams

	def groups_json(self):
		return json.dumps(self.groups)

	def teams_json(self):
		return json.dumps(self.teams)

	def golfers_json(self):
		return json.dumps(self.golfers)

class Pairing(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		json_builder = JsonBuilder(root)
		template_values = {
			'messages': [],
			'groups_json': json_builder.groups_json(),
			'teams_json': json_builder.teams_json(),
			'golfers_json': json_builder.golfers_json(),
			'capabilities': caps
			}
		html = render_to_string('pairing.html', template_values)
		self.response.out.write(html)

	def complain(self, what):
		self.response.out.write('<html><head>\n')
		self.response.out.write('<title>Internal Error</title>\n')
		self.response.out.write('</head><body>\n')
		self.response.out.write('<h1>Internal Error</h1>\n')
		self.response.out.write('<p>%s</p>\n' % what)
		self.response.out.write('</body></html>\n')

	def post(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, '/admin/view/golfers/teams')
			return
		golfers_json = self.request.get('golfers_json')
		groups_json = self.request.get('groups_json')
		teams_json = self.request.get('teams_json')
		# logging.debug("golfers: " + golfers_json)
		# logging.debug("groups: " + groups_json)
		# logging.debug("teams: " + teams_json)
		updater = TeamsUpdater(root, golfers_json, groups_json, teams_json)
		updater.update_teams_pass1()
		updater.update_golfers_pass1()
		updater.update_teams_pass2()
		updater.update_golfers_pass2()
		updater.update_json()
		memcache.delete('2019/admin/view/golfers')
		template_values = {
			'messages': [],
			'groups_json': updater.groups_json(),
			'teams_json': updater.teams_json(),
			'golfers_json': updater.golfers_json(),
			'capabilities': caps
			}
		html = render_to_string('pairing.html', template_values)
		self.response.out.write(html)
		# self.redirect('/admin/view/golfers/teams')

def calculate_team_handicap(golfer_handicaps):
	try:
		handicaps = sorted([int(h) for h in golfer_handicaps])
	except:
		return "n/a"
	weight = 4.0
	sum = 0.0
	sum_of_weights = 0.0
	for i in range(0, len(handicaps)):
		sum += handicaps[i] * weight
		sum_of_weights += weight
		weight /= 2.0
	return int(round(sum / sum_of_weights * 0.75))

def sort_by_starting_hole(team):
	h = team['starting_hole']
	if len(h) == 2:
		h = '0' + h
	return h

class ViewGolfersByTeam(webapp2.RequestHandler):
	def get(self, bywhat):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		readonly = True if self.request.get('readonly') else False
		projection_fields = (
			'first_name', 'last_name', 'gender', 'cart', 'tees',
			'has_index', 'handicap_index', 'average_score'
		)
		golfers = db.Query(Golfer, projection=projection_fields).filter("active =", True).order("sort_name")
		golfers_by_key = {}
		for g in golfers:
			golfers_by_key[g.key().id()] = g
		teams = []
		q = Team.all().ancestor(root).order("name")
		for t in q:
			golfers_in_team = []
			course_handicaps = []
			for g_key in t.golfers:
				g_id = g_key.id()
				if not g_id in golfers_by_key:
					logging.warning("Golfer %d, referenced by team %s (%d) does not exist" % (g_id, t.name, t.key().id()))
					continue
				g = golfers_by_key[g_id]
				tees = get_tees(t.flight, g.gender)
				handicap_index = g.get_handicap_index()
				if handicap_index is not None:
					course_handicap = calc_course_handicap(root, handicap_index, tees)
				else:
					course_handicap = 'n/a'
				course_handicaps.append(course_handicap)
				golfer = {
					'first_name': g.first_name,
					'last_name': g.last_name,
					'cart': g.cart,
					'tees': tees,
					'course_handicap': course_handicap
				}
				golfers_in_team.append(golfer)
			team_handicap = calculate_team_handicap(course_handicaps)
			team = {
				'key': t.key().id(),
				'name': t.name,
				'starting_hole': t.starting_hole,
				'flight': t.flight,
				'golfers': golfers_in_team,
				'team_handicap': team_handicap
			}
			teams.append(team)
		if bywhat == 'bystart':
			teams.sort(key = sort_by_starting_hole)
		template_values = {
			'bywhat': bywhat,
			'teams': teams,
			'num_teams': len(teams),
			'readonly': readonly,
			'capabilities': caps
			}
		html = render_to_string('viewgolfersbyteam.html', template_values)
		self.response.out.write(html)

	def post(self, bywhat):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, '/admin/view/golfers/byteams')
			return
		num_teams = int(self.request.get('num_teams'))
		for i in range(1, num_teams + 1):
			t_id = int(self.request.get('team_%d_key' % i))
			starting_hole = self.request.get('team_%d_start' % i)
			team = Team.get_by_id(t_id, parent = root)
			if not team:
				logging.error("No team with id %d" % t_id)
			else:
				team.starting_hole = starting_hole
				team.put()
		self.redirect('/admin/view/golfers/%s' % bywhat)

class ViewDinners(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		html = memcache.get('2019/admin/view/dinners')
		if html:
			self.response.out.write(html)
			return
		all_dinners = []
		counter = 1
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("sort_name")
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
		memcache.add('2019/admin/view/dinners', html, 60*60*24)
		self.response.out.write(html)

class ViewTributeAds(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = TributeAd.all()
		q.ancestor(root)
		q.order("timestamp")
		ads = q.fetch(limit = None)
		template_values = {
			'ads': ads,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewtributeads.html', template_values))

def csv_encode(val):
	val = re.sub(r'"', '""', str(val or ''))
	return '"%s"' % val

class DownloadRegistrationsCSV(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
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
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("timestamp")
		csv = []
		csv.append(','.join(['first_name', 'last_name', 'gender', 'company',
							 'address', 'city', 'state', 'zip',
							 'email', 'phone', 'ghin_number', 'index',
							 'avg_score', 'tournament_index', 'course_handicap', 'tees',
							 'shirt_size', 'team', 'starting_hole', 'cart',
							 'contact_first_name', 'contact_last_name']))
		counter = 1
		for s in q:
			golfers = Golfer.all().ancestor(s.key()).order("sequence").fetch(s.num_golfers)
			for g in golfers:
				team_name = ''
				starting_hole = ''
				cart = ''
				flight = 1
				if g.team:
					team_name = g.team.name
					starting_hole = g.team.starting_hole
					flight = g.team.flight
				if g.cart:
					cart = str(g.cart)
				tees = get_tees(flight, g.gender)
				tees_str = ["Red", "White", "Blue"][tees - 1]
				handicap_index = g.get_handicap_index()
				if g.has_index:
					handicap_index_str = "%.1f" % handicap_index
					tournament_index = handicap_index_str
				elif handicap_index is not None:
					handicap_index_str = ''
					tournament_index = "%.1f" % handicap_index
				else:
					handicap_index_str = ''
					tournament_index = ''
				if handicap_index is not None:
					course_handicap = str(calc_course_handicap(root, handicap_index, tees))
				else:
					course_handicap = ''
				counter += 1
				csv.append(','.join([csv_encode(x)
									 for x in [g.first_name, g.last_name, g.gender, g.company,
											   g.address, g.city, g.state, g.zip,
											   g.email, g.phone, g.ghin_number, handicap_index_str,
											   g.average_score, tournament_index, course_handicap, tees_str,
											   g.shirt_size, team_name, starting_hole, cart,
											   s.first_name, s.last_name]]))
			for i in range(len(golfers) + 1, s.num_golfers + 1):
				csv.append(','.join([csv_encode(x)
									 for x in ['n/a', 'n/a', '', '',
											   '', '', '', '',
											   '', '', '', '',
											   '', '', '', '',
											   '', '', '', '',
											   s.first_name, s.last_name]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=golfers.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

class DownloadDinnersCSV(webapp2.RequestHandler):
	def get(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.all()
		q.ancestor(root)
		q.filter("confirmed =", True)
		q.order("timestamp")
		csv = []
		csv.append(','.join(['first_name', 'last_name', 'dinner_choice', 'seating_pref',
							 'contact_first_name', 'contact_last_name']))
		for s in q:
			q = Golfer.all().ancestor(s.key())
			golfers = q.fetch(s.num_golfers)
			for g in golfers:
				if g.dinner_choice != 'No Dinner':
					csv.append(','.join([csv_encode(x) for x in [g.first_name, g.last_name,
																 g.dinner_choice, s.dinner_seating,
																 s.first_name, s.last_name]]))
			for i in range(len(golfers) + 1, s.num_golfers + 1):
				csv.append(','.join([csv_encode(x) for x in ['n/a', 'n/a', '', s.dinner_seating,
															 s.first_name, s.last_name]]))
			guests = DinnerGuest.all().ancestor(s.key()).order("sequence").fetch(s.num_dinners)
			for g in guests:
				csv.append(','.join([csv_encode(x) for x in [g.first_name, g.last_name,
															 g.dinner_choice, s.dinner_seating,
															 s.first_name, s.last_name]]))
			for i in range(len(guests) + 1, s.num_dinners + 1):
				csv.append(','.join([csv_encode(x) for x in ['n/a', 'n/a', '', s.dinner_seating,
															 s.first_name, s.last_name]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=dinners.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

# Reminder E-mails

incomplete_email_template = """
Dear %s,

Thank you for registering for the Celebration Classic Dinner and
Golf Tournament! In order to prepare for this event, we need a
little more information from you. Please visit the following URL:

    http://www.celebrationclassic.org/register?id=%s

and check to make sure that you have provided all of the
following information for each golfer and dinner guest:

- Name
- GHIN number or average score (for golfers)
- Gender (for golfers)
- Dinner selection

If you have any questions, just reply to this email and we'll be
glad to assist.
"""

unpaid_email_template_part1 = """
Dear %s,

Thank you for registering for the Celebration Classic Dinner and
Golf Tournament! Our records show that you have not yet paid for
this event.  Please visit the following URL:

    http://www.celebrationclassic.org/register?id=%s

and choose a payment method at the bottom of the page. If you
have already paid by other means, or if we should cancel this
registration, please reply to this message and let us know.

If you are a GO campaign member, click the "Back to Step 1"
button to return to the first page, then check the GO box, enter
your discount code, and click "Apply".
"""

unpaid_email_template_part2 = """
Remember the last day to take advantage of the early-bird rate
is %s.
"""

unpaid_email_template_part3 = """
Please also check to make sure that you have provided all of the
following information for each golfer and dinner guest:

- Name
- GHIN number or average score (for golfers)
- Gender (for golfers)
- Dinner selection

If you have any questions, just reply to this email and we'll be
glad to assist.

Thank you for your participation and contribution to this event
which is so important to Shir Hadash. I look forward to seeing
you at the event.
"""

dinner_survey_template = """
Dear %s,

As you know, part of your golf package includes participation in
the dinner event immediately following the tournament. Please let
us know if you or anyone else in your foursome will not be
staying for the dinner. We will assume that you will be attending
the dinner unless you respond to this email to tell us that you
will not.

Thank you and we look forward to seeing you on May 18th.

If you would like to update any information you provided with
your registration, please visit the following URL:

    http://www.celebrationclassic.org/register?id=%s

If you have any questions, just reply to this email and we'll be
glad to assist.
"""

class SendEmail(webapp2.RequestHandler):
	def post(self, what):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		subject = "Your Celebration Classic Registration"
		sender = users.get_current_user().email()
		if what == 'incomplete':
			body_template = incomplete_email_template
		elif what == 'unpaid':
			today = datetime.datetime.now() - datetime.timedelta(hours=8)
			body_template = unpaid_email_template_part1
			if today.date() <= root.early_bird_deadline:
				early_bird_deadline = "%s %d, %d" % (root.early_bird_deadline.strftime("%B"),
													 root.early_bird_deadline.day,
													 root.early_bird_deadline.year)
				body_template += unpaid_email_template_part2 % early_bird_deadline
			body_template += unpaid_email_template_part3
		elif what == 'dinnersurvey':
			body_template = dinner_survey_template
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
				if dev_server:
					logging.info(body)
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
			show_login_page(self.response.out, self.request.uri)
			return
		which_auction = self.request.get('which_auction')
		if self.request.get('key'):
			key = self.request.get('key')
			if which_auction == 'l':
				item = auctionitem.AuctionItem.get(key)
			else:
				item = auctionitem.SilentAuctionItem.get(key)
			template_values = {
				'item': item,
				'which_auction': which_auction,
				'key': key,
				'upload_url': blobstore.create_upload_url('/admin/upload-auction'),
				'capabilities': caps
				}
			self.response.out.write(render_to_string('editauction.html', template_values))
		elif self.request.get('new'):
			if which_auction == 'l':
				auction_items = auctionitem.get_auction_items()
			else:
				auction_items = auctionitem.get_silent_auction_items()
			if auction_items:
				seq = auction_items[-1].sequence + 1
			else:
				seq = 1
			item = auctionitem.AuctionItem(sequence = seq)
			template_values = {
				'item': item,
				'which_auction': which_auction,
				'key': '',
				'upload_url': blobstore.create_upload_url('/admin/upload-auction'),
				'capabilities': caps
				}
			self.response.out.write(render_to_string('editauction.html', template_values))
		else:
			live_auction_items = auctionitem.get_auction_items()
			silent_auction_items = auctionitem.get_silent_auction_items()
			template_values = {
				'live_auction_items': live_auction_items,
				'silent_auction_items': silent_auction_items,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('adminauction.html', template_values))

class UploadAuctionItem(blobstore_handlers.BlobstoreUploadHandler):
	# Process the submitted info.
	def post(self):
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_auction:
			show_login_page(self.response.out, '/admin/auction')
			return
		auctionitem.clear_auction_item_cache()
		which_auction = self.request.get('which_auction')
		key = self.request.get('key')
		if which_auction == 'l':
			if key:
				item = auctionitem.AuctionItem.get(key)
			else:
				item = auctionitem.AuctionItem(parent = root)
		else:
			if key:
				item = auctionitem.SilentAuctionItem.get(key)
			else:
				item = auctionitem.SilentAuctionItem(parent = root)
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
			show_login_page(self.response.out, '/admin/edit')
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
			show_login_page(self.response.out, '/admin/edit')
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
			show_login_page(self.response.out, '/admin/edit')
			return
		pages = []
		for name in detailpage.detail_page_list():
			path = name if name != "home" else ""
			published_version = detailpage.get_published_version(name)
			draft_version = detailpage.get_draft_version(name)
			page = detailpage.get_detail_page(name, True)
			page_info = {
				'name': name,
				'path': path,
				'published_version': published_version,
				'draft_version': draft_version,
				'is_draft': draft_version > published_version,
				'last_modified': page.last_modified.replace(tzinfo=tz.utc).astimezone(tz.pacific)
				}
			pages.append(page_info)
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
			show_login_page(self.response.out, '/admin/edit')
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

class DeleteHandler(webapp2.RequestHandler):
	def get(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, '/admin/delete-registrations')
			return
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		q = Sponsor.all()
		q.ancestor(root)
		q.order("timestamp")
		sponsors = q.fetch(limit = None)
		template_values = {
			'sponsors': sponsors,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('deleteregistrations.html', template_values))

	def post(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, '/admin/delete-registrations')
			return
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if self.request.get('delete'):
			ids_to_delete = self.request.get_all('selected_items')
			for id in ids_to_delete:
				s = Sponsor.all().ancestor(root).filter('id =', int(id)).get()
				golfers = Golfer.all().ancestor(s.key()).fetch(limit = None, keys_only = True)
				db.delete(golfers)
				guests = DinnerGuest.all().ancestor(s.key()).fetch(limit = None, keys_only = True)
				db.delete(guests)
				s.delete()
		self.redirect('/admin/delete-registrations')

class UpgradeHandler(webapp2.RequestHandler):
	def get(self):
		start = int(self.request.get('start') or 0)
		count = self.request.get('count')
		self.response.out.write('<html><head><title>Upgrade</title></head>')
		if count:
			self.response.out.write('<p>Upgraded %s records.</p>' % count)
		self.response.out.write('<body><form action="/admin/upgrade" method="post">')
		self.response.out.write('<input type="text" name="start" value="%d">' % start)
		self.response.out.write('<input type="submit" name="upgrade" value="Upgrade">')
		self.response.out.write('</form></body></html>')

	def post(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, '/admin/delete-registrations')
			return
		root = tournament.get_tournament()
		start = int(self.request.get('start'))
		q = Sponsor.all().ancestor(root).order("timestamp")
		sponsors = q.fetch(offset = start, limit = 20)
		for s in sponsors:
			s.sort_name = s.last_name.lower() + ',' + s.first_name.lower()
			s.put()
		count = len(sponsors)
		logging.info("Upgraded registrations %d through %d" % (start, start + count - 1))
		self.redirect('/admin/upgrade?start=%d&count=%d' % (start + count, count))

app = webapp2.WSGIApplication([('/admin/sponsorships', Sponsorships),
							   ('/admin/users', ManageUsers),
							   ('/admin/tournament', ManageTournament),
							   ('/admin/payments', PaymentGateway),
							   ('/admin/auction', ManageAuction),
							   ('/admin/upload-auction', UploadAuctionItem),
							   ('/admin/upload-file', UploadFile),
							   ('/admin/delete-file', DeleteFile),
							   ('/admin/view/registrations', ViewRegistrations),
							   ('/admin/view/incomplete', ViewIncomplete),
							   ('/admin/view/unpaid', ViewUnpaid),
							   ('/admin/view/unconfirmed', ViewUnconfirmed),
							   ('/admin/view/dinnersurvey', ViewDinnerSurvey),
							   ('/admin/view/golfers', ViewGolfers),
							   ('/admin/view/golfers/byname', ViewGolfersByName),
							   ('/admin/view/golfers/(byteam)', ViewGolfersByTeam),
							   ('/admin/view/golfers/(bystart)', ViewGolfersByTeam),
							   ('/admin/view/golfers/handicap', UpdateHandicap),
							   ('/admin/view/golfers/pairing', Pairing),
							   ('/admin/view/dinners', ViewDinners),
							   ('/admin/view/tribute', ViewTributeAds),
							   ('/admin/csv/registrations', DownloadRegistrationsCSV),
							   ('/admin/csv/golfers', DownloadGolfersCSV),
							   ('/admin/csv/dinners', DownloadDinnersCSV),
							   ('/admin/handicap', ViewGolfersByName),
							   ('/admin/mail/(.*)', SendEmail),
							   ('/admin/edit', EditPageHandler),
							   ('/admin/delete-registrations', DeleteHandler),
							   ('/admin/logout', Logout),
							   ('/admin/upgrade', UpgradeHandler)],
							  debug=dev_server)
