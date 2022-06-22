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
from google.appengine.ext import ndb
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
import auditing
from sponsor import Sponsor, Team, Golfer, Substitute, DinnerGuest, TributeAd, get_handicap_index

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

def make_bitmask(*caps):
	bitmask = 0
	for cap in caps:
		bitmask = bitmask << 1
		if cap:
			bitmask = bitmask | 1
	return bitmask

class ManageUsers(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, self.request.uri)
			return
		caps = capabilities.get_current_user_caps()
		q = capabilities.all_caps()
		q = q.order(capabilities.Capabilities.email)
		allcaps = q.fetch(30)
		for u in allcaps:
			u.capbits = make_bitmask(u.can_update_sponsorships,
									 u.can_view_registrations,
									 u.can_add_registrations,
									 u.can_update_auction,
									 u.can_edit_content,
									 u.can_edit_tournament_properties,
									 u.can_edit_payment_processor)
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
		count = int(self.request.get('count'))
		updated_records = [ ]
		for i in range(1, count + 1):
			email = self.request.get('email%d' % i)
			us = True if self.request.get('us%d' % i) == 'u' else False
			vr = True if self.request.get('vr%d' % i) == 'v' else False
			ar = True if self.request.get('ar%d' % i) == 'a' else False
			ua = True if self.request.get('ua%d' % i) == 'u' else False
			ec = True if self.request.get('ec%d' % i) == 'e' else False
			et = True if self.request.get('et%d' % i) == 't' else False
			pp = True if self.request.get('pp%d' % i) == 'p' else False
			orig_capbits = int(self.request.get('capbits%d' % i))
			new_capbits = make_bitmask(us, vr, ar, ua, ec, et, pp)
			if orig_capbits != new_capbits:
				u = capabilities.get_caps(email)
				logging.info("updating user %s: orig caps %02x new caps %02x" % (email, orig_capbits, new_capbits))
				if u.email is None:
					logging.error("user %d not found" % email)
				else:
					u.can_update_sponsorships = us
					u.can_view_registrations = vr
					u.can_add_registrations = ar
					u.can_update_auction = ua
					u.can_edit_content = ec
					u.can_edit_tournament_properties = et
					u.can_edit_payment_processor = pp
					updated_records.append(u)
					u.audit()
		if updated_records:
			ndb.put_multi(updated_records)
		email = self.request.get('email')
		if email:
			us = True if self.request.get('us') == 'u' else False
			vr = True if self.request.get('vr') == 'v' else False
			ar = True if self.request.get('ar') == 'a' else False
			ua = True if self.request.get('ua') == 'u' else False
			ec = True if self.request.get('ec') == 'e' else False
			et = True if self.request.get('et') == 't' else False
			pp = True if self.request.get('pp') == 'p' else False
			new_capbits = make_bitmask(us, vr, ar, ua, ec, et, pp)
			logging.info("adding user %s: caps %02x" % (email, new_capbits))
			capabilities.add_user(email = email,
								  can_update_sponsorships = us,
								  can_view_registrations = vr,
								  can_add_registrations = ar,
								  can_update_auction = ua,
								  can_edit_content = ec,
								  can_edit_tournament_properties = et,
								  can_edit_payment_processor = pp)
		memcache.flush_all()
		self.redirect('/admin/users')

def reinitialize_counters(t):
	counters = tournament.get_counters(t)
	q = Sponsor.query(ancestor = t.key)
	q = q.filter(Sponsor.confirmed == True)
	q = q.order(Sponsor.timestamp)
	num_golfers = 0
	num_dinners = 0
	for s in q:
		num_golfers += s.num_golfers + s.num_golfers_no_dinner
		num_dinners += s.num_golfers + s.num_dinners
	counters.golfer_count = num_golfers
	counters.dinner_count = num_dinners
	counters.put()
	logging.info("updated golfer_count = %d, dinner_count = %d" % (num_golfers, num_dinners))

# Tournament properties

