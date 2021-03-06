#!/usr/bin/env python

import datetime
import time
import hmac
import os
import cgi
import logging
import random
import urllib
import re
import webapp2
from google.appengine.ext import ndb
from google.appengine.api import memcache, mail
from django.template.loaders.filesystem import Loader
from django.template.loader import render_to_string

import tournament
import payments
import capabilities
import detailpage
import sponsorship
from sponsor import Sponsor, Golfer, DinnerGuest, TributeAd
import auditing

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

# Show the initial registration form.

def show_registration_form(response, t, s, messages, caps,
						   golf_wait = False,
						   dinner_wait = False,
						   in_progress = None,
						   debug = False):
	# Get today's date in PST. (We won't worry about DST, so early bird pricing will
	# last until 1 am PDT.)
	today = datetime.datetime.now() - datetime.timedelta(hours=8)
	early_bird = today.date() <= t.early_bird_deadline
	dinner_early_bird = today.date() <= t.dinner_early_bird_deadline
	registration_closed = today.date() > t.deadline
	early_bird_deadline = "%s %d, %d" % (t.early_bird_deadline.strftime("%B"),
										 t.early_bird_deadline.day,
										 t.early_bird_deadline.year)
	dinner_early_bird_deadline = "%s %d, %d" % (t.dinner_early_bird_deadline.strftime("%B"),
												t.dinner_early_bird_deadline.day,
												t.dinner_early_bird_deadline.year)
	deadline = "%s %d, %d" % (t.deadline.strftime("%B"),
							  t.deadline.day,
							  t.deadline.year)
	doubleeagle = sponsorship.get_sponsorships("Double Eagle")
	holeinone = sponsorship.get_sponsorships("Hole in One")
	eagle = sponsorship.get_sponsorships("Eagle")
	birdie = sponsorship.get_sponsorships("Birdie")
	angel = sponsorship.get_sponsorships("Angel")
	selected_sponsorships = []
	non_angel_selected = False
	use_go_discount_code = 1 if t.go_discount_codes else 0
	for sskey in s.sponsorships:
		ss = sskey.get()
		if ss:
			selected_sponsorships.append(ss.sequence)
			if ss.sequence != angel[0].sequence:
				non_angel_selected = True
	page = detailpage.get_detail_page('register', False)
	counters = tournament.get_counters(t)
	golf_sold_out = False
	dinner_sold_out = False
	if not registration_closed and not s.confirmed:
		if t.golf_sold_out or (counters.golfer_count >= t.limit_golfers) or golf_wait:
			golf_sold_out = True
		if t.dinner_sold_out or (counters.dinner_count >= t.limit_dinners) or dinner_wait:
			dinner_sold_out = True
	template_values = {
		'tournament': t,
		'golf_sold_out': golf_sold_out,
		'dinner_sold_out': dinner_sold_out,
		'sponsor': s,
		'credits': s.payment_made + s.discount,
		'net_payment_due': max(0, s.payment_due - s.payment_made - s.discount),
		'early_bird': early_bird,
		'dinner_early_bird': dinner_early_bird,
		'registration_closed': registration_closed,
		'early_bird_deadline': early_bird_deadline,
		'dinner_early_bird_deadline': dinner_early_bird_deadline,
		'deadline': deadline,
		'doubleeagle': doubleeagle,
		'holeinone': holeinone,
		'eagle': eagle,
		'birdie': birdie,
		'angel': angel[0],
		'non_angel_selected': non_angel_selected,
		'use_go_discount_code': use_go_discount_code,
		'selected': selected_sponsorships,
		'page': page,
		'messages': messages,
		'in_progress': in_progress,
		'capabilities': caps,
		'debug': debug
	}
	response.out.write(render_to_string('register.html', template_values))

# Show the continuation form.

def show_continuation_form(response, t, s, messages, caps, debug = False):
	# Get today's date in PST. (We won't worry about DST, so early bird pricing will
	# last until 1 am PDT.)
	today = datetime.datetime.now() - datetime.timedelta(hours=8)
	registration_closed = today.date() > t.deadline
	deadline = "%s %d, %d" % (t.deadline.strftime("%B"),
							  t.deadline.day,
							  t.deadline.year)
	dinner_choices = t.dinner_choices.split(',')
	has_registered = s.confirmed
	has_completed_names = True
	has_completed_handicaps = True
	has_selected_sizes = True
	has_paid = (s.payment_made + s.discount >= s.payment_due)
	total_golfers = s.num_golfers
	if s.num_golfers_no_dinner:
		total_golfers += s.num_golfers_no_dinner
	if total_golfers:
		golfers = ndb.get_multi(s.golfer_keys[:total_golfers])
		for i in range(1, total_golfers + 1):
			if i <= len(golfers):
				golfer = golfers[i - 1]
				if not golfer.first_name or not golfer.last_name or not golfer.gender:
					has_completed_names = False
				if golfer.ghin_number == '' and golfer.average_score == '' and not golfer.has_index:
					has_completed_handicaps = False
				if not golfer.shirt_size:
					has_selected_sizes = False
			else:
				has_completed_names = False
				has_completed_handicaps = False
				has_selected_sizes = False
				golfer = Golfer(tournament = t.key, sponsor = s.key, sequence = i)
				if i == 1:
					golfer.first_name = s.first_name
					golfer.last_name = s.last_name
					golfer.company = s.company
					golfer.address = s.address
					golfer.city = s.city
					golfer.state = s.state
					golfer.zip = s.zip
					golfer.phone = s.phone
					golfer.email = s.email
				golfers.append(golfer)
	else:
		golfers = []
	if s.num_dinners:
		dinner_guests = ndb.get_multi(s.dinner_keys[:s.num_dinners])
		for i in range(1, s.num_dinners + 1):
			if i <= len(dinner_guests):
				guest = dinner_guests[i - 1]
				if not guest.first_name or not guest.last_name:
					has_completed_names = False
			else:
				has_completed_names = False
				guest = DinnerGuest(tournament = t.key, sponsor = s.key, sequence = i)
				if s.num_golfers + i == 1:
					guest.first_name = s.first_name
					guest.last_name = s.last_name
				dinner_guests.append(guest)
	else:
		dinner_guests = []
	template_values = {
		'deadline': deadline,
		'registration_closed': registration_closed,
		'dinner_choices': dinner_choices,
		'sponsor': s,
		'net_payment_due': max(0, s.payment_due - s.payment_made - s.discount),
		'golfers': golfers,
		'total_golfers': total_golfers,
		'golfer_dinners': s.num_golfers > 0,
		'dinner_guests': dinner_guests,
		'has_registered': has_registered,
		'has_completed_names': has_completed_names,
		'has_completed_handicaps': has_completed_handicaps,
		'has_selected_sizes': has_selected_sizes,
		'has_paid': has_paid,
		'messages': messages,
		'capabilities': caps,
		'debug': debug
	}
	response.out.write(render_to_string('continue.html', template_values))

