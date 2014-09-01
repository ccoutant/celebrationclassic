import os
import cgi
import logging
import webapp2
from google.appengine.api import images
from django.template.loaders.filesystem import Loader
from django.template.loader import render_to_string

import auctionitem
import capabilities
import tournament

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

class Auction(webapp2.RequestHandler):
	def get(self):
		t = tournament.get_tournament()
		dinner_date = "%s, %s %d, %d" % (t.dinner_date.strftime("%A"), t.dinner_date.strftime("%B"),
										 t.dinner_date.day, t.dinner_date.year)
		auction_items = auctionitem.get_auction_items()
		caps = capabilities.get_current_user_caps()
		template_values = {
			'auction_items': auction_items,
			'dinner_date': dinner_date,
			'capabilities': caps
			}
		self.response.out.write(render_to_string('auction.html', template_values))

class ServeThumbnail(webapp2.RequestHandler):
	def get(self, id):
		thumb = auctionitem.Thumbnail.get_by_id(long(id))
		if thumb:
			self.response.headers['Content-Type'] = 'image/jpeg'
			self.response.headers['Cache-Control'] = 'public, max-age=86400;'
			self.response.out.write(thumb.image)
		else:
			self.error(404)

app = webapp2.WSGIApplication([('/auction', Auction),
							   ('/img/(.*)', ServeThumbnail)],
							  debug=dev_server)
