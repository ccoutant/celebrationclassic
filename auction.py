import os
import cgi
import logging
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template, util

import auctionitem

webapp.template.register_template_library('tags.custom_filters')

server_software = os.environ.get('SERVER_SOFTWARE')
dev_server = True if server_software and server_software.startswith("Development") else False

class Auction(webapp.RequestHandler):
	def get(self):
		auction_items = auctionitem.get_auction_items()
		template_values = {
			'auction_items': auction_items
			}
		self.response.out.write(template.render('auction.html', template_values))

def main():
	logging.getLogger().setLevel(logging.INFO)
	application = webapp.WSGIApplication([('/auction.html', Auction)],
										 debug=dev_server)
	util.run_wsgi_app(application)

if __name__ == '__main__':
	main()
