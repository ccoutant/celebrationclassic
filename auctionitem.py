from google.appengine.ext import db, blobstore
from google.appengine.api import memcache

import tournament

class Thumbnail(db.Model):
	image = db.BlobProperty()

class AuctionItem(db.Model):
	sequence = db.IntegerProperty(default = 0)
	description = db.TextProperty(default = "")
	photo_blob = blobstore.BlobReferenceProperty()
	thumbnail_id = db.IntegerProperty()
	thumbnail_width = db.IntegerProperty()
	thumbnail_height = db.IntegerProperty()

def get_auction_items():
	auction_items = memcache.get("2015/auction_items")
	if auction_items is not None:
		return auction_items
	root = tournament.get_tournament()
	q = AuctionItem.all()
	q.ancestor(root)
	q.order("sequence")
	auction_items = q.fetch(30)
	memcache.add("2015/auction_items", auction_items, 60*60*24)
	return auction_items

class SilentAuctionItem(db.Model):
	sequence = db.IntegerProperty(default = 0)
	description = db.TextProperty(default = "")
	photo_blob = blobstore.BlobReferenceProperty()
	thumbnail_id = db.IntegerProperty()
	thumbnail_width = db.IntegerProperty()
	thumbnail_height = db.IntegerProperty()

def get_silent_auction_items():
	auction_items = memcache.get("2015/silent_auction_items")
	if auction_items is not None:
		return auction_items
	root = tournament.get_tournament()
	q = SilentAuctionItem.all()
	q.ancestor(root)
	q.order("sequence")
	auction_items = q.fetch(30)
	memcache.add("2015/silent_auction_items", auction_items, 60*60*24)
	return auction_items

def clear_auction_item_cache():
	memcache.delete("2015/auction_items")
	memcache.delete("2015/silent_auction_items")