# Registration Step 1.

class Register(webapp2.RequestHandler):
	# Show a form for a new sponsor or the continuation form,
	# depending on whether or not the "id" parameter was provided.
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		messages = []
		sponsor_id = self.request.get('id')
		if sponsor_id:
			try:
				id = int(sponsor_id)
			except ValueError:
				pass
			else:
				q = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == id)
				s = q.get()
				if s:
					if self.request.get('page') == '1':
						show_registration_form(self.response, t, s, messages, caps, debug = dev_server)
					else:
						show_continuation_form(self.response, t, s, messages, caps, debug = dev_server)
					return
			messages.append('Sorry, we could not find a registration for ID %s' % sponsor_id)
		s = Sponsor(sponsorships = [])
		in_progress = None
		existing_id = self.request.cookies.get('sponsorid')
		if existing_id:
			try:
				id = int(existing_id)
			except ValueError:
				self.request.cookies.delete('sponsorid')
			else:
				q = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == id)
				in_progress = q.get()
		show_registration_form(self.response, t, s, messages, caps, in_progress = in_progress, debug = dev_server)

	# Process the submitted info.
	def post(self):
		messages = []
		t = tournament.get_tournament()
		counters = tournament.get_counters(t)
		# Get today's date in PST. (We won't worry about DST, so early bird pricing will
		# last until 1 am PDT.)
		today = datetime.datetime.now() - datetime.timedelta(hours=8)
		early_bird = today.date() <= t.early_bird_deadline
		dinner_early_bird = today.date() <= t.dinner_early_bird_deadline
		registration_closed = today.date() > t.deadline
		golf_price = t.golf_price_early if early_bird else t.golf_price_late
		golf_only_price = t.golf_only_price_early if early_bird else t.golf_only_price_late
		dinner_price = t.dinner_price_early if dinner_early_bird else t.dinner_price_late
		caps = capabilities.get_current_user_caps()
		orig_num_golfers = 0
		orig_num_golfers_no_dinner = 0
		orig_num_dinners = 0
		id = int(self.request.get('id'))
		if id:
			q = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == id)
			s = q.get()
			if s.num_golfers_no_dinner is None:
				s.num_golfers_no_dinner = 0
			if s.confirmed:
				orig_num_golfers = s.num_golfers
				orig_num_golfers_no_dinner = s.num_golfers_no_dinner
				orig_num_dinners = s.num_dinners
		else:
			s = Sponsor(parent = t.key)
			s.golfer_keys = []
			s.dinner_keys = []
		s.first_name = self.request.get('first_name')
		s.last_name = self.request.get('last_name')
		s.sort_name = s.last_name.lower() + ',' + s.first_name.lower()
		s.company = self.request.get('company')
		s.address = self.request.get('address')
		s.city = self.request.get('city')
		s.state = self.request.get('state')
		s.zip = self.request.get('zip')
		s.phone = self.request.get('phone')
		s.fax = self.request.get('fax')
		s.email = self.request.get('email')
		s.anonymous = False if self.request.get('agree') == 'y' else True
		s.ok_to_share_email = True if self.request.get('share_email') == 'y' else False
		s.printed_names = self.request.get('printed_names')
		s.sponsorships = []
		s.num_golfers = int(self.request.get('num_golfers'))
		if self.request.get('num_golfers_no_dinner'):
			s.num_golfers_no_dinner = int(self.request.get('num_golfers_no_dinner'))
		s.num_dinners = int(self.request.get('num_dinners'))
		s.payment_due = 0

		# If the number of golfers or dinners have changed,
		# mark new ones active and old ones inactive.
		total_golfers = s.num_golfers + s.num_golfers_no_dinner
		for k in s.golfer_keys:
			g = k.get()
			if g.active and g.sequence > total_golfers:
				g.active = False
				g.put()
			elif not g.active and g.sequence <= total_golfers:
				g.active = True
				g.put()
		for k in s.dinner_keys:
			g = k.get()
			if g.active and g.sequence > s.num_dinners:
				g.active = False
				g.put()
			elif not g.active and g.sequence <= s.num_dinners:
				g.active = True
				g.put()

		if registration_closed and (s.num_golfers > orig_num_golfers or s.num_golfers_no_dinner > orig_num_golfers_no_dinner or s.num_dinners > orig_num_dinners) and not caps.can_add_registrations:
			messages.append('Sorry, registration is closed.')
			show_registration_form(self.response, t, s, messages, caps, debug = dev_server)
			return

		discount_applied = False
		if self.request.get('show_go_campaign'):
			if t.go_discount_codes:
				discount_code = self.request.get('discount_code')
				if discount_code and s.discount == 0:
					codes = [ pair.split(':') for pair in t.go_discount_codes.split(',') ]
					codes = dict(codes)
					if discount_code in codes:
						s.go_discount_code = discount_code
						s.go_golfers = int(codes[discount_code])
						if s.go_golfers != int(self.request.get('go_golfers')):
							discount_applied = True
							messages.append('Your GO campaign discount has been applied.')
					else:
						messages.append('The discount code you entered is not valid.')
			else:
				s.go_discount_code = 'go'
				s.go_golfers = 2
		else:
			s.go_discount_code = ''
			s.go_golfers = 0

		if s.go_golfers > 12:
			go_discount = s.go_golfers
			go_golfers = 0
		else:
			go_discount = 0
			go_golfers = s.go_golfers

		if not s.first_name and not s.last_name:
			messages.append('Please enter your name.')
		elif not s.first_name or not s.last_name:
			messages.append('Please enter both first and last name.')

		if not caps.can_add_registrations:
			if s.address == '':
				messages.append('Please enter your mailing address.')
			if s.city == '' or s.state == '' or s.zip == '':
				messages.append('Please enter your city, state, and ZIP code.')
			if s.email == '':
				messages.append('Please enter your email address.')
			if s.phone == '':
				messages.append('Please enter your phone number.')

		form_payment_due = int(self.request.get('payment_due'))
		try:
			s.additional_donation = int(self.request.get('other'))
		except ValueError:
			s.additional_donation = 0
			messages.append('You entered an invalid value in the "Other Donation" field.')

		selected = self.request.get_all('sponsorships')
		sponsorships = sponsorship.get_sponsorships("all")
		sponsorship_names = []
		golfers_included = 0
		dinners_included = 0
		for ss in sponsorships:
			k = '%s:%d:%d:%d' % (ss.level, ss.sequence, ss.price, ss.golfers_included)
			if k in selected:
				s.sponsorships.append(ss.key)
				sponsorship_names.append(ss.name)
				if ss.price != go_discount:
					s.payment_due += ss.price
				golfers_included += ss.golfers_included
		dinners_included = golfers_included
		golfers_included += go_golfers
		if s.num_golfers > golfers_included:
			s.payment_due += golf_price * (s.num_golfers - golfers_included)
		golfers_included = max(0, golfers_included - s.num_golfers)
		if s.num_golfers_no_dinner > golfers_included:
			s.payment_due += golf_only_price * (s.num_golfers_no_dinner - golfers_included)
		golfers_included = max(0, golfers_included - s.num_golfers_no_dinner)
		dinners_included += golfers_included
		if s.num_dinners > dinners_included:
			s.payment_due += dinner_price * (s.num_dinners - dinners_included)
		s.payment_due += s.additional_donation
		if total_golfers <= 0 and s.num_dinners <= 0 and s.payment_due <= 0 and not caps.can_add_registrations:
			messages.append('You have not chosen any sponsorships, golfers, or dinners.')
		if s.payment_due != form_payment_due and not discount_applied:
			messages.append('There was an error processing the form: payment due does not match selected sponsorships and number of golfers and dinners.')
			logging.info('Payment Due from form was %d, calculated %d instead' % (form_payment_due, s.payment_due))

		if caps.can_add_registrations:
			s.confirmed = True
			payment_made = self.request.get('payment_made')
			if payment_made == '':
				s.payment_made = 0
				s.payment_type = ''
				s.transaction_code = ''
				s.auth_code = ''
			else:
				try:
					s.payment_made = int(payment_made)
				except ValueError:
					s.payment_made = 0
					messages.append('You entered an invalid value in the "Payment Made" field.')
				s.payment_type = self.request.get('paytype')
				s.transaction_code = self.request.get('transcode')
				s.auth_code = self.request.get('authcode')
			discount = self.request.get('discount')
			if discount == '':
				s.discount = 0
				s.discount_type = ''
			else:
				try:
					s.discount = int(discount)
				except ValueError:
					s.discount = 0
					messages.append('You entered an invalid value in the "Discount" field.')
				s.discount_type = self.request.get('discount_type')

		golf_wait = False
		dinner_wait = False
		if not caps.can_add_registrations:
			if total_golfers > orig_num_golfers + orig_num_golfers_no_dinner:
				if t.golf_sold_out or (counters.golfer_count + total_golfers - orig_num_golfers - orig_num_golfers_no_dinner > t.limit_golfers):
					s.num_golfers = orig_num_golfers
					s.num_golfers_no_dinner = orig_num_golfers_no_dinner
					golf_wait = True
			if s.num_golfers + s.num_dinners > orig_num_golfers + orig_num_dinners:
				if t.dinner_sold_out or (counters.dinner_count + s.num_golfers + s.num_dinners - orig_num_golfers - orig_num_dinners > t.limit_dinners):
					s.num_golfers = orig_num_golfers
					s.num_dinners = orig_num_dinners
					dinner_wait = True

		if messages or golf_wait or dinner_wait or self.request.get('apply_discount'):
			show_registration_form(self.response, t, s, messages, caps, debug = dev_server, golf_wait = golf_wait, dinner_wait = dinner_wait)
			return

		if s.sponsor_id == 0:
			while True:
				trial_id = random.randrange(100000,999999)
				q = Sponsor.query(ancestor = t.key)
				q = q.filter(Sponsor.sponsor_id == trial_id)
				result = q.get(keys_only = True)
				if result is None:
					s.sponsor_id = trial_id
					break
				logging.info('ID collision for %d; retrying...' % trial_id)
		logging.info('Registration Step 1 for ID %d (%d golfers + %d dinners)' % (s.sponsor_id, total_golfers, s.num_golfers + s.num_dinners))
		s.put()
		if s.confirmed:
			tournament.update_counters(t, total_golfers - orig_num_golfers - orig_num_golfers_no_dinner,
										  s.num_golfers + s.num_dinners - orig_num_golfers - orig_num_dinners)
		auditing.audit(t, "Registration Step 1",
					   sponsor_id = s.sponsor_id,
					   data = "%s %s (%d golfers + %d dinners)" % (s.first_name, s.last_name, total_golfers, s.num_golfers + s.num_dinners),
					   request = self.request)
		memcache.delete('%s/admin/view/golfers' % t.name)
		memcache.delete('%s/admin/view/dinners' % t.name)
		if caps.can_add_registrations and self.request.get('save'):
			self.redirect('/admin/view/registrations')
			return
		if not caps.can_add_registrations:
			self.response.set_cookie('sponsorid', str(s.sponsor_id), expires=datetime.datetime.combine(t.golf_date, datetime.time(23,59)))
		self.redirect('/register?id=%d' % s.sponsor_id)