class ManageTournament(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_tournament_properties:
			show_login_page(self.response.out, self.request.uri)
			return
		t = tournament.get_tournament(self.request.get("t"))
		if t.dinner_early_bird_deadline is None:
			t.dinner_early_bird_deadline = t.early_bird_deadline
		counters = tournament.get_counters(t)
		template_values = {
			'capabilities': caps,
			'tournament': t,
			'counters': counters
			}
		self.response.out.write(render_to_string('tournament.html', template_values))

	# Process the submitted info.
	def post(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_tournament_properties:
			show_login_page(self.response.out, '/admin/tournament')
			return
		t = tournament.get_tournament(self.request.get("original_name"))
		if self.request.get("num_golfers") == "" or self.request.get("num_dinners") == "":
			reinitialize_counters(t)
		t.name = self.request.get("new_name")
		t.published = (self.request.get("published") == "y")
		t.accepting_registrations = (self.request.get("accepting") == "y")
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
		dinner_early_bird_month = int(self.request.get("dinner_early_bird_month"))
		dinner_early_bird_day = int(self.request.get("dinner_early_bird_day"))
		dinner_early_bird_year = int(self.request.get("dinner_early_bird_year"))
		t.dinner_early_bird_deadline = datetime.date(dinner_early_bird_year, dinner_early_bird_month, dinner_early_bird_day)
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
		t.golf_only_price_early = int(self.request.get("golf_only_price_early"))
		t.golf_only_price_late = int(self.request.get("golf_only_price_late"))
		t.dinner_price_early = int(self.request.get("dinner_price_early"))
		t.dinner_price_late = int(self.request.get("dinner_price_late"))
		t.limit_golfers = int(self.request.get("limit_golfers"))
		t.limit_dinners = int(self.request.get("limit_dinners"))
		t.golf_sold_out = (self.request.get("golf_sold_out") == "y")
		t.dinner_sold_out = (self.request.get("dinner_sold_out") == "y")
		t.wait_list_email = self.request.get("wait_list_email")
		t.dinner_choices = self.request.get("dinner_choices")
		t.go_discount_codes = self.request.get("go_discount_codes")
		t.red_course_rating = float(self.request.get("red_course_rating"))
		t.red_course_slope = float(self.request.get("red_course_slope"))
		t.white_course_rating = float(self.request.get("white_course_rating"))
		t.white_course_slope = float(self.request.get("white_course_slope"))
		t.blue_course_rating = float(self.request.get("blue_course_rating"))
		t.blue_course_slope = float(self.request.get("blue_course_slope"))
		t.put()
		tournament.set_tournament_cache(t)
		auditing.audit(t, "Updated tournament properties", request = self.request)
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
		payment_gateway = payments.Payments.query(ancestor = t.key).get()
		if payment_gateway is None:
			payment_gateway = payments.Payments(parent = t.key)
		payment_gateway.gateway_url = self.request.get("gateway_url")
		payment_gateway.relay_url = self.request.get("relay_url")
		payment_gateway.receipt_url = self.request.get("receipt_url")
		payment_gateway.api_login_id = self.request.get("api_login_id")
		payment_gateway.transaction_key = self.request.get("transaction_key")
		payment_gateway.test_mode = self.request.get("test_mode") == "true"
		payment_gateway.put()
		auditing.audit(t, "Updated payment gateway", request = self.request)
		self.redirect('/admin/payments')

# Sponsorship information.

class Sponsorships(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_sponsorships:
			show_login_page(self.response.out, self.request.uri)
			return
		t = tournament.get_tournament()
		sponsorships = sponsorship.Sponsorship.query(ancestor = t.key).order(sponsorship.Sponsorship.sequence).fetch(30)
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
		t = tournament.get_tournament()
		sponsorship.clear_sponsorships_cache()
		count = int(self.request.get('count'))
		for i in range(1, count + 1):
			name = self.request.get('name%d' % i)
			q = sponsorship.Sponsorship.query(ancestor = t.key)
			q = q.filter(sponsorship.Sponsorship.name == name)
			s = q.get()
			if self.request.get('delete%d' % i) == 'd':
				auditing.audit(t, "Deleted Sponsorship", data = s.level + "/" + s.name, request = self.request)
				s.key.delete()
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
					auditing.audit(t, "Updated Sponsorship", data = s.level + "/" + name, request = self.request)
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
			s = sponsorship.Sponsorship(parent = t.key,
										name = name,
										level = level,
										sequence = int(sequence),
										price = int(price),
										golfers_included = int(golfers_included),
										unique = unique,
										sold = sold)
			s.put()
			auditing.audit(t, "Added Sponsorship", data = level + "/" + name, request = self.request)
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
		self.golfer_key = g.key.urlsafe()
		if s:
			self.sponsor_id = s.sponsor_id
			self.sponsor_name = s.first_name + " " + s.last_name
		if g.substitute:
			g1 = g.substitute.get()
			self.has_substitute = True
		else:
			g1 = g
			self.has_substitute = False
		self.golfer = g1
		self.sequence = g.sequence
		team = None
		if g.team:
			team = g.team.get()
		if g1.first_name or g1.last_name:
			self.golfer_name = g1.first_name + " " + g1.last_name
			if self.has_substitute:
				self.golfer_name = "*" + self.golfer_name
		elif s:
			self.golfer_name = "(%s #%d)" % (s.last_name, g.sequence)
		else:
			self.golfer_name = "(TBD)"
		self.count = count
		if s:
			self.pairing = s.pairing if g.sequence == s.num_golfers + s.num_golfers_no_dinner else '' # TODO: remove this
		self.team_name = team.name if team else '-'
		self.starting_hole = team.starting_hole if team else ''
		self.cart = g.cart
		if g1.tees:
			self.tees = g1.tees
		else:
			flight = 1
			if team:
				flight = team.flight
			self.tees = get_tees(flight, g1.gender)
		handicap_index = get_handicap_index(g1)
		if g1.has_index:
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
			self.course_handicap = 'n/a'

class ViewDinner(object):
	def __init__(self, s, first_name, last_name, choice, sequence, table_num, count):
		self.sponsor_id = s.sponsor_id
		self.sponsor_name = s.first_name + " " + s.last_name
		if first_name or last_name:
			self.guest_name = first_name + " " + last_name
		else:
			self.guest_name = "(%s #%d)" % (s.last_name, sequence)
		self.dinner_choice = choice
		self.sequence = sequence
		self.count = count
		self.table_num = str(table_num) if table_num > 0 else ""
		self.seating = s.dinner_seating if sequence == s.num_golfers + s.num_dinners else ''

class ViewRegistrations(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		if self.request.get('sort') == 'date':
			q = q.order(Sponsor.timestamp)
		else:
			q = q.order(Sponsor.sort_name)
		sponsors = q.fetch(limit = None)
		golfer_count = 0
		dinner_count = 0
		for s in sponsors:
			no_dinners = 0
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers:
				golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
				for g in golfers:
					if g.dinner_choice == 'none':
						no_dinners += 1
			s.total_golfers = total_golfers
			s.adjusted_dinners = total_golfers - no_dinners + s.num_dinners
			s.flag_dinners = True if no_dinners != s.num_golfers_no_dinner else False
			s.net_due = s.payment_due - s.payment_made
			if s.discount:
				s.net_due -= s.discount
			s.net_due = max(0, s.net_due)
			golfer_count += total_golfers
			dinner_count += total_golfers - no_dinners + s.num_dinners
		template_values = {
			'sponsors': sponsors,
			'sponsor_count': len(sponsors),
			'golfer_count': golfer_count,
			'dinner_count': dinner_count,
			'incomplete': '',
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewsponsors.html', template_values))

class ViewIncomplete(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.sort_name)
		sponsors = []
		for s in q:
			golfers_complete = 0
			ndinners = 0
			no_dinners = 0
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers:
				golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
				for g in golfers:
					if g.first_name and g.last_name and g.gender and (g.ghin_number or g.has_index or g.average_score):
						golfers_complete += 1
					if g.dinner_choice:
						ndinners += 1
					if g.dinner_choice == 'none':
						no_dinners += 1
			if s.num_dinners:
				guests = ndb.get_multi(s.dinner_keys[:s.num_dinners])
				for g in guests:
					if g.first_name and g.last_name and g.dinner_choice:
						ndinners += 1
			s.total_golfers = total_golfers
			s.adjusted_dinners = total_golfers - no_dinners + s.num_dinners
			s.flag_dinners = True if no_dinners != s.num_golfers_no_dinner else False
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.sort_name)
		sponsors = []
		for s in q:
			no_dinners = 0
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers:
				golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
				for g in golfers:
					if g.dinner_choice == 'none':
						no_dinners += 1
			s.total_golfers = total_golfers
			s.adjusted_dinners = total_golfers - no_dinners + s.num_dinners
			s.flag_dinners = True if no_dinners != s.num_golfers_no_dinner else False
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.sort_name)
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == False)
		q = q.order(Sponsor.timestamp)
		sponsors = q.fetch(100)
		for s in sponsors:
			s.total_golfers = s.num_golfers + s.num_golfers_no_dinner
			s.adjusted_dinners = s.num_golfers + s.num_dinners
			s.flag_dinners = True if no_dinners != s.num_golfers_no_dinner else False
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		# html = memcache.get('%s/admin/view/golfers' % t.name)
		# if html:
		#	self.response.out.write(html)
		#	return
		all_golfers = []
		counter = 1
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.sort_name)
		for s in q:
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers == 0:
				continue
			golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
			for g in golfers:
				all_golfers.append(ViewGolfer(t, s, g, counter))
				counter += 1
			for i in range(len(golfers) + 1, total_golfers + 1):
				g = Golfer(tournament = t.key, sponsor = s.key, sequence = i,
						   sort_name = '', first_name = '', last_name = '', gender = '',
						   company = '', address = '', city = '', phone = '', email = '',
						   handicap_index = 0.0, average_score = '', ghin_number = '',
						   shirt_size = '', dinner_choice = '')
				all_golfers.append(ViewGolfer(t, s, g, counter))
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
		self.response.out.write(html)

class ViewGolfersByName(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		all_golfers = []
		q = Golfer.query()
		q = q.filter(Golfer.tournament == t.key)
		q = q.filter(Golfer.active == True)
		q = q.order(Golfer.sort_name)
		counter = 1
		for g in q:
			s = g.sponsor.get()
			all_golfers.append(ViewGolfer(t, s, g, counter))
			counter += 1
		template_values = {
			'golfers': all_golfers,
			'capabilities': caps
			}
		html = render_to_string('viewgolfersbyname.html', template_values)
		self.response.out.write(html)

class UpdateHandicap(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		start = 1
		if self.request.get('start'):
			start = int(self.request.get('start'))
		all_golfers = []
		q = Golfer.query()
		q = q.filter(Golfer.tournament == t.key)
		q = q.filter(Golfer.active == True)
		q = q.order(Golfer.sort_name)
		golfer_keys = q.fetch(offset = start - 1, limit = 21, keys_only = True)
		prev_page_offset = 0 if start == 1 else max(1, start - 20)
		next_page_offset = 0
		if len(golfer_keys) == 21:
			next_page_offset = start + 20
			golfer_keys = golfer_keys[:20]
		counter = start
		golfers = ndb.get_multi(golfer_keys)
		for g in golfers:
			s = g.sponsor.get()
			vg = ViewGolfer(t, s, g, counter)
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, '/admin/view/golfers/handicap')
			return
		prev_page_offset = int(self.request.get('prev_page_offset'))
		this_page_offset = int(self.request.get('this_page_offset'))
		next_page_offset = int(self.request.get('next_page_offset'))
		count = int(self.request.get('count'))
		golfers_to_update = []
		for i in range(this_page_offset, this_page_offset + count):
			key = ndb.Key(urlsafe = self.request.get('key_%d' % i))
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
				g = key.get()
			except:
				logging.error("Invalid key for golfer #%d" % i)
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
			golfers_to_update.append(g)
		if golfers_to_update:
			ndb.put_multi(golfers_to_update)
		if self.request.get('prevpage'):
			self.redirect('/admin/view/golfers/handicap?start=%d' % prev_page_offset)
		elif self.request.get('nextpage'):
			self.redirect('/admin/view/golfers/handicap?start=%d' % next_page_offset)
		else:
			self.redirect('/admin/view/golfers/handicap?start=%d' % this_page_offset)

class JsonBuilder:
	def __init__(self, t):
		self.t = t
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
		q = Team.query(ancestor = self.t.key).order(Team.name)
		for t in q:
			t_id = t.key.id()
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
		self.substitutes = []
		self.groups = []
		self.teams_by_golfer_id_rev = {}
		q = Sponsor.query(ancestor = self.t.key).filter(Sponsor.confirmed == True).order(Sponsor.sort_name)
		for s in q:
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers == 0:
				continue
			group_golfer_nums = []
			for g in ndb.get_multi(s.golfer_keys[:total_golfers]):
				g_id = g.key.id()
				golfer_num = len(self.golfers) + 1
				team = None
				team_num = 0
				if g.team:
					try:
						team = g.team.get()
					except:
						logging.warning("Dangling reference from golfer %d (sponsor id %d) to deleted team" % (g_id, s.sponsor_id))
						g.team = None
						g.put()
				if team:
					t_id = team.key.id()
					team_num = self.teams_by_id[t_id]
					if not g_id in self.teams_by_golfer_id_fwd:
						logging.warning("Golfer %d (sponsor id %d) refers to team \"%s\", but no team contains golfer" % (g_id, s.sponsor_id, t.name))
					elif self.teams_by_golfer_id_fwd[g_id] != team_num:
						other_team_num = self.teams_by_golfer_id_fwd[g_id]
						other_team = self.teams[other_team_num - 1]
						logging.warning("Golfer %d (sponsor id %d) refers to team \"%s\", but is contained by team \"%s\"" % (g_id, s.sponsor_id, t.name, other_team['name']))
				else:
					t_id = -1
				self.teams_by_golfer_id_rev[g_id] = team_num
				if g_id in self.teams_by_golfer_id_fwd:
					team_num = self.teams_by_golfer_id_fwd[g_id]
				else:
					team_num = 0
				if g.substitute:
					g_sub = g.substitute.get()
					hdcp_index = get_handicap_index(g_sub)
					if hdcp_index is not None:
						hdcp_index = "%.1f" % hdcp_index
					else:
						hdcp_index = "-"
					substitute = {
						'key': g.substitute.id(),
						'first_name': g_sub.first_name,
						'last_name': g_sub.last_name,
						'gender': g_sub.gender,
						'ghin': g_sub.ghin_number,
						'avg': g_sub.average_score,
						'index': hdcp_index
					}
					self.substitutes.append(substitute)
					substitute_index = len(self.substitutes)
				else:
					substitute_index = 0
				hdcp_index = get_handicap_index(g)
				if hdcp_index is not None:
					hdcp_index = "%.1f" % hdcp_index
				else:
					hdcp_index = "-"
				h = hashlib.md5()
				h.update(','.join(str(x) for x in [t_id, g.cart]))
				golfer = {
					'golfer_num': golfer_num,
					'group_num': len(self.groups) + 1,
					'team_num': team_num,
					'key': g_id,
					'first_name': g.first_name,
					'last_name': g.last_name,
					'gender': g.gender,
					'index': hdcp_index,
					'cart': g.cart,
					'substitute': substitute_index,
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
				'key': s.key.id(),
				'id': str(s.sponsor_id),
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

	def substitutes_json(self):
		return json.dumps(self.substitutes)

class TeamsUpdater:
	def __init__(self, t, golfers_json, substitutes_json, groups_json, teams_json):
		self.t = t
		self.golfers = json.loads(golfers_json)
		self.substitutes = json.loads(substitutes_json)
		self.groups = json.loads(groups_json)
		self.teams = json.loads(teams_json)

	def update_teams_pass1(self):
		self.team_entities = []
		self.golfers_by_id = {}
		for t in self.teams:
			team_id = t['key']
			if team_id:
				team = Team.get_by_id(int(team_id), parent = self.t.key)
				if not team:
					logging.error("no team with id %s" % team_id)
					continue
			else:
				team = Team(parent = self.t.key)
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
			h.update(','.join(str(x) for x in [t_id, g['cart']]))
			modified = h.hexdigest() != g['md5']
			# logging.debug("Update golfers pass 1: team %d golfer %d (%s)" % (g['team_num'], g_id, "modified" if modified else "not modified"))
			if modified or g_id in self.golfers_by_id:
				group_num = g['group_num']
				group = self.groups[group_num - 1]
				s_id = group['key']
				s = Sponsor.get_by_id(s_id, parent = self.t.key)
				if not s:
					logging.error("no sponsor with key %d" % s_id)
					continue
				golfer = Golfer.get_by_id(g_id)
				if not golfer:
					logging.error("no golfer with key %d" % g_id)
					continue
				if g['team_num'] == 0:
					golfer.team = None
				golfer.cart = g['cart']
				self.golfers_by_id[g_id] = (golfer, modified)

	def update_substitutes(self):
		for g in self.golfers:
			g_id = g['key']
			if g_id in self.golfers_by_id:
				(golfer, _) = self.golfers_by_id[g_id]
			else:
				golfer = Golfer.get_by_id(g_id)
			if g['substitute'] > 0:
				sub = self.substitutes[g['substitute'] - 1]
				sub_id = sub['key']
				if sub_id:
					if golfer.substitute is None or golfer.substitute.id() != sub_id:
						logging.warning("Golfer %d substitute does not match Substitute %d" % (g_id, sub_id))
					substitute = Substitute.get_by_id(sub_id)
				else:
					substitute = Substitute()
				substitute.first_name = sub['first_name']
				substitute.last_name = sub['last_name']
				substitute.gender = sub['gender']
				substitute.ghin_number = sub['ghin']
				if sub['index']:
					try:
						substitute.handicap_index = float(sub['index'])
						substitute.has_index = True
					except ValueError:
						substitute.handicap_index = 0.0
						substitute.has_index = False
				else:
					substitute.handicap_index = 0.0
					substitute.has_index = False
				substitute.average_score = sub['avg']
				substitute.put()
				golfer.substitute = substitute.key
				golfer.sort_name = substitute.last_name.lower() + ',' + substitute.first_name.lower()
				self.golfers_by_id[g_id] = (golfer, True)
			elif golfer.substitute:
				golfer.substitute.delete()
				golfer.substitute = None
				golfer.sort_name = golfer.last_name.lower() + ',' + golfer.first_name.lower()
				self.golfers_by_id[g_id] = (golfer, True)

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
				golfers_in_team.append(golfer.key)
				if modified:
					golfers_to_update.append(golfer)
			team.golfers = golfers_in_team
			if len(team.golfers) == 0:
				self.team_renumber.append(0)
				t['key'] = ''
				try:
					team.key.delete()
					logging.warning("Deleting empty team %d \"%s\"" % (team_num, team.name))
				except:
					logging.warning("Empty team %d \"%s\" not saved" % (team_num, team.name))
			else:
				self.team_renumber.append(new_team_num)
				new_team_num += 1
				try:
					t_id = team.key.id()
					logging.info("Updating team %d \"%s\" with %d golfers" % (team_num, team.name, len(team.golfers)))
				except:
					logging.info("Adding new team %d \"%s\" with %d golfers" % (team_num, team.name, len(team.golfers)))
				team.put()
				t['key'] = team.key.id()
				for golfer in golfers_to_update:
					golfer.team = team.key

	def update_golfers_pass2(self):
		for g_id in self.golfers_by_id:
			(golfer, modified) = self.golfers_by_id[g_id]
			if modified:
				logging.info("Updating golfer %s %s (%d)" % (golfer.first_name, golfer.last_name, golfer.key.id()))
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

	def substitutes_json(self):
		return json.dumps(self.substitutes)

class Pairing(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		json_builder = JsonBuilder(t)
		template_values = {
			'messages': [],
			'groups_json': json_builder.groups_json(),
			'teams_json': json_builder.teams_json(),
			'golfers_json': json_builder.golfers_json(),
			'substitutes_json': json_builder.substitutes_json(),
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, '/admin/view/golfers/teams')
			return
		golfers_json = self.request.get('golfers_json')
		groups_json = self.request.get('groups_json')
		substitutes_json = self.request.get('substitutes_json')
		teams_json = self.request.get('teams_json')
		if dev_server:
			logging.debug("golfers: " + golfers_json)
			logging.debug("substitutes: " + substitutes_json)
			logging.debug("groups: " + groups_json)
			logging.debug("teams: " + teams_json)
		updater = TeamsUpdater(t, golfers_json, substitutes_json, groups_json, teams_json)
		updater.update_teams_pass1()
		updater.update_golfers_pass1()
		updater.update_substitutes()
		updater.update_teams_pass2()
		updater.update_golfers_pass2()
		updater.update_json()
		template_values = {
			'messages': [],
			'groups_json': updater.groups_json(),
			'teams_json': updater.teams_json(),
			'golfers_json': updater.golfers_json(),
			'substitutes_json': updater.substitutes_json(),
			'capabilities': caps
			}
		html = render_to_string('pairing.html', template_values)
		self.response.out.write(html)
		# self.redirect('/admin/view/golfers/teams')

def calculate_team_handicap(golfer_handicaps):
	try:
		handicaps = [int(h) for h in golfer_handicaps]
	except:
		return "n/a"
	handicaps.sort()
	weights = [0.50, 0.25, 0.15, 0.10]
	scale = 1.0
	sum = 0.0
	sum_of_weights = 0.0
	for i in range(0, min(4, len(handicaps))):
		sum += handicaps[i] * weights[i]
		sum_of_weights += weights[i]
	return int(round(sum * scale / sum_of_weights))

def sort_by_starting_hole(team):
	h = team['starting_hole']
	if len(h) == 2:
		h = '0' + h
	return h

class ViewGolfersByTeam(webapp2.RequestHandler):
	def get(self, bywhat):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		readonly = True if self.request.get('readonly') else False
		q = Golfer.query()
		q = q.filter(Golfer.tournament == t.key)
		q = q.filter(Golfer.active == True)
		q = q.order(Golfer.sort_name)
		golfer_keys = set(q.fetch(limit = None, keys_only = True))
		used_keys = set()
		teams = []
		q = Team.query(ancestor = t.key).order(Team.name)
		for team in q:
			golfers_in_team = []
			course_handicaps = []
			sequence = 0
			for g_key in team.golfers:
				sequence += 1
				g_id = g_key.id()
				if not g_key in golfer_keys:
					logging.warning("Golfer %d, referenced by team %s (%d), does not exist" % (g_key.id(), team.name, team.key.id()))
					continue
				if g_key in used_keys:
					logging.warning("Golfer %d, referenced by team %s (%d), is in another team" % (g_key.id(), team.name, team.key.id()))
				used_keys.add(g_key)
				g = g_key.get()
				vg = ViewGolfer(t, None, g, None)
				course_handicaps.append(vg.course_handicap)
				golfers_in_team.append(vg)
			team_handicap = calculate_team_handicap(course_handicaps)
			newteam = {
				'key': team.key.id(),
				'name': team.name,
				'starting_hole': team.starting_hole,
				'flight': team.flight,
				'golfers': golfers_in_team,
				'team_handicap': team_handicap
			}
			teams.append(newteam)
		if bywhat == 'bystart':
			teams.sort(key = sort_by_starting_hole)
		unassigned_golfers = []
		for g_key in golfer_keys - used_keys:
			g = g_key.get()
			if g.first_name or g.last_name:
				fname = g.first_name
				lname = g.last_name
			else:
				fname = "(%s #%d)" % (team.name, g.sequence)
				lname = ""
			golfer = {
				'first_name': fname,
				'last_name': lname,
			}
			unassigned_golfers.append(golfer)
		template_values = {
			'bywhat': bywhat,
			'teams': teams,
			'num_teams': len(teams),
			'unassigned_golfers': unassigned_golfers,
			'readonly': readonly,
			'capabilities': caps
			}
		html = render_to_string('viewgolfersbyteam.html', template_values)
		self.response.out.write(html)

	def post(self, bywhat):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, '/admin/view/golfers/byteams')
			return
		num_teams = int(self.request.get('num_teams'))
		for i in range(1, num_teams + 1):
			t_id = int(self.request.get('team_%d_key' % i))
			starting_hole = self.request.get('team_%d_start' % i)
			team = Team.get_by_id(t_id, parent = t.key)
			if not team:
				logging.error("No team with id %d" % t_id)
			elif team.starting_hole != starting_hole:
				team.starting_hole = starting_hole
				team.put()
		self.redirect('/admin/view/golfers/%s' % bywhat)

class ViewDinners(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		# html = memcache.get('%s/admin/view/dinners' % t.name)
		# if html:
		#	self.response.out.write(html)
		#	return
		all_dinners = []
		counter = 1
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.sort_name)
		for s in q:
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers:
				golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
				for g in golfers:
					if g.dinner_choice != 'none':
						all_dinners.append(ViewDinner(s, g.first_name, g.last_name, g.dinner_choice, g.sequence, g.table_num, counter))
						counter += 1
				for i in range(len(golfers) + 1, total_golfers + 1):
					all_dinners.append(ViewDinner(s, '', '', '', i, 0, counter))
					counter += 1
			if s.num_dinners:
				guests = ndb.get_multi(s.dinner_keys[:s.num_dinners])
				for g in guests:
					all_dinners.append(ViewDinner(s, g.first_name, g.last_name, g.dinner_choice, g.sequence + s.num_golfers, g.table_num, counter))
					counter += 1
				for i in range(len(guests) + 1, s.num_dinners + 1):
					all_dinners.append(ViewDinner(s, '', '', '', i + s.num_golfers, 0, counter))
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
		self.response.out.write(html)

class AssignSeating(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		groups = []
		guests = []
		q = Sponsor.query(ancestor = t.key).filter(Sponsor.confirmed == True).order(Sponsor.sort_name)
		for s in q:
			if s.num_golfers + s.num_dinners == 0:
				continue
			group_num = len(groups) + 1
			new_group = {
				'id': str(s.sponsor_id),
				'group_num': group_num,
				'first_name': s.first_name,
				'last_name': s.last_name,
				'seating_prefs': s.dinner_seating
			}
			groups.append(new_group)
			for g in ndb.get_multi(s.golfer_keys[:s.num_golfers + s.num_golfers_no_dinner]):
				if g.dinner_choice == "none":
					continue
				g_id = g.key.id()
				guest_num = len(guests) + 1
				new_guest = {
					'key': g_id,
					'is_golfer': True,
					'guest_num': guest_num,
					'group_num': group_num,
					'table_num': g.table_num,
					'orig_table_num': g.table_num,
					'guest_name': g.first_name + " " + g.last_name
				}
				guests.append(new_guest)
			for g in ndb.get_multi(s.dinner_keys[:s.num_dinners]):
				g_id = g.key.id()
				guest_num = len(guests) + 1
				new_guest = {
					'key': g_id,
					'is_golfer': False,
					'guest_num': guest_num,
					'group_num': group_num,
					'table_num': g.table_num,
					'orig_table_num': g.table_num,
					'guest_name': g.first_name + " " + g.last_name
				}
				guests.append(new_guest)
		template_values = {
			'messages': [],
			'groups_json': json.dumps(groups),
			'guests_json': json.dumps(guests),
			'capabilities': caps
			}
		html = render_to_string('seating.html', template_values)
		self.response.out.write(html)

	def post(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, '/admin/view/seating')
			return
		guests_json = self.request.get('guests_json')
		guests = json.loads(guests_json)
		guests_to_update = []
		for g in guests:
			if g['table_num'] != g['orig_table_num']:
				g_id = g['key']
				if g['is_golfer']:
					guest = Golfer.get_by_id(g_id)
				else:
					guest = DinnerGuest.get_by_id(g_id)
				guest.table_num = g['table_num']
				guests_to_update.append(guest)
		if guests_to_update:
			ndb.put_multi(guests_to_update)
		self.redirect('/admin/view/seating')

class ViewTributeAds(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = TributeAd.query(ancestor = t.key)
		q = q.order(TributeAd.timestamp)
		ads = q.fetch(limit = None)
		template_values = {
			'ads': ads,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('viewtributeads.html', template_values))

def csv_encode(val):
	val = re.sub(r'"', '""', unicode(val or ''))
	return '"%s"' % val

class DownloadRegistrationsCSV(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.timestamp)
		csv = []
		csv.append(','.join(['ID', 'first_name', 'last_name', 'company',
							 'address', 'city', 'state', 'zip', 'email', 'phone',
							 'sponsorships', 'num_golfers', 'num_dinners', 'payment_due',
							 'payment_paid', 'payment_type', 'trans_code']))
		for s in q:
			sponsorships = []
			for sskey in s.sponsorships:
				ss = sskey.get()
				sponsorships.append(ss.name)
			csv.append(','.join([csv_encode(x)
								 for x in [s.sponsor_id, s.first_name, s.last_name, s.company, s.address,
										   s.city, s.state, s.zip, s.email, s.phone,
										   ','.join(sponsorships),
										   s.num_golfers + s.num_golfers_no_dinner,
										   s.num_golfers + s.num_dinners,
										   s.payment_due, s.payment_made,
										   s.payment_type, s.transaction_code]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=registrations.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

class DownloadGolfersCSV(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.timestamp)
		csv = []
		csv.append(','.join(['first_name', 'last_name', 'gender', 'company',
							 'address', 'city', 'state', 'zip',
							 'email', 'phone', 'ghin_number', 'index',
							 'avg_score', 'tournament_index', 'course_handicap', 'tees',
							 'shirt_size', 'team', 'starting_hole', 'cart',
							 'contact_first_name', 'contact_last_name']))
		for s in q:
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers == 0:
				continue
			golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
			for g in golfers:
				vg = ViewGolfer(t, s, g, None)
				g1 = vg.golfer
				cart = ''
				if g.cart:
					cart = str(g.cart)
				tees_str = ["Red", "White", "Blue"][vg.tees - 1]
				if g1.has_index:
					tournament_index = vg.handicap_index_str
				else:
					tournament_index = vg.computed_index
				csv.append(','.join([csv_encode(x)
									 for x in [g1.first_name, g1.last_name, g1.gender, g1.company,
											   g1.address, g1.city, g1.state, g1.zip,
											   g1.email, g1.phone, g1.ghin_number, vg.handicap_index_str,
											   g1.average_score, tournament_index, vg.course_handicap, tees_str,
											   g1.shirt_size, vg.team_name, vg.starting_hole, vg.cart,
											   s.first_name, s.last_name]]))
			for i in range(len(golfers) + 1, total_golfers + 1):
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

class DownloadGolfersByTeamCSV(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Golfer.query()
		q = q.filter(Golfer.tournament == t.key)
		q = q.filter(Golfer.active == True)
		q = q.order(Golfer.sort_name)
		golfer_keys = set(q.fetch(limit = None, keys_only = True))
		used_keys = set()
		teams = []
		q = Team.query(ancestor = t.key).order(Team.name)
		for team in q:
			golfers_in_team = []
			course_handicaps = []
			sequence = 0
			for g_key in team.golfers:
				sequence += 1
				g_id = g_key.id()
				if not g_key in golfer_keys:
					logging.warning("Golfer %d, referenced by team %s (%d), does not exist" % (g_key.id(), team.name, team.key.id()))
					continue
				if g_key in used_keys:
					logging.warning("Golfer %d, referenced by team %s (%d), is in another team" % (g_key.id(), team.name, team.key.id()))
				used_keys.add(g_key)
				g = g_key.get()
				vg = ViewGolfer(t, None, g, None)
				course_handicaps.append(vg.course_handicap)
				golfers_in_team.append(vg)
			team_handicap = calculate_team_handicap(course_handicaps)
			golfers_in_team.sort(key = lambda vg: vg.cart)
			newteam = {
				'golfers': golfers_in_team,
				'starting_hole': team.starting_hole,
				'team_handicap': team_handicap
			}
			teams.append(newteam)
		teams.sort(key = sort_by_starting_hole)

		csv = []
		csv.append(','.join(['first_name', 'last_name', 'gender', 'company',
							 'address', 'city', 'state', 'zip',
							 'email', 'phone', 'ghin_number', 'index',
							 'avg_score', 'tournament_index', 'course_handicap', 'tees',
							 'shirt_size', 'team', 'team_handicap', 'starting_hole', 'cart']))
		for team in teams:
			for vg in team['golfers']:
				g1 = vg.golfer
				cart = ''
				if g.cart:
					cart = str(g.cart)
				tees_str = ["Red", "White", "Blue"][vg.tees - 1]
				if g1.has_index:
					tournament_index = vg.handicap_index_str
				else:
					tournament_index = vg.computed_index
				csv.append(','.join([csv_encode(x)
									 for x in [g1.first_name, g1.last_name, g1.gender, g1.company,
											   g1.address, g1.city, g1.state, g1.zip,
											   g1.email, g1.phone, g1.ghin_number, vg.handicap_index_str,
											   g1.average_score, tournament_index, vg.course_handicap, tees_str,
											   g1.shirt_size, vg.team_name, team['team_handicap'],
											   vg.starting_hole, vg.cart]]))

		for g_key in golfer_keys - used_keys:
			g = g_key.get()
			vg = ViewGolfer(t, None, g, None)
			csv.append(','.join([csv_encode(x)
								 for x in [g1.first_name, g1.last_name, g1.gender, g1.company,
										   g1.address, g1.city, g1.state, g1.zip,
										   g1.email, g1.phone, g1.ghin_number, vg.handicap_index_str,
										   g1.average_score, tournament_index, vg.course_handicap, tees_str,
										   g1.shirt_size, vg.team_name, '',
										   vg.starting_hole, vg.cart]]))

		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=golfers.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

class DownloadDinnersCSV(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = Sponsor.query(ancestor = t.key)
		q = q.filter(Sponsor.confirmed == True)
		q = q.order(Sponsor.timestamp)
		csv = []
		csv.append(','.join(['first_name', 'last_name', 'dinner_choice', 'seating_pref', 'table_num',
							 'contact_first_name', 'contact_last_name']))
		for s in q:
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers:
				golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
				for g in golfers:
					if g.dinner_choice != 'none':
						csv.append(','.join([csv_encode(x) for x in [g.first_name, g.last_name,
																	 g.dinner_choice, s.dinner_seating, g.table_num,
																	 s.first_name, s.last_name]]))
				for i in range(len(golfers) + 1, total_golfers + 1):
					csv.append(','.join([csv_encode(x) for x in ['n/a', 'n/a', '', s.dinner_seating,
																 s.first_name, s.last_name]]))
			if s.num_dinners:
				guests = ndb.get_multi(s.dinner_keys[:s.num_dinners])
				for g in guests:
					csv.append(','.join([csv_encode(x) for x in [g.first_name, g.last_name,
																 g.dinner_choice, s.dinner_seating, g.table_num,
																 s.first_name, s.last_name]]))
				for i in range(len(guests) + 1, s.num_dinners + 1):
					csv.append(','.join([csv_encode(x) for x in ['n/a', 'n/a', '', s.dinner_seating, 0,
																 s.first_name, s.last_name]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=dinners.csv'
		self.response.out.write('\n'.join(csv))
		self.response.out.write('\n')

class DownloadTributeAdsCSV(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_view_registrations:
			show_login_page(self.response.out, self.request.uri)
			return
		q = TributeAd.query(ancestor = t.key)
		q = q.order(TributeAd.timestamp)
		ads = q.fetch(limit = None)
		ad_sizes = [ '', 'One Line', 'Business Card', '1/4 Page', '1/2 Page', 'Full Page', 'Full Page Color' ]
		csv = []
		csv.append(','.join(['ID', 'first_name', 'last_name',
							 'address', 'city', 'state', 'zip', 'email', 'phone',
							 'ad_size', 'text',
							 'payment_due', 'payment_paid', 'payment_type', 'trans_code']))
		for ad in ads:
			csv.append(','.join([csv_encode(x)
								 for x in [ad.key.id(), ad.first_name, ad.last_name, ad.address,
										   ad.city, ad.state, ad.zip, ad.email, ad.phone,
										   ad_sizes[ad.ad_size], ad.printed_names,
										   ad.payment_due, ad.payment_made,
										   ad.payment_type, ad.transaction_code]]))
		self.response.headers['Content-Type'] = 'text/csv; charset=utf-8'
		self.response.headers['Content-Disposition'] = 'attachment;filename=tributeads.csv'
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
		t = tournament.get_tournament()
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
			if today.date() <= t.early_bird_deadline:
				early_bird_deadline = "%s %d, %d" % (t.early_bird_deadline.strftime("%B"),
													 t.early_bird_deadline.day,
													 t.early_bird_deadline.year)
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
			q = Sponsor.query(ancestor = t.key)
			q = q.filter(Sponsor.sponsor_id == int(id))
			s = q.get()
			if s:
				body = body_template % (s.first_name, s.sponsor_id)
				logging.info("sending mail to %s (id %s)" % (s.email, s.sponsor_id))
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_auction:
			show_login_page(self.response.out, self.request.uri)
			return
		which_auction = self.request.get('which_auction')
		if self.request.get('key'):
			id = self.request.get('key')
			item = auctionitem.AuctionItem.get_by_id(int(id), parent = t.key)
			template_values = {
				'item': item,
				'which_auction': which_auction,
				'key': id,
				'upload_url': '/admin/upload-auction',
				'capabilities': caps
				}
			self.response.out.write(render_to_string('editauction.html', template_values))
		elif self.request.get('new'):
			auction_items = auctionitem.get_auction_items(t, which_auction)
			if auction_items:
				seq = auction_items[-1].sequence + 1
			else:
				seq = 1
			item = auctionitem.AuctionItem(sequence = seq)
			template_values = {
				'item': item,
				'which_auction': which_auction,
				'key': '',
				'upload_url': '/admin/upload-auction',
				'capabilities': caps
				}
			self.response.out.write(render_to_string('editauction.html', template_values))
		else:
			live_auction_items = auctionitem.get_auction_items(t, 'l')
			silent_auction_items = auctionitem.get_auction_items(t, 's')
			template_values = {
				'live_auction_items': live_auction_items,
				'silent_auction_items': silent_auction_items,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('adminauction.html', template_values))

class UploadAuctionItem(webapp2.RequestHandler):
	# Process the submitted info.
	def post(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_update_auction:
			show_login_page(self.response.out, '/admin/auction')
			return
		auctionitem.clear_auction_item_cache(t)
		which_auction = self.request.get('which_auction')
		id = self.request.get('key')
		if id:
			item = auctionitem.AuctionItem.get_by_id(int(id), parent = t.key)
		else:
			item = auctionitem.AuctionItem(parent = t.key, which = which_auction)
		item.sequence = int(self.request.get('sequence'))
		desc = self.request.get('description')
		desc = desc.replace('\r\n', '\n')
		item.description = desc
		uploads = self.request.POST.getall('file')
		try:
			if dev_server:
				item.image = uploads[0].file.read()
				item.image_width = 200
				item.image_height = 100
			else:
				img = images.Image(uploads[0].file.read())
				img.resize(width = 200)
				item.image = img.execute_transforms(output_encoding = images.JPEG)
				item.image_width = img.width
				item.image_height = img.height
			uploads[0].file.close()
		except:
			logging.debug("No uploaded file.")
		item.put()
		auditing.audit(t, "Added Auction Item", data = desc, request = self.request)
		self.redirect("/admin/auction")

class DeleteFile(webapp2.RequestHandler):
	def post(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_content:
			show_login_page(self.response.out, '/admin/edit')
			return
		if self.request.get('delete-photos'):
			items_to_delete = self.request.get_all('delete-photo')
		else:
			items_to_delete = self.request.get_all('delete-file')
		for path in items_to_delete:
			q = uploadedfile.UploadedFile.query(ancestor = t.key)
			q = q.filter(uploadedfile.UploadedFile.path == path)
			k = q.get(keys_only = True)
			if k:
				k.delete()
				auditing.audit(t, "Deleted Uploaded File", data = path, request = self.request)
		self.redirect("/admin/edit")

class UploadFile(webapp2.RequestHandler):
	def post(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if caps is None or not caps.can_edit_content:
			show_login_page(self.response.out, '/admin/edit')
			return
		uploads = self.request.POST.getall('file')
		try:
			filename = uploads[0].filename
			contents = uploads[0].file.read()
			uploads[0].file.close()
			logging.debug("upload file %s, size %d" % (filename, len(contents)))
			if self.request.get('upload-photo'):
				item = uploadedfile.UploadedFile(parent = t.key, name = filename,
												 path = "/photos/%s" % filename,
												 contents = contents)
				item.put()
				auditing.audit(t, "Uploaded Photo", data = filename, request = self.request)
			elif self.request.get('upload-file'):
				item = uploadedfile.UploadedFile(parent = t.key, name = filename,
												 path = "/files/%s" % filename,
												 contents = contents)
				item.put()
				auditing.audit(t, "Uploaded File", data = filename, request = self.request)
		except:
			logging.info("No uploaded file.")
		self.redirect("/admin/edit")

def show_edit_form(name, caps, response):
	page = detailpage.get_detail_page(name, True)
	logging.info("showing %s, version %d, draft %s, preview %s" %
				 (page.name, page.version, "yes" if page.draft else "no", "yes" if page.preview else "no"))
	last_modified = ""
	if page.last_modified:
		last_modified = page.last_modified.replace(tzinfo=tz.utc).astimezone(tz.pacific)
	template_values = {
		'page': page,
		'timestamp': last_modified,
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
			last_modified = ""
			if page.last_modified:
				last_modified = page.last_modified.replace(tzinfo=tz.utc).astimezone(tz.pacific)
			page_info = {
				'name': name,
				'path': path,
				'published_version': published_version,
				'draft_version': draft_version,
				'is_draft': draft_version > published_version,
				'last_modified': last_modified
				}
			pages.append(page_info)
		photos = []
		files = []
		q = uploadedfile.UploadedFile.query(ancestor = t.key)
		q = q.order(uploadedfile.UploadedFile.name)
		for item in q:
			if item.path.startswith('/photos/'):
				photos.append(item)
			elif item.path.startswith('/files/'):
				files.append(item)

		template_values = {
			'pages': pages,
			'photos': photos,
			'files': files,
			'upload_url': '/admin/upload-file',
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
			q = detailpage.DetailPage.query(ancestor = t.key)
			q = q.filter(detailpage.DetailPage.name == name)
			q = q.filter(detailpage.DetailPage.version == version)
			page = q.get()
			logging.info("saving %s: name %s, version %d, draft %s, preview %s" %
						 (page.key.id(), name, version, "yes" if is_draft else "no", "yes" if is_preview else "no"))
			page.title = title
			page.content = content
			page.preview = is_preview
			page.draft = is_draft
			page.put()
		else:
			versions = detailpage.get_draft_version(name)
			version += 1
			page = detailpage.DetailPage(parent = t.key, name = name, version = version,
										 title = title, content = content,
										 draft = is_draft, preview = is_preview)
			logging.info("saving new: name %s, version %d, draft %s, preview %s" %
						 (name, version, "yes" if is_draft else "no", "yes" if is_preview else "no"))
			page.put()
		auditing.audit(t, "Saved Page",
					   data = ("%s: version %d%s%s" %
							   (name, version, " draft" if is_draft else "", " preview" if is_preview else "")))
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		q = Sponsor.query(ancestor = t.key)
		q = q.order(Sponsor.timestamp)
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
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		if self.request.get('delete'):
			ids_to_delete = self.request.get_all('selected_items')
			for id in ids_to_delete:
				s = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == int(id)).get()
				ndb.delete_multi(s.golfer_keys)
				ndb.delete_multi(s.dinner_keys)
				auditing.audit(t, "Deleted Registration", sponsor_id = int(id), request = self.request)
				if s.confirmed:
					tournament.update_counters(t, -(s.num_golfers + s.num_golfers_no_dinner), -(s.num_golfers + s.num_dinners))
				s.key.delete()
		self.redirect('/admin/delete-registrations')

class AuditHandler(webapp2.RequestHandler):
	def get(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, '/admin/delete-registrations')
			return
		start = int(self.request.get('start') or 0)
		q = auditing.get_audit_entries()
		limit = 20
		if self.request.get('sponsor_id'):
			q = q.filter(auditing.AuditEntry.sponsor_id == int(self.request.get('sponsor_id')))
			limit = None
		elif self.request.get('tribute_id'):
			q = q.filter(auditing.AuditEntry.tribute_id == int(self.request.get('tribute_id')))
			limit = None
		q = q.order(-auditing.AuditEntry.timestamp)
		entries = q.fetch(offset = start, limit = limit)
		self.response.out.write("""<!DOCTYPE html>
<html>
<meta http-equiv="content-type" content="text/html; charset=utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<head><title>Audit</title></head>
<link rel="icon" href="/favicon.png" type="image/png" />
<link href="https://fonts.googleapis.com/css?family=Nunito+Sans:400,400i,700,700i" rel="stylesheet" />
<style type="text/css">
body { margin: 20px; font-size: 10pt; }
body, div, h1, h2, h3, p, th, td, li, dd { font-family: "Nunito Sans", sans-serif; }
table { margin: 0 auto; }
th, td { padding: 0.5em 1em; }
td.nw { white-space: nowrap; }
p { text-align: center; }
</style>
</head>
""")
		self.response.out.write('<body><table border="0" cellpadding="0" cellspacing="0">')
		self.response.out.write('<tr valign="top">')
		self.response.out.write('<th align="left">Timestamp</th>')
		self.response.out.write('<th align="left">User</th>')
		self.response.out.write('<th align="left">Tournament</th>')
		self.response.out.write('<th align="left">Description</th>')
		self.response.out.write('<th align="left">ID</th>')
		self.response.out.write('<th align="left">Data</th>')
		self.response.out.write('</tr>')
		for entry in entries:
			self.response.out.write('<tr valign="top">')
			self.response.out.write(entry.timestamp.replace(tzinfo=tz.utc).astimezone(tz.pacific).strftime('<td class="nw">%Y-%b-%d %H:%M:%S</td>'))
			if entry.ipaddr:
				loc = 'title="%s"' % (entry.ipaddr + ' / ' + entry.location)
			else:
				loc = ''
			self.response.out.write('<td %s>%s</td>' % (loc, entry.user))
			self.response.out.write('<td>%s</td>' % entry.tournament)
			self.response.out.write('<td class="nw">%s</td>' % entry.desc)
			if entry.sponsor_id:
				self.response.out.write('<td><a href="/admin/audit?sponsor_id=%d">%d</a></td>' % (entry.sponsor_id, entry.sponsor_id))
			elif entry.tribute_id:
				self.response.out.write('<td><a href="/admin/audit?tribute_id=%d">%d</a></td>' % (entry.tribute_id, entry.tribute_id))
			else:
				self.response.out.write('<td></td>')
			self.response.out.write('<td>%s</td>' % (entry.data or ''))
			self.response.out.write('</tr>')
			start += 1
		self.response.out.write('</table>')
		if limit:
			self.response.out.write('<p><a href="/admin/audit?start=%d">Older &rarr;</a></p>' % start)
		self.response.out.write('</body></html>')

class UpgradeHandler(webapp2.RequestHandler):
	def get(self):
		start = int(self.request.get('start') or 0)
		commit = int(self.request.get('commit') or 0)
		count = self.request.get('count')
		self.response.out.write('<html><head><title>Upgrade</title></head>')
		self.response.out.write('<body><form action="/admin/upgrade" method="post">')
		if count:
			self.response.out.write('<p>Upgraded %s records.</p>' % count)
		self.response.out.write('Start: <input type="text" name="start" value="%d">' % start)
		self.response.out.write('<br>Commit: <input type="text" name="commit" value="%d">' % commit)
		self.response.out.write('<br><input type="submit" name="upgrade" value="Upgrade">')
		self.response.out.write('</form></body></html>')

	def post(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, '/admin/upgrade')
			return
		t = tournament.get_tournament()
		start = int(self.request.get('start'))
		commit = int(self.request.get('commit'))
		q = Sponsor.query(ancestor = t.key).order(Sponsor.timestamp)
		sponsors = q.fetch(offset = start, limit = 20)
		for s in sponsors:
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			golfers = Golfer.query().filter(Golfer.sponsor == s.key).order(Golfer.sequence).fetch(limit = None, keys_only = True)
			golfers_to_delete = set(golfers) - set(s.golfer_keys)
			all_dinners = DinnerGuest.query().filter(DinnerGuest.sponsor == s.key).order(DinnerGuest.sequence).fetch(limit = None, keys_only = True)
			dinners_to_delete = set(all_dinners) - set(s.dinner_keys)
			logging.debug("sponsor id: %d, %d golfers, %d dinners" % (s.sponsor_id, total_golfers, s.num_dinners))
			logging.debug("golfers to delete: " + ",".join(str(k.id()) for k in golfers_to_delete))
			logging.debug("dinners to delete: " + ",".join(str(k.id()) for k in dinners_to_delete))
			if golfers_to_delete and commit:
				ndb.delete_multi(golfers_to_delete)
			if dinners_to_delete and commit:
				ndb.delete_multi(dinners_to_delete)
			seq = 1
			for k in s.golfer_keys:
				g = k.get()
				mod = False
				if seq != g.sequence:
					logging.debug("golfer %d has wrong sequence, %d should be %d" % (k.id(), g.sequence, seq))
					g.sequence = seq
					mod = True
				if seq > total_golfers and g.active:
					logging.debug("golfer %d (#%d) should not be active" % (k.id(), seq))
					g.active = False
					mod = True
				elif seq <= total_golfers and not g.active:
					logging.debug("golfer %d (#%d) should be active" % (k.id(), seq))
					g.active = True
					mod = True
				if mod and commit:
					g.put()
				seq += 1
			seq = 1
			for k in s.dinner_keys:
				g = k.get()
				mod = False
				if seq != g.sequence:
					logging.debug("dinner %d has wrong sequence, %d should be %d" % (k.id(), g.sequence, seq))
					g.sequence = seq
					mod = True
				if seq > s.num_dinners and g.active:
					logging.debug("dinner %d (#%d) should not be active" % (k.id(), seq))
					g.active = False
					mod = True
				elif seq <= s.num_dinners and not g.active:
					logging.debug("dinner %d (#%d) should be active" % (k.id(), seq))
					g.active = True
					mod = True
				if mod and commit:
					g.put()
				seq += 1
		count = len(sponsors)
		# logging.info("Updated %d sponsors %d through %d" % (count, start, start + count - 1))
		self.redirect('/admin/upgrade?start=%d&count=%d&commit=%d' % (start + count, count, commit))

class FindOrphansHandler(webapp2.RequestHandler):
	def get(self):
		if not users.is_current_user_admin():
			show_login_page(self.response.out, '/admin/find-orphans')
			return
		t = tournament.get_tournament()
		sponsor_keys = Sponsor.query(ancestor = t.key).order(Sponsor.timestamp).fetch(limit = None, keys_only = True)
		all_golfers = set(Golfer.query().filter(Golfer.tournament == t.key).fetch(limit = None, keys_only = True))
		all_dinners = set(DinnerGuest.query().filter(DinnerGuest.tournament == t.key).fetch(limit = None, keys_only = True))
		extra_golfers = []
		extra_dinners = []
		for k in sponsor_keys:
			s = k.get()
			total_golfers = s.num_golfers + s.num_golfers_no_dinner
			if total_golfers < len(s.golfer_keys):
				extra_golfers += s.golfer_keys[total_golfers:]
				logging.debug("Sponsor %d contains extra golfers" % s.sponsor_id)
			if s.num_dinners < len(s.dinner_keys):
				extra_dinners += s.dinner_keys[s.num_dinners:]
				logging.debug("Sponsor %d contains extra dinners" % s.sponsor_id)
			s_golfers = set(s.golfer_keys)
			if s_golfers - all_golfers:
				logging.debug("Sponsor %d contains dangling golfer keys" % s.sponsor_id)
			all_golfers = all_golfers - s_golfers
			s_dinners = set(s.dinner_keys)
			if s_dinners - all_dinners:
				logging.debug("Sponsor %d contains dangling dinner keys" % s.sponsor_id)
			all_dinners = all_dinners - s_dinners
		logging.debug("Found %d orphaned golfers" % len(all_golfers))
		logging.debug("Found %d orphaned dinners" % len(all_dinners))
		self.response.out.write('<html><head><title>Orphans</title></head>')
		self.response.out.write('<body>')
		self.response.out.write('<h1>Orphaned Golfers</h1>')
		self.response.out.write('<table>')
		for k in all_golfers:
			g = k.get()
			self.response.out.write('<tr><td>%d</td><td>%s %s</td></tr>' % (k.id(), g.first_name, g.last_name))
		self.response.out.write('</table>')
		self.response.out.write('<h1>Extra Golfers</h1>')
		self.response.out.write('<table>')
		for k in extra_golfers:
			g = k.get()
			self.response.out.write('<tr><td>%d</td><td>%s %s</td><td>%d</td></tr>' % (k.id(), g.first_name, g.last_name, g.sponsor.id()))
		self.response.out.write('</table>')
		self.response.out.write('<h1>Orphaned Dinners</h1>')
		self.response.out.write('<table>')
		for k in all_dinners:
			g = k.get()
			self.response.out.write('<tr><td>%d</td><td>%s %s</td></tr>' % (k.id(), g.first_name, g.last_name))
		self.response.out.write('</table>')
		self.response.out.write('<h1>Extra Dinners</h1>')
		self.response.out.write('<table>')
		for k in extra_dinners:
			g = k.get()
			self.response.out.write('<tr><td>%d</td><td>%s %s</td><td>%d</td></tr>' % (k.id(), g.first_name, g.last_name, g.sponsor.id()))
		self.response.out.write('</table>')
		self.response.out.write('</body></html>')

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
							   ('/admin/view/seating', AssignSeating),
							   ('/admin/view/tribute', ViewTributeAds),
							   ('/admin/csv/registrations', DownloadRegistrationsCSV),
							   ('/admin/csv/golfers', DownloadGolfersCSV),
							   ('/admin/csv/golfersbyteam', DownloadGolfersByTeamCSV),
							   ('/admin/csv/dinners', DownloadDinnersCSV),
							   ('/admin/csv/tributeads', DownloadTributeAdsCSV),
							   ('/admin/mail/(.*)', SendEmail),
							   ('/admin/edit', EditPageHandler),
							   ('/admin/delete-registrations', DeleteHandler),
							   ('/admin/audit', AuditHandler),
							   ('/admin/logout', Logout),
							   ('/admin/upgrade', UpgradeHandler),
							   ('/admin/find-orphans', FindOrphansHandler)],
							  debug=dev_server)
