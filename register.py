#!/usr/bin/env python

import datetime
import os
import cgi
import logging
import random
import urllib
import re
import webapp2
from google.appengine.ext import db
from google.appengine.api import memcache
from django.template.loaders.filesystem import Loader
from django.template.loader import render_to_string

import tournament
import capabilities
import detailpage
import sponsorship
from sponsor import Sponsor, Golfer, DinnerGuest

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

# Show the initial registration form.

def show_registration_form(response, root, s, messages, caps, debug):
	# Get today's date in PST. (We won't worry about DST, so early bird pricing will
	# last until 1 am PDT.)
	today = datetime.datetime.now() - datetime.timedelta(hours=8)
	early_bird = today.date() <= root.early_bird_deadline
	registration_closed = today.date() > root.deadline
	early_bird_deadline = "%s %d, %d" % (root.early_bird_deadline.strftime("%B"),
										 root.early_bird_deadline.day,
										 root.early_bird_deadline.year)
	deadline = "%s %d, %d" % (root.deadline.strftime("%B"),
							  root.deadline.day,
							  root.deadline.year)
	doubleeagle = sponsorship.get_sponsorships("Double Eagle")
	holeinone = sponsorship.get_sponsorships("Hole in One")
	eagle = sponsorship.get_sponsorships("Eagle")
	underpar = sponsorship.get_sponsorships("Under Par")
	angel = sponsorship.get_sponsorships("Angel")
	selected_sponsorships = []
	for sskey in s.sponsorships:
		ss = db.get(sskey)
		if ss:
			selected_sponsorships.append(ss.sequence)
	page = detailpage.get_detail_page('register', False)
	template_values = {
		'tournament': root,
		'sponsor': s,
		'early_bird': early_bird,
		'registration_closed': registration_closed,
		'early_bird_deadline': early_bird_deadline,
		'deadline': deadline,
		'doubleeagle': doubleeagle,
		'holeinone': holeinone,
		'eagle': eagle,
		'underpar': underpar,
		'angel': angel[0],
		'selected': selected_sponsorships,
		'page': page,
		'messages': messages,
		'capabilities': caps,
		'debug': debug
	}
	response.out.write(render_to_string('register.html', template_values))

# Show the continuation form.