# Registration Step 2.

class Continue(webapp2.RequestHandler):
	# Process the submitted info.
	def post(self):
		messages = []
		t = tournament.get_tournament()
		counters = tournament.get_counters(t)
		caps = capabilities.get_current_user_caps()
		id = self.request.get('id')
		q = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == int(id))
		s = q.get()
		if s is None:
			messages.append('Sorry, we could not find a registration for ID %s' % id)
			s = Sponsor(sponsorships = [])
			show_registration_form(self.response, t, s, messages, caps, debug = dev_server)
			return

		if s.num_golfers_no_dinner is None:
			s.num_golfers_no_dinner = 0
		orig_num_golfers = 0
		orig_num_golfers_no_dinner = 0
		orig_num_dinners = 0
		if s.confirmed:
			orig_num_golfers = s.num_golfers
			orig_num_golfers_no_dinner = s.num_golfers_no_dinner
			orig_num_dinners = s.num_dinners

		golfers = ndb.get_multi(s.golfer_keys)
		golfers_to_delete = []
		total_golfers = s.num_golfers + s.num_golfers_no_dinner
		if len(golfers) < total_golfers:
			# Initialize new golfer instances.
			for i in range(len(golfers), total_golfers):
				golfers.append(Golfer(tournament = t.key, sponsor = s.key, sequence = i + 1, active = True))
		elif len(golfers) > total_golfers:
			# Mark excess golfer instances as not active, so we can filter
			# them out when querying all golfers. Delete any that have no
			# information worth saving.
			extras_have_names = False
			for i in range(total_golfers, len(golfers)):
				golfers[i].active = False
				if golfers[i].first_name or golfers[i].last_name:
					extras_have_names = True
			if not extras_have_names:
				golfers_to_delete += [g.key for g in golfers[total_golfers:]]
				golfers = golfers[:total_golfers]
		golfer_dinners = 0
		for golfer in golfers:
			if not golfer.active:
				break
			i = golfer.sequence
			golfer.first_name = self.request.get('first_name%d' % i)
			golfer.last_name = self.request.get('last_name%d' % i)
			if golfer.last_name:
				golfer.sort_name = golfer.last_name.lower() + ',' + golfer.first_name.lower()
			else:
				golfer.sort_name = s.last_name.lower() + '@' + ("%02d" % i)
			golfer.gender = self.request.get('gender%d' % i)
			golfer.company = self.request.get('company%d' % i)
			golfer.address = self.request.get('address%d' % i)
			golfer.city = self.request.get('city%d' % i)
			golfer.state = self.request.get('state%d' % i)
			golfer.zip = self.request.get('zip%d' % i)
			golfer.phone = self.request.get('phone%d' % i)
			golfer.email = self.request.get('email%d' % i)
			golfer.index_info_modified = False
			handicap_index = self.request.get('index%d' % i)
			if handicap_index:
				try:
					val = float(handicap_index)
					if not golfer.has_index or val != golfer.handicap_index:
						golfer.handicap_index = val
						golfer.has_index = True
						golfer.index_info_modified = True
				except ValueError:
					messages.append('Invalid handicap index for golfer #%d; please enter a decimal number.' % i)
					logging.error("Invalid handicap index '%s'" % handicap_index)
					if golfer.has_index:
						golfer.index_info_modified = True
					golfer.handicap_index = 0.0
					golfer.has_index = False
			else:
				if golfer.has_index:
					golfer.index_info_modified = True
				golfer.handicap_index = 0.0
				golfer.has_index = False
			average_score = self.request.get('avg%d' % i)
			if average_score != golfer.average_score:
				golfer.index_info_modified = True
			golfer.average_score = average_score
			ghin_number = self.request.get('ghin%d' % i)
			if ghin_number != golfer.ghin_number:
				golfer.index_info_modified = True
			golfer.ghin_number = ghin_number
			golfer.shirt_size = self.request.get('shirtsize%d' % i)
			golfer.dinner_choice = self.request.get('golfer_dinner%d' % i)
			if golfer.dinner_choice != "none":
				golfer_dinners += 1
		ndb.put_multi(golfers)
		s.golfer_keys = [ g.key for g in golfers ]

		if golfer_dinners > s.num_golfers:
			messages.append('Please select "No Dinner" for golfers who will not be attending dinner.')

		dinner_guests = ndb.get_multi(s.dinner_keys)
		dinners_to_delete = []
		if len(dinner_guests) < s.num_dinners:
			# Initialize new DinnerGuest instances.
			for i in range(len(dinner_guests), s.num_dinners):
				dinner_guests.append(DinnerGuest(tournament = t.key, sponsor = s.key, sequence = i + 1, active = True))
		elif len(dinner_guests) > s.num_dinners:
			# Mark excess DinnerGuest instances as not active, so we can filter
			# them out when querying all dinner guests. Delete any that have
			# no information worth saving.
			extras_have_names = False
			for i in range(s.num_dinners, len(dinner_guests)):
				dinner_guests[i].active = False
				if dinner_guests[i].first_name or dinner_guests[i].last_name:
					extras_have_names = True
			if not extras_have_names:
				dinners_to_delete += [g.key for g in dinner_guests[s.num_dinners:]]
				dinner_guests = dinner_guests[:s.num_dinners]
		for guest in dinner_guests:
			if not guest.active:
				break
			i = guest.sequence
			guest.first_name = self.request.get('guest_first_name%d' % i)
			guest.last_name = self.request.get('guest_last_name%d' % i)
			guest.dinner_choice = self.request.get('guest_dinner%d' % i)
		ndb.put_multi(dinner_guests)
		s.dinner_keys = [ g.key for g in dinner_guests ]

		s.pairing = self.request.get('pairing')
		s.dinner_seating = self.request.get('dinner_seating')

		if (not caps.can_add_registrations) and (not self.request.get('back')):
			if total_golfers > orig_num_golfers + orig_num_golfers_no_dinner:
				if counters.golfer_count + total_golfers - orig_num_golfers - orig_num_golfers_no_dinner > t.limit_golfers:
					open_slots = t.limit_golfers - counters.golfer_count
					if open_slots <= 0:
						messages.append('Sorry, the golf tournament is sold out.')
					elif open_slots == 1:
						messages.append('Sorry, the tournament only has room for 1 more golfer.')
					else:
						messages.append('Sorry, the tournament only has room for %d more golfers.' % open_slots)
			if s.num_golfers + s.num_dinners > orig_num_golfers + orig_num_dinners:
				if counters.dinner_count + s.num_golfers + s.num_dinners - orig_num_golfers - orig_num_dinners > t.limit_dinners:
					open_slots = t.limit_dinners - counters.dinner_count
					if open_slots <= 0:
						messages.append('Sorry, the dinner is sold out.')
					elif open_slots == 1:
						messages.append('Sorry, there is only room for 1 more dinner reservation.')
					else:
						messages.append('Sorry, there is only room for %d more dinner reservations.' % open_slots)

		if messages:
			s.put()
			show_continuation_form(self.response, t, s, messages, caps, debug = dev_server)
			return

		if not self.request.get('back'):
			s.confirmed = True

		logging.info('Registration Step 2 for ID %d' % s.sponsor_id)
		s.put()
		if golfers_to_delete:
			ndb.delete_multi(golfers_to_delete)
		if dinners_to_delete:
			ndb.delete_multi(dinners_to_delete)

		if not caps.can_add_registrations:
			self.response.set_cookie('sponsorid', str(s.sponsor_id), expires=datetime.datetime.combine(t.golf_date, datetime.time(23,59)))

		if s.confirmed:
			tournament.update_counters(t, total_golfers - orig_num_golfers - orig_num_golfers_no_dinner,
										  s.num_golfers + s.num_dinners - orig_num_golfers - orig_num_dinners)
		auditing.audit(t, "Registration Step 2",
					   sponsor_id = s.sponsor_id,
					   data = s.first_name + " " + s.last_name,
					   request = self.request)
		memcache.delete('%s/admin/view/golfers' % t.name)
		memcache.delete('%s/admin/view/dinners' % t.name)

		# Mark unique sponsorships as sold.
		ss_changed = []
		for sskey in s.sponsorships:
			ss = sskey.get()
			if ss and ss.unique:
				ss.sold = True;
				ss_changed.append(ss)
		if ss_changed:
			ndb.put_multi(ss_changed)
			sponsorship.clear_sponsorships_cache()

		if caps.can_add_registrations and self.request.get('save'):
			self.redirect('/admin/view/registrations')
			return

		if self.request.get('back'):
			self.redirect('/register?id=%s&page=1' % id)
			return

		net_payment_due = max(0, s.payment_due - s.payment_made - s.discount)
		if net_payment_due == 0 and self.request.get('save'):
			template_values = {
				'sponsor': s,
				'capabilities': caps
			}
			self.response.out.write(render_to_string('ack.html', template_values))
			return

		if self.request.get('pay_by_check'):
			if s.email and net_payment_due > 0:
				email_check_ack(s, net_payment_due)
			template_values = {
				'sponsor': s,
				'net_payment_due': net_payment_due,
				'capabilities': caps
			}
			logging.info('Pay by check, ID %d' % s.sponsor_id)
			self.response.out.write(render_to_string('paybycheck.html', template_values))
			return

		sponsorship_names = []
		for sskey in s.sponsorships:
			ss = sskey.get()
			if ss:
				sponsorship_names.append(ss.name)

		payments_info = payments.get_payments_info(t)

		if payments_info.gateway_url and 'acceptiva' in payments_info.gateway_url:
			parms = [('cst', '60605a'),
					 ('contactname', s.first_name + " " + s.last_name),
					 ('contactemailaddress', s.email),
					 ('sponsorshiplevel', ','.join(sponsorship_names)),
					 ('numberofgolfers', total_golfers),
					 ('numberofdinnerguests', s.num_golfers + s.num_dinners),
					 ('amount_20_20_amt', net_payment_due),
					 ('idnumberhidden', s.sponsor_id),
					 ('fname', s.first_name),
					 ('lname', s.last_name),
					 ('address', s.address),
					 ('city', s.city),
					 ('state', s.state),
					 ('zip', s.zip),
					 ('phone', s.phone),
					 ('email', s.email)]
			logging.info('Pay by acceptiva, ID %d' % s.sponsor_id)
			self.redirect('%s?%s' % (payments_info.gateway_url, urllib.urlencode(parms)))

		elif payments_info.gateway_url and 'authorize.net' in payments_info.gateway_url:
			timestamp = int(time.time())
			fingerprint = hmac.new(payments_info.transaction_key.encode())
			fingerprint.update(payments_info.api_login_id)
			fingerprint.update('^')
			fingerprint.update(str(s.sponsor_id))
			fingerprint.update('^')
			fingerprint.update(str(timestamp))
			fingerprint.update('^')
			fingerprint.update(str(net_payment_due))
			fingerprint.update('^')
			description = "Celebration Classic Registration"
			api_fields = [
				('x_test_request', 'TRUE' if payments_info.test_mode else 'FALSE'),
				('x_login', payments_info.api_login_id),
				('x_fp_sequence', str(s.sponsor_id)),
				('x_fp_timestamp', str(timestamp)),
				('x_fp_hash', fingerprint.hexdigest()),
				('x_version', '3.1'),
				('x_method', 'CC'),
				('x_type', 'AUTH_CAPTURE'),
				('x_cust_id', s.sponsor_id),
				('x_description', description),
				('x_email_customer', 'FALSE'),
				('x_delim_data', 'FALSE'),
				('x_relay_response', 'TRUE'),
				('x_relay_url', payments_info.relay_url),
				]
			template_values = {
				'sponsor': s,
				'gateway_url': payments_info.gateway_url,
				'api_fields': api_fields,
				'net_payment_due': str(net_payment_due),
				'capabilities': caps
			}
			logging.info('Pay by authorize.net, ID %d' % s.sponsor_id)
			self.response.out.write(render_to_string('paybycredit.html', template_values))

		else:
			messages.append('Sorry, we are not yet accepting credit card payments.')
			show_continuation_form(self.response, t, s, messages, caps, debug = dev_server)

