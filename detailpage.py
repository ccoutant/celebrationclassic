#!/usr/bin/env python

import logging
from google.appengine.ext import db
from google.appengine.api import memcache

import tournament

class DetailPage(db.Model):
	name = db.StringProperty(required = True)
	version = db.IntegerProperty(required = True)
	title = db.StringProperty(default = "")
	content = db.TextProperty(default = "")
	draft = db.BooleanProperty(default = False)
	preview = db.BooleanProperty(default = False)
	last_modified = db.DateTimeProperty(required = True, auto_now = True)

class PageVersion(db.Model):
	name = db.StringProperty(required = True)
	published_version = db.IntegerProperty(default = 0)
	draft_version = db.IntegerProperty(default = 0)

def get_published_version(name):
	versions = memcache.get("2015/published_versions")
	if not versions:
		t = tournament.get_tournament()
		q = PageVersion.all()
		q.ancestor(t)
		q.order('name')
		versions = { v.name: v.published_version for v in q }
		if versions:
			memcache.add("2015/published_versions", versions, 60*60*24)
	if versions.has_key(name):
		return versions[name]
	return 0

def get_draft_version(name):
	versions = memcache.get("2015/draft_versions")
	if not versions:
		t = tournament.get_tournament()
		q = PageVersion.all()
		q.ancestor(t)
		q.order('name')
		versions = { v.name: v.draft_version for v in q }
		if versions:
			memcache.add("2015/draft_versions", versions, 60*60*24)
	if versions.has_key(name):
		return versions[name]
	return 0

def set_version(name, v, draft):
	t = tournament.get_tournament()
	q = PageVersion.all()
	q.ancestor(t)
	q.filter("name = ", name)
	pageversion = q.get()
	if not pageversion:
		pageversion = PageVersion(parent = t, name = name, published_version = 0 if draft else v, draft_version = v)
	else:
		if not draft:
			pageversion.published_version = v
		pageversion.draft_version = v
	pageversion.put()
	memcache.delete("2015/draft_versions")
	memcache.delete("2015/published_versions")

def detail_page_list():
	return ["home", "details", "raffle", "map", "sponsors", "sponsorships", "volunteer", "register"]

def get_detail_page(name, draft):
	if not name in detail_page_list():
		return None
	t = tournament.get_tournament()
	v = get_draft_version(name) if draft else get_published_version(name)
	if v is None:
		v = 0
	q = DetailPage.all()
	q.ancestor(t)
	q.filter("name = ", name)
	q.filter("version = ", v)
	page = q.get()
	if not page:
		page = DetailPage(parent = t, name = name, version = v, title = name, content = "Sorry, no content yet.")
	return page