def show_continuation_form(response, s, messages, caps, debug):
	q = Golfer.all().ancestor(s.key()).order('sequence')
	golfers = q.fetch(s.num_golfers)
	for i in range(len(golfers) + 1, s.num_golfers + 1):
		golfer = Golfer(parent = s, sequence = i)
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
	q = DinnerGuest.all().ancestor(s.key()).order('sequence')
	dinner_guests = q.fetch(s.num_dinners)
	for i in range(len(dinner_guests) + 1, s.num_dinners + 1):
		guest = DinnerGuest(parent = s, sequence = i)
		if s.num_golfers + i == 1:
			guest.name = s.name
		dinner_guests.append(guest)
	template_values = {
		'sponsor': s,
		'golfers': golfers,
		'dinner_guests': dinner_guests,
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
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		messages = []
		if self.request.get('id'):
			id = self.request.get('id')
			q = Sponsor.all()
			q.ancestor(root)
			q.filter('id = ', int(id))
			s = q.get()
			if s:
				if self.request.get('page') == '1':
					show_registration_form(self.response, root, s, messages, caps, dev_server)
				else:
					show_continuation_form(self.response, s, messages, caps, dev_server)
				return
			messages.append('Sorry, we could not find a registration for ID %s' % id)
		s = Sponsor(sponsorships = [])
		show_registration_form(self.response, root, s, messages, caps, dev_server)

	# Process the submitted info.
	def post(self):
		messages = []
		root = tournament.get_tournament()
		# Get today's date in PST. (We won't worry about DST, so early bird pricing will
		# last until 1 am PDT.)
		today = datetime.datetime.now() - datetime.timedelta(hours=8)
		early_bird = today.date() <= root.early_bird_deadline
		registration_closed = today.date() > root.deadline
		golf_price = root.golf_price_early if early_bird else root.golf_price_late
		dinner_price = root.dinner_price_early if early_bird else root.dinner_price_late
		caps = capabilities.get_current_user_caps()
		id = int(self.request.get('id'))
		if id:
			q = Sponsor.all()
			q.ancestor(root)
			q.filter('id = ', id)
			s = q.get()
		else:
			s = Sponsor(parent=root)
		s.first_name = self.request.get('first_name')
		s.last_name = self.request.get('last_name')
		s.company = self.request.get('company')
		s.address = self.request.get('address')
		s.city = self.request.get('city')
		s.state = self.request.get('state')
		s.zip = self.request.get('zip')
		s.phone = self.request.get('phone')
		s.fax = self.request.get('fax')
		s.email = self.request.get('email')
		s.anonymous = False if self.request.get('agree') == 'y' else True
		s.printed_names = self.request.get('printed_names')
		s.sponsorships = []
		s.num_golfers = int(self.request.get('num_golfers'))
		s.num_dinners = int(self.request.get('num_dinners'))
		s.payment_due = 0
		s.payment_made = 0

		if registration_closed and not caps.can_add_registrations:
			messages.append('Sorry, registration is closed.')
			show_registration_form(self.response, root, s, messages, caps, dev_server)
			return

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
			if root.golf_sold_out and s.num_golfers > 0:
				messages.append('Sorry, the golf tournament is sold out.')
			if root.dinner_sold_out and s.num_dinners > 0:
				messages.append('Sorry, the dinner is sold out.')

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
				s.sponsorships.append(ss.key())
				sponsorship_names.append(ss.name)
				s.payment_due += ss.price
				golfers_included += ss.golfers_included
		dinners_included = golfers_included
		if s.num_golfers > golfers_included:
			s.payment_due += golf_price * (s.num_golfers - golfers_included)
		else:
			dinners_included += golfers_included - s.num_golfers
		if s.num_dinners > dinners_included:
			s.payment_due += dinner_price * (s.num_dinners - dinners_included)
		s.payment_due += s.additional_donation
		if s.payment_due <= 0:
			messages.append('You have not chosen any sponsorships, golfers, or dinners.')
		if s.payment_due != form_payment_due:
			messages.append('There was an error processing the form: payment due does not match selected sponsorships and number of golfers and dinners.')
			logging.info('Payment Due from form was %d, calculated %d instead' % (form_payment_due, s.payment_due))

		if caps.can_add_registrations:
			payment_made = self.request.get('payment_made')
			if payment_made == '':
				s.payment_made = 0
				s.payment_type = ''
				s.transaction_code = ''
			else:
				try:
					s.payment_made = int(payment_made)
				except ValueError:
					s.payment_made = 0
					messages.append('You entered an invalid value in the "Payment Made" field.')
				s.payment_type = self.request.get('paytype')
				s.transaction_code = self.request.get('transcode')
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

		if messages:
			if root.golf_sold_out:
				s.num_golfers = 0
			if root.dinner_sold_out:
				s.num_dinners = 0
			show_registration_form(self.response, root, s, messages, caps, dev_server)
			return

		if s.id == 0:
			while True:
				s.id = random.randrange(100000,999999)
				q = Sponsor.all()
				q.ancestor(root)
				q.filter('id = ', s.id)
				result = q.get()
				if not result: break
				logging.info('ID collision for %d; retrying...' % s.id)
		s.put()
		memcache.delete('2015/admin/view/golfers')
		memcache.delete('2015/admin/view/dinners')
		if caps.can_add_registrations and (s.payment_made > 0 or s.discount > 0) and self.request.get('save'):
			self.redirect('/register')
			return
		self.redirect('/register?id=%d' % s.id)

# Registration Step 2.

class Continue(webapp2.RequestHandler):
	# Process the submitted info.
	def post(self):
		messages = []
		root = tournament.get_tournament()
		caps = capabilities.get_current_user_caps()
		id = self.request.get('id')
		q = Sponsor.all()
		q.ancestor(root)
		q.filter('id = ', int(id))
		s = q.get()
		if not s:
			messages.append('Sorry, we could not find a registration for ID %s' % id)
			s = Sponsor(sponsorships = [])
			show_registration_form(self.response, root, s, messages, caps, dev_server)
			return

		q = Golfer.all().ancestor(s.key()).order('sequence')
		golfers = q.fetch(limit = None)
		for i in range(1, s.num_golfers + 1):
			if len(golfers) < i:
				golfers.append(Golfer(parent = s, sequence = i))
			golfer = golfers[i-1]
			golfer.active = True
			golfer.first_name = self.request.get('first_name%d' % i)
			golfer.last_name = self.request.get('last_name%d' % i)
			if golfer.last_name:
				golfer.sort_name = golfer.last_name + ',' + golfer.first_name
			else:
				golfer.sort_name = s.last_name + '#' + ("%02d" % i)
			golfer.gender = self.request.get('gender%d' % i)
			golfer.company = self.request.get('company%d' % i)
			golfer.address = self.request.get('address%d' % i)
			golfer.city = self.request.get('city%d' % i)
			golfer.state = self.request.get('state%d' % i)
			golfer.zip = self.request.get('zip%d' % i)
			golfer.phone = self.request.get('phone%d' % i)
			golfer.email = self.request.get('email%d' % i)
			golfer.average_score = self.request.get('avg%d' % i)
			golfer.ghin_number = self.request.get('ghin%d' % i)
			golfer.shirt_size = self.request.get('shirtsize%d' % i)
			golfer.dinner_choice = self.request.get('golfer_choice%d' % i)
			golfer.put()

		# Mark excess golfer instances as not active, so we can filter
		# them out when querying all golfers.
		if len(golfers) > s.num_golfers:
			for i in range(s.num_golfers, len(golfers)):
				golfers[i].active = False
				golfers[i].put()

		q = DinnerGuest.all().ancestor(s.key()).order('sequence')
		dinner_guests = q.fetch(s.num_dinners)
		for i in range(1, s.num_dinners + 1):
			if len(dinner_guests) < i:
				dinner_guests.append(DinnerGuest(parent = s, sequence = i))
			guest = dinner_guests[i-1]
			guest.first_name = self.request.get('guest_first_name%d' % i)
			guest.last_name = self.request.get('guest_last_name%d' % i)
			guest.dinner_choice = self.request.get('guest_choice%d' % i)
			guest.put()

		s.pairing = self.request.get('pairing')
		s.dinner_seating = self.request.get('dinner_seating')
		s.confirmed = True
		s.put()
		memcache.delete('2015/admin/view/golfers')
		memcache.delete('2015/admin/view/dinners')

		if caps.can_add_registrations and self.request.get('save'):
			self.redirect('/admin/view/registrations')
			return

		if s.payment_made > 0:
			template_values = {
				'sponsor': s,
				'capabilities': caps
			}
			self.response.out.write(render_to_string('ack.html', template_values))
			return

		if self.request.get('pay_by_check'):
			template_values = {
				'sponsor': s,
				'capabilities': caps
			}
			self.response.out.write(render_to_string('paybycheck.html', template_values))
			return

		sponsorship_names = []
		for sskey in s.sponsorships:
			ss = db.get(sskey)
			if ss:
				sponsorship_names.append(ss.name)
		parms = [('cst', '60605a'),
				 ('contactname', s.first_name + " " + s.last_name),
				 ('contactemailaddress', s.email),
				 ('sponsorshiplevel', ','.join(sponsorship_names)),
				 ('numberofgolfers', s.num_golfers),
				 ('numberofdinnerguests', s.num_dinners),
				 ('amount_20_20_amt', s.payment_due),
				 ('idnumberhidden', s.id),
				 ('fname', s.first_name),
				 ('lname', s.last_name),
				 ('address', s.address),
				 ('city', s.city),
				 ('state', s.state),
				 ('zip', s.zip),
				 ('phone', s.phone),
				 ('email', s.email)]
		acceptiva = 'https://secure.acceptiva.com/' if not dev_server else '/fakeacceptiva'
		self.redirect('%s?%s' % (acceptiva, urllib.urlencode(parms)))

# Process the POST request from Acceptiva confirming payment.

class PostPayment(webapp2.RequestHandler):
	# Process the submitted info.
	def post(self):
		root = tournament.get_tournament()
		name = self.request.get('contactname')
		id = self.request.get('idnumberhidden')
		payment_made = self.request.get('amount_20_20_amt')
		paytype = self.request.get('paytype')
		transcode = self.request.get('transcode')
		q = Sponsor.all()
		q.ancestor(root)
		q.filter('id = ', int(id))
		s = q.get()
		if not s:
			self.response.set_status(204, 'ID Not Found')
		else:
			s.payment_type = paytype
			s.transaction_code = transcode
			try:
				s.payment_made = int(payment_made) // 100
			except ValueError:
				s.payment_made = 0
			s.put()
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

app = webapp2.WSGIApplication([('/register', Register),
							   ('/continue', Continue),
							   ('/postpayment', PostPayment),
							   ('/fakeacceptiva', FakeAcceptiva)],
							  debug=dev_server)