# Send an email receipt.

check_ack_template = """
Dear %s,

Thank you for registering for the Celebration Classic Dinner
and Golf Tournament!

Please mail your check for $%s to:

  Celebration Classic
  20 Cherry Blossom Rd.
  Los Gatos, CA 95032

Please make sure that you have provided all of the following
information for each golfer and dinner guest:

- Name
- GHIN number or average score (for golfers)
- Shirt size (for golfers)
- Dinner selection

To provide any missing information or make changes, please visit
the following URL:

  http://www.celebrationclassic.org/register?id=%s

If you have any questions, just reply to this email and we'll be
glad to assist.
"""

def email_check_ack(s, amount):
	subject = "Your Celebration Classic Registration"
	sender = "registration@celebrationclassic.org"
	body = check_ack_template % (s.first_name, amount, s.sponsor_id)
	logging.info("sending email acknowledgment to %s (id %s)" % (s.email, s.sponsor_id))
	try:
		mail.send_mail(sender=sender, to=s.email, subject=subject, body=body)
	except:
		logging.exception("Could not send email to %s" % s.email)

cc_receipt_template = """
Dear %s,

Thank you for registering for the Celebration Classic Dinner
and Golf Tournament!

We have recorded your payment as follows:

Card type: %s
Amount: $%s
Authorization code: %s

Please make sure that you have provided all of the following
information for each golfer and dinner guest:

- Name
- GHIN number or average score (for golfers)
- Shirt size (for golfers)
- Dinner selection

To provide any missing information or make changes, please visit
the following URL:

  http://www.celebrationclassic.org/register?id=%s

If you have any questions, just reply to this email and we'll be
glad to assist.
"""

