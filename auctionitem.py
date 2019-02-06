from google.appengine.ext import ndb
from google.appengine.api import memcache

import tournament

class AuctionItem(ndb.Model):
	which = ndb.StringProperty()		# 'l' (Live) or 's' (Silent)
	sequence = ndb.IntegerProperty(default = 0)
	description = ndb.TextProperty(default = "")
	image = ndb.BlobProperty()
	image_width = ndb.IntegerProperty()
	image_height = ndb.IntegerProperty()

def get_auction_items(t, which):
	auction_items = memcache.get("%s/auction_items/%s" % (t.name, which))
	if auction_items is not None:
		return auction_items
	q = AuctionItem.query(ancestor = t.key)
	q = q.filter(AuctionItem.which == which)
	q = q.order(AuctionItem.sequence)
	auction_items = q.fetch(30)
	memcache.set("%s/auction_items/%s" % (t.name, which), auction_items, 60*60*24)
	return auction_items

def clear_auction_item_cache(root):
	memcache.delete("%s/auction_items/l" % root.name)
	memcache.delete("%s/auction_items/s" % root.name)
