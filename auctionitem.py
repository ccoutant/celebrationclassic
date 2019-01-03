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
	root = tournament.get_tournament()
	auction_items = memcache.get("%s/auction_items" % root.name)
	if auction_items is not None:
		return auction_items
	q = AuctionItem.all()
	q.ancestor(root)
	q.order("sequence")
	auction_items = q.fetch(30)
	memcache.add("%s/auction_items" % root.name, auction_items, 60*60*24)
	return auction_items

class SilentAuctionItem(db.Model):
	sequence = db.IntegerProperty(default = 0)
	description = db.TextProperty(default = "")
	photo_blob = blobstore.BlobReferenceProperty()
	thumbnail_id = db.IntegerProperty()
	thumbnail_width = db.IntegerProperty()
	thumbnail_height = db.IntegerProperty()

def get_silent_auction_items():
	root = tournament.get_tournament()
	auction_items = memcache.get("%s/silent_auction_items" % root.name)
	if auction_items is not None:
		return auction_items
	q = SilentAuctionItem.all()
	q.ancestor(root)
	q.order("sequence")
	auction_items = q.fetch(30)
	memcache.add("%s/silent_auction_items" % root.name, auction_items, 60*60*24)
	return auction_items

def clear_auction_item_cache(root):
	memcache.delete("%s/auction_items" % root.name)
	memcache.delete("%s/silent_auction_items" % root.name)