def email_cc_receipt(s, card_type, auth_code, amount):
	subject = "Your Celebration Classic Registration"
	sender = "registration@celebrationclassic.org"
	body = cc_receipt_template % (s.first_name, card_type, amount, auth_code, s.sponsor_id)
	logging.info("sending email receipt to %s (id %s)" % (s.email, s.sponsor_id))
	try:
		mail.send_mail(sender=sender, to=s.email, subject=subject, body=body)
	except:
		logging.exception("Could not send email to %s" % s.email)

cc_tribute_receipt_template = """
Dear %s,

Thank you for your tribute ad for the Celebration Classic Dinner
and Golf Tournament!

We have recorded your payment as follows:

Card type: %s
Amount: $%s
Authorization code: %s

If you have any questions, just reply to this email and we'll be
glad to assist.
"""

def email_cc_tribute_receipt(ad, tribute_id, card_type, auth_code, amount):
	subject = "Your Celebration Classic Tribute Ad"
	sender = "registration@celebrationclassic.org"
	body = cc_tribute_receipt_template % (ad.first_name, card_type, amount, auth_code)
	logging.info("sending email receipt to %s (tribute id %s)" % (ad.email, tribute_id))
	try:
		mail.send_mail(sender=sender, to=ad.email, subject=subject, body=body)
	except:
		logging.exception("Could not send email to %s" % ad.email)

