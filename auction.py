import os
import cgi
import logging
import webapp2
from google.appengine.api import images
from django.template.loaders.filesystem import Loader
from django.template.loader import render_to_string

import auctionitem

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

class Auction(webapp2.RequestHandler):
	def get(self):
		auction_items = auctionitem.get_auction_items()
		template_values = {
			'auction_items': auction_items
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

app = webapp2.WSGIApplication([('/auction.html', Auction),
							   ('/img/(.*)', ServeThumbnail)],
							  debug=dev_server)
