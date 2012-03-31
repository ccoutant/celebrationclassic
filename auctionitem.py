from google.appengine.ext import db, blobstore
from google.appengine.api import memcache

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
	auction_items = memcache.get("auction_items")
	if auction_items is not None:
		return auction_items
	else:
		q = AuctionItem.all()
		q.order("sequence")
		auction_items = q.fetch(30)
		memcache.add("auction_items", auction_items, 60*60*24)
		return auction_items