# Process the relay response from Authorize.net confirming payment.

class RelayResponse(webapp2.RequestHandler):
	# Process the submitted info.
	def post(self):
		t = tournament.get_tournament()
		payments_info = payments.get_payments_info(t)
		response_code = self.request.get('x_response_code')
		reason_code = self.request.get('x_response_reason_code')
		reason_text = self.request.get('x_response_reason_text')
		card_type = self.request.get('x_card_type')
		auth_code = self.request.get('x_auth_code')
		trans_id = self.request.get('x_trans_id')
		id = self.request.get('x_cust_id')
		amount = self.request.get('x_amount')
		method = self.request.get('x_method')
		logging.info("relay response for id %s: %s, reason %s (\"%s\"), auth_code %s, trans_id %s, amount %s, method %s" %
					 (id, response_code, reason_code, reason_text, auth_code, trans_id, amount, method))
		pat = re.compile(r'T(\d+)$')
		m = pat.match(id)
		if m:
			tribute_id = int(m.group(1))
			ad = TributeAd.get_by_id(tribute_id, parent = t.key)
			if ad and int(response_code) == 1:
				ad.payment_type = method
				ad.transaction_code = trans_id
				ad.auth_code = auth_code
				try:
					ad.payment_made += int(float(amount))
				except ValueError:
					logging.error("Could not convert amount %s to int" % amount)
				ad.put()
				if ad.email:
					email_cc_tribute_receipt(ad, tribute_id, card_type, auth_code, amount)
				auditing.audit(t, "Tribute Ad Payment",
							   tribute_id = tribute_id,
							   data = ("Response code %s, reason %s (\"%s\"), auth_code %s, trans_id %s, amount %s, method %s" %
									   (response_code, reason_code, reason_text, auth_code, trans_id, amount, method)),
							   request = self.request)
			else:
				auditing.audit(t, "Tribute Ad Payment Failed",
							   tribute_id = tribute_id,
							   data = ("Response code %s, reason %s (\"%s\"), auth_code %s, trans_id %s, amount %s, method %s" %
									   (response_code, reason_code, reason_text, auth_code, trans_id, amount, method)),
							   request = self.request)
		else:
			sponsor_id = None
			try:
				sponsor_id = int(id)
			except ValueError:
				logging.error("Invalid id \"%s\"" % id)
			if sponsor_id is not None:
				q = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == sponsor_id)
				s = q.get()
				if s and int(response_code) == 1:
					s.payment_type = method
					s.transaction_code = trans_id
					s.auth_code = auth_code
					try:
						s.payment_made += int(float(amount))
					except ValueError:
						logging.error("Could not convert amount %s to int" % amount)
					s.put()
					if s.email:
						email_cc_receipt(s, card_type, auth_code, amount)
					auditing.audit(t, "Golf/Dinner Payment",
								   sponsor_id = sponsor_id,
								   data = ("Response code %s, reason %s (\"%s\"), auth_code %s, trans_id %s, amount %s, method %s" %
										   (response_code, reason_code, reason_text, auth_code, trans_id, amount, method)),
								   request = self.request)
				else:
					auditing.audit(t, "Golf/Dinner Payment Failed",
								   sponsor_id = sponsor_id,
								   data = ("Response code %s, reason %s (\"%s\"), auth_code %s, trans_id %s, amount %s, method %s" %
										   (response_code, reason_code, reason_text, auth_code, trans_id, amount, method)),
								   request = self.request)
		parms = [
			('response_code', response_code),
			('reason_code', reason_code),
			('reason_text', reason_text),
			('auth_code', auth_code),
			('card_type', card_type),
			('id', id),
			('amount', amount),
			]
		receipt_url = '%s?%s' % (str(payments_info.receipt_url), urllib.urlencode(parms))
		self.response.out.write('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"')
		self.response.out.write('	"http://www.w3.org/TR/html4/loose.dtd">')
		self.response.out.write('<html>')
		self.response.out.write('<head>')
		self.response.out.write('<noscript>')
		self.response.out.write('<meta http-equiv="refresh" content="0;url=%s">' % receipt_url)
		self.response.out.write('</noscript>')
		self.response.out.write('</head>')
		self.response.out.write('<body>')
		self.response.out.write('<script type="text/javascript">')
		self.response.out.write('document.location = "%s";' % receipt_url)
		self.response.out.write('</script>')
		self.response.out.write('</body>')
		self.response.out.write('</html>')

# Process the receipt request from Authorize.net.

