#!/usr/bin/env python

import os
import re
import quopri
import cgi
import logging
from google.appengine.ext import db, webapp, blobstore
from google.appengine.ext.webapp import template, util, blobstore_handlers
from google.appengine.api import users, memcache, images

import capabilities
import sponsorship
import auctionitem
from sponsor import Sponsor, Golfer, DinnerGuest

webapp.template.register_template_library('tags.custom_filters')

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

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
<tr><th>Email</th><th>Name</th><th>Update Sponsorships</th><th>View Registrations</th><th>Add Registrations</th><th>Update Auction</th></tr>
""")
		seq = 1
		for u in caps:
			self.response.out.write('<tr>\n')
			self.response.out.write('<td>%s<input type="hidden" name="email%d" value="%s"></td>\n' % (cgi.escape(u.email), seq, cgi.escape(u.email)))
			self.response.out.write('<td>%s</td>\n' % users.User(u.email).nickname())
			self.response.out.write('<td><input type="checkbox" name="us%d" value="u" %s></td>\n' % (seq, "checked" if u.can_update_sponsorships else ""))
			self.response.out.write('<td><input type="checkbox" name="vr%d" value="v" %s></td>\n' % (seq, "checked" if u.can_view_registrations else ""))
			self.response.out.write('<td><input type="checkbox" name="ar%d" value="a" %s></td>\n' % (seq, "checked" if u.can_add_registrations else ""))
			self.response.out.write('<td><input type="checkbox" name="ua%d" value="u" %s></td>\n' % (seq, "checked" if u.can_update_auction else ""))
			self.response.out.write('</tr>\n')
			seq += 1
		self.response.out.write('<tr>\n')
		self.response.out.write('<td><input type="text" size="30" name="email" value=""></td>\n')
		self.response.out.write('<td></td>\n')
		self.response.out.write('<td><input type="checkbox" name="us" value="u"></td>\n')
		self.response.out.write('<td><input type="checkbox" name="vr" value="v"></td>\n')
		self.response.out.write('<td><input type="checkbox" name="ar" value="a"></td>\n')
		self.response.out.write('<td><input type="checkbox" name="ua" value="u"></td>\n')
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
		count = int(self.request.get('count'))
		for i in range(1, count):
			email = self.request.get('email%d' % i)
			q = capabilities.Capabilities.all()
			q.filter("email = ", email)
			u = q.get()
			us = True if self.request.get('us%d' % i) == 'u' else False
			vr = True if self.request.get('vr%d' % i) == 'v' else False
			ar = True if self.request.get('ar%d' % i) == 'a' else False
			ua = True if self.request.get('ua%d' % i) == 'u' else False
			if us != u.can_update_sponsorships or vr != u.can_view_registrations or ar != u.can_add_registrations or ua != u.can_update_auction:
				u.can_update_sponsorships = us
				u.can_view_registrations = vr
				u.can_add_registrations = ar
				u.can_update_auction = ua
				u.put()
		email = self.request.get('email')
		us = True if self.request.get('us') == 'u' else False
		vr = True if self.request.get('vr') == 'v' else False
		ar = True if self.request.get('ar') == 'a' else False
		ua = True if self.request.get('ua') == 'u' else False
		if email:
			u = capabilities.Capabilities(email = email, can_update_sponsorships = us, can_view_registrations = vr, can_add_registrations = ar, can_update_auction = ua)
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
		user = capabilities.get_current_user_caps()
		if user is None or not user.can_update_sponsorships:
			self.redirect(users.create_login_url('/admin/sponsorships'))
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

class ViewRegistrations(webapp.RequestHandler):
	def get(self, what):
		user = capabilities.get_current_user_caps()
		if user is None or not user.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		if what == "sponsors":
			if self.request.get('start'):
				start = int(self.request.get('start'))
			else:
				start = 0
			lim = 20
			q = Sponsor.all()
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
				'nav': nav
				}
			self.response.out.write(template.render('viewsponsors.html', template_values))
		elif what == "incomplete":
			q = Sponsor.all()
			q.order("timestamp")
			sponsors = []
			for s in q:
				if s.payment_made == 0:
					sponsors.append(s)
				else:
					golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
					ndinners = 0
					for g in golfers:
						if g.dinner_choice:
							ndinners += 1
					guests = DinnerGuest.all().ancestor(s.key()).fetch(s.num_dinners)
					for g in guests:
						if g.dinner_choice:
							ndinners += 1
					if ndinners < s.num_golfers + s.num_dinners:
						sponsors.append(s)
			nav = []
			template_values = {
				'sponsors': sponsors,
				'incomplete': True,
				'nav': nav
				}
			self.response.out.write(template.render('viewsponsors.html', template_values))
		elif what == "golfers":
			html = memcache.get('/admin/view/golfers')
			if html:
				self.response.out.write(html)
				return
			all_golfers = []
			counter = 1
			q = Sponsor.all()
			q.order("timestamp")
			for s in q:
				golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
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
				'shirt_sizes': shirt_sizes
				}
			html = template.render('viewgolfers.html', template_values)
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
			q.order("timestamp")
			for s in q:
				golfers = Golfer.all().ancestor(s.key()).fetch(s.num_golfers)
				for g in golfers:
					if g.dinner_choice != 'No Dinner':
						all_dinners.append(ViewDinner(s, g.name, g.dinner_choice, g.sequence, counter))
						counter += 1
				for i in range(len(golfers) + 1, s.num_golfers + 1):
					all_dinners.append(ViewDinner(s, '', '', i, counter))
					counter += 1
				guests = DinnerGuest.all().ancestor(s.key()).fetch(s.num_dinners)
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
				'dinner_choices': dinner_choices
				}
			html = template.render('viewguests.html', template_values)
			memcache.add('/admin/view/guests', html, 60*60*24)
			self.response.out.write(html)
		else:
			self.error(404)

def csv_encode(val):
	val = re.sub(r'"', '""', str(val or ''))
	return '"%s"' % val

class DownloadCSV(webapp.RequestHandler):
	def get(self, what):
		user = capabilities.get_current_user_caps()
		if user is None or not user.can_view_registrations:
			self.redirect(users.create_login_url(self.request.uri))
			return
		if what == "sponsors":
			q = Sponsor.all()
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
			q.order("timestamp")
			csv = []
			csv.append(','.join(['contact', 'name', 'gender', 'title', 'company', 'address', 'city',
								 'email', 'phone', 'golf_index', 'best_score', 'ghn_number',
								 'shirt_size']))
			for s in q:
				q = Golfer.all().ancestor(s.key())
				golfers = q.fetch(s.num_golfers)
				for g in golfers:
					csv.append(','.join([csv_encode(x)
										 for x in [s.name, g.name, g.gender, g.company, g.title,
												   g.address, g.city, g.email, g.phone,
												   g.golf_index, g.best_score, g.ghn_number,
												   g.shirt_size]]))
				for i in range(len(golfers) + 1, s.num_golfers + 1):
					csv.append(','.join([csv_encode(x)
										 for x in [s.name, 'n/a', '', '', '', '', '', '', '',
												   '', '', '', '']]))
		elif what == "guests":
			q = Sponsor.all()
			q.order("timestamp")
			csv = []
			csv.append(','.join(['contact', 'name', 'dinner_choice']))
			for s in q:
				q = Golfer.all().ancestor(s.key())
				golfers = q.fetch(s.num_golfers)
				for g in golfers:
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

# Auction Items

class ManageAuction(webapp.RequestHandler):
	# Show the form.
	def get(self):
		user = capabilities.get_current_user_caps()
		if user is None or not user.can_update_auction:
			self.redirect(users.create_login_url(self.request.uri))
			return
		if self.request.get('key'):
			key = self.request.get('key')
			item = auctionitem.AuctionItem.get(key)
			template_values = {
				'item': item,
				'key': key,
				'upload_url': blobstore.create_upload_url('/admin/upload-auction')
				}
			self.response.out.write(template.render('editauction.html', template_values))
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
				'upload_url': blobstore.create_upload_url('/admin/upload-auction')
				}
			self.response.out.write(template.render('editauction.html', template_values))
		else:
			auction_items = auctionitem.get_auction_items()
			template_values = {
				'auction_items': auction_items
				}
			self.response.out.write(template.render('adminauction.html', template_values))

class UploadAuctionItem(blobstore_handlers.BlobstoreUploadHandler):
	# Process the submitted info.
	def post(self):
		user = capabilities.get_current_user_caps()
		if user is None or not user.can_update_auction:
			self.redirect(users.create_login_url('/admin/auction'))
			return
		key = self.request.get('key')
		if key:
			item = auctionitem.AuctionItem.get(key)
		else:
			item = auctionitem.AuctionItem()
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
		memcache.delete("auction_items")
		self.redirect("/admin/auction")

def main():
	logging.getLogger().setLevel(logging.INFO)
	application = webapp.WSGIApplication([('/admin/sponsorships', Sponsorships),
										  ('/admin/users', ManageUsers),
										  ('/admin/auction', ManageAuction),
										  ('/admin/upload-auction', UploadAuctionItem),
										  ('/admin/view/(.*)', ViewRegistrations),
										  ('/admin/csv/(.*)', DownloadCSV),
										  ('/admin/logout', Logout)],
										 debug=dev_server)
	util.run_wsgi_app(application)

if __name__ == '__main__':
	main()