class Receipt(webapp2.RequestHandler):
	# Process the submitted info.
	def get(self):
		t = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		response_code = self.request.get('response_code')
		reason_code = self.request.get('reason_code')
		reason_text = self.request.get('reason_text')
		card_type = self.request.get('card_type')
		auth_code = self.request.get('auth_code')
		id = self.request.get('id')
		amount = self.request.get('amount')
		pat = re.compile(r'T(\d+)$')
		m = pat.match(id)
		if m:
			tribute_id = int(m.group(1))
			ad = None
			try:
				ad = TributeAd.get_by_id(tribute_id, parent = t.key)
			except:
				logging.error("Invalid tribute_id \"%s\"" % id)
			if not ad:
				self.response.out.write('<html><head>\n')
				self.response.out.write('<title>ID Not Found</title>\n')
				self.response.out.write('</head><body>\n')
				self.response.out.write('<h1>ID Not Found</h1>\n')
				self.response.out.write('<p>The requested tribute id &quot;%s&quot; was not found.</p>\n' % id)
				self.response.out.write('</body></html>\n')
				return
			template_values = {
				'email': ad.email,
				'amount': int(float(amount)),
				'response_code': int(response_code),
				'reason_code': int(reason_code),
				'reason_text': reason_text,
				'card_type': card_type,
				'auth_code': auth_code,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('receipt-tribute.html', template_values))
		else:
			sponsor_id = None
			s = None
			try:
				sponsor_id = int(id)
			except ValueError:
				logging.error("Invalid id \"%s\"" % id)
			if sponsor_id is not None:
				q = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == sponsor_id)
				s = q.get()
			if not s:
				self.response.out.write('<html><head>\n')
				self.response.out.write('<title>ID Not Found</title>\n')
				self.response.out.write('</head><body>\n')
				self.response.out.write('<h1>ID Not Found</h1>\n')
				self.response.out.write('<p>The requested registration id &quot;%s&quot; was not found.</p>\n' % id)
				self.response.out.write('</body></html>\n')
				return
			template_values = {
				'sponsor': s,
				'amount': int(float(amount)),
				'response_code': int(response_code),
				'reason_code': int(reason_code),
				'reason_text': reason_text,
				'card_type': card_type,
				'auth_code': auth_code,
				'capabilities': caps
				}
			self.response.out.write(render_to_string('receipt.html', template_values))

# Process the POST request from Acceptiva confirming payment.

class PostPayment(webapp2.RequestHandler):
	# Process the submitted info.
	def post(self):
		t = tournament.get_tournament()
		name = self.request.get('contactname')
		id = self.request.get('idnumberhidden')
		payment_made = self.request.get('amount_20_20_amt')
		paytype = self.request.get('paytype')
		transcode = self.request.get('transcode')
		logging.info("post payment for id %s: amount %s, paytype %s, transcode %s" %
					 (id, payment_made, paytype, transcode))
		q = Sponsor.query(ancestor = t.key).filter(Sponsor.sponsor_id == int(id))
		s = q.get()
		if not s:
			self.response.set_status(204, 'ID Not Found')
		else:
			s.payment_type = paytype
			s.transaction_code = transcode
			try:
				s.payment_made += int(payment_made) // 100
			except ValueError:
				s.payment_made += 0
			s.put()
			if s.email:
				email_cc_receipt(s, paytype, transcode, payment_made)
			self.response.set_status(204, 'Payment Posted')

# Simulate the acceptiva page (for testing).

class FakeAcceptiva(webapp2.RequestHandler):
	# Show the form.
	def get(self):
		name = self.request.get('contactname')
		id = self.request.get('idnumberhidden')
		payment_due = self.request.get('amount_20_20_amt')
		self.response.out.write('<html><body>\n')
		self.response.out.write('<h1>Fake Acceptiva</h1>\n')
		self.response.out.write('<form action="/postpayment" method="post">\n')
		self.response.out.write('<p>Name: %s</p>\n' % cgi.escape(name))
		self.response.out.write('<p>First Name: %s</p>\n' % cgi.escape(self.request.get('fname')))
		self.response.out.write('<p>Last Name: %s</p>\n' % cgi.escape(self.request.get('lname')))
		self.response.out.write('<p>Email: %s</p>\n' % cgi.escape(self.request.get('contactemailaddress')))
		self.response.out.write('<p>Sponsorships: %s</p>\n' % cgi.escape(self.request.get('sponsorshiplevel')))
		self.response.out.write('<p># Golfers: %s</p>\n' % cgi.escape(self.request.get('numberofgolfers')))
		self.response.out.write('<p># Dinner Guests: %s</p>\n' % cgi.escape(self.request.get('numberofdinnerguests')))
		self.response.out.write('<p>Payment Due: %s</p>\n' % cgi.escape(payment_due))
		self.response.out.write('<p>Address: %s</p>\n' % cgi.escape(self.request.get('address')))
		self.response.out.write('<p>City: %s</p>\n' % cgi.escape(self.request.get('city')))
		self.response.out.write('<p>State: %s</p>\n' % cgi.escape(self.request.get('state')))
		self.response.out.write('<p>ZIP: %s</p>\n' % cgi.escape(self.request.get('zip')))
		self.response.out.write('<p>Phone: %s</p>\n' % cgi.escape(self.request.get('phone')))
		self.response.out.write('<p>Email: %s</p>\n' % cgi.escape(self.request.get('email')))
		self.response.out.write('<p>ID: %s</p>\n' % cgi.escape(id))
		self.response.out.write('<input type="hidden" name="contactname" value="%s">\n' % cgi.escape(name, True))
		self.response.out.write('<input type="hidden" name="idnumberhidden" value="%s">\n' % cgi.escape(id))
		self.response.out.write('<input type="hidden" name="amount_20_20_amt" value="%d">\n' % (int(payment_due) * 100))
		self.response.out.write('<p>Payment Type: fake<input type="hidden" name="paytype" value="fake"></p>\n')
		self.response.out.write('<p>Transaction Code: <input type="text" name="transcode" value="1234"></p>\n')
		self.response.out.write('<p><input type="submit" value="Pay"></p>\n')
		self.response.out.write('</form>\n')
		self.response.out.write('<p><a href="/register?id=%s">Continue registration...</a></p>\n' % id)
		self.response.out.write('</body></html>\n')

# Handle a request for a tribute ad.

class Tribute(webapp2.RequestHandler):
	def show_form(self, t, ad, tribute_id, messages, existing_ad):
		today = datetime.datetime.now() - datetime.timedelta(hours=8)
		past_deadline = today.date() > t.tribute_deadline
		page = detailpage.get_detail_page('tribute', False)
		caps = capabilities.get_current_user_caps()
		template_values = {
			'capabilities': caps,
			'page': page,
			'messages': messages,
			'ad': ad,
			'tribute_id': tribute_id,
			'existing_ad': existing_ad,
			'past_deadline': past_deadline
			}
		self.response.out.write(render_to_string('tribute.html', template_values))

	def get(self):
		t = tournament.get_tournament()
		messages = []
		id_parm = self.request.get('id')
		if id_parm:
			try:
				num_id = int(id_parm)
			except ValueError:
				pass
			else:
				ad = TributeAd.get_by_id(num_id, parent = t.key)
				if ad:
					self.show_form(t, ad, id_parm, messages, "")
					return
			messages.append("Sorry, we could not find a Tribute Ad with ID %s" % id_parm)
		ad = TributeAd(parent = t.key)
		existing_ad = None
		id_from_cookie = self.request.cookies.get('tributeid')
		if id_from_cookie:
			try:
				num_id = int(id_from_cookie)
			except ValueError:
				self.request.cookies.delete('tributeid')
			else:
				existing_ad = TributeAd.get_by_id(num_id, parent = t.key)
		self.show_form(t, ad, "", messages, existing_ad)

	def post(self):
		t = tournament.get_tournament()
		today = datetime.datetime.now() - datetime.timedelta(hours=8)
		past_deadline = today.date() > t.tribute_deadline
		caps = capabilities.get_current_user_caps()
		messages = []
		id_parm = self.request.get('id') or ""
		first_name = self.request.get('first_name')
		last_name = self.request.get('last_name')
		email = self.request.get('email')
		phone = self.request.get('phone')
		ad_size = int(self.request.get('ad_size'))
		go_campaign = (self.request.get('go_campaign') == 'y')
		printed_names = self.request.get('printed_names')
		printed_names = re.sub(r'\s+', ' ', printed_names)
		price_list = [ 0, 36, 108, 360, 720, 1800, 3600 ]
		net_payment_due = price_list[ad_size] if ad_size >= 1 and ad_size <= 6 else 0
		if go_campaign:
			net_payment_due = 0 if net_payment_due <= 360 else net_payment_due - 360
		ad = None

		if id_parm:
			try:
				ad = TributeAd.get_by_id(int(id_parm), parent = t.key)
			except:
				messages.append("Could not find a Tribute Ad with id %s" % id_parm)

		if not ad:
			ad = TributeAd(parent = t.key)

		ad.first_name = first_name
		ad.last_name = last_name
		ad.email = email
		ad.phone = phone
		ad.ad_size = ad_size
		ad.go_campaign = go_campaign
		ad.printed_names = printed_names
		ad.payment_due = net_payment_due

		if not ad.first_name and not ad.last_name:
			messages.append('Please enter your name.')
		elif not ad.first_name or not ad.last_name:
			messages.append('Please enter both first and last name.')
		if ad.email == '':
			messages.append('Please enter your email address.')
		if ad.phone == '':
			messages.append('Please enter your phone number.')
		if ad_size < 1 or ad_size > 6:
			messages.append('Please select an ad size.')
		if past_deadline and not caps.can_add_registrations:
			messages.append('Sorry, the deadline has passed.')

		if caps.can_add_registrations:
			payment_made = self.request.get('payment_made')
			if payment_made == '':
				ad.payment_made = 0
				ad.payment_type = ''
				ad.transaction_code = ''
				ad.auth_code = ''
			else:
				try:
					ad.payment_made = int(payment_made)
				except ValueError:
					ad.payment_made = 0
					messages.append('You entered an invalid value in the "Payment Made" field.')
				ad.payment_type = self.request.get('paytype')
				ad.transaction_code = self.request.get('transcode')
				ad.auth_code = self.request.get('authcode')

		if messages:
			self.show_form(t, ad, id_parm, messages, '')
			return

		if caps.can_add_registrations and self.request.get('save'):
			pass
		elif self.request.get('pay_by_check'):
			ad.payment_type = 'check'
		else:
			ad.payment_type = 'credit'

		ad.put()
		tribute_id = ad.key.id()
		logging.info("Tribute ad for %s %s, amount due $%d, pay by %s" %
					 (ad.first_name, ad.last_name, ad.payment_due, ad.payment_type))
		action = "Updated" if id_parm else "Added"
		auditing.audit(t, "%s Tribute Ad" % action,
					   tribute_id = tribute_id,
					   data = "%s %s: due $%d, pay by %s" % (ad.first_name, ad.last_name, ad.payment_due - ad.payment_made, ad.payment_type),
					   request = self.request)

		if self.request.get('save') and caps.can_add_registrations:
			self.redirect('/admin/view/tribute')
			return

		if not caps.can_add_registrations:
			self.response.set_cookie('tributeid', str(tribute_id), expires=datetime.datetime.combine(t.golf_date, datetime.time(23,59)))

		if ad.payment_type == 'check' or self.request.get('save'):
			template_values = {
				'tribute_id': str(tribute_id),
				'first_name': first_name,
				'last_name': last_name,
				'email': email,
				'phone': phone,
				'net_payment_due': net_payment_due,
				'capabilities': caps
			}
			self.response.out.write(render_to_string('paybycheck-tribute.html', template_values))
			return

		payments_info = payments.get_payments_info(t)

		if payments_info.gateway_url and 'authorize.net' in payments_info.gateway_url:
			cust_id = 'T%d' % tribute_id
			timestamp = int(time.time())
			fingerprint = hmac.new(payments_info.transaction_key.encode())
			fingerprint.update(payments_info.api_login_id)
			fingerprint.update('^')
			fingerprint.update(cust_id)
			fingerprint.update('^')
			fingerprint.update(str(timestamp))
			fingerprint.update('^')
			fingerprint.update(str(net_payment_due))
			fingerprint.update('^')
			description = "Celebration Classic Tribute Ad"
			api_fields = [
				('x_test_request', 'TRUE' if payments_info.test_mode else 'FALSE'),
				('x_login', payments_info.api_login_id),
				('x_fp_sequence', cust_id),
				('x_fp_timestamp', str(timestamp)),
				('x_fp_hash', fingerprint.hexdigest()),
				('x_version', '3.1'),
				('x_method', 'CC'),
				('x_type', 'AUTH_CAPTURE'),
				('x_cust_id', cust_id),
				('x_description', description),
				('x_email_customer', 'FALSE'),
				('x_delim_data', 'FALSE'),
				('x_relay_response', 'TRUE'),
				('x_relay_url', payments_info.relay_url),
				]
			template_values = {
				'tribute_id': str(tribute_id),
				'first_name': first_name,
				'last_name': last_name,
				'email': email,
				'phone': phone,
				'gateway_url': payments_info.gateway_url,
				'api_fields': api_fields,
				'net_payment_due': str(net_payment_due),
				'capabilities': caps
			}
			self.response.out.write(render_to_string('paybycredit-tribute.html', template_values))

		else:
			messages.append('Sorry, we are not yet accepting credit card payments.')
			self.show_form(t, ad, str(tribute_id), messages, '')

app = webapp2.WSGIApplication([('/register', Register),
							   ('/continue', Continue),
							   ('/relayresponse', RelayResponse),
							   ('/receipt', Receipt),
							   ('/fakeacceptiva', FakeAcceptiva),
							   ('/postpayment', PostPayment),
							   ('/tribute', Tribute)],
							  debug=dev_server)
