#!/usr/bin/env python

import logging
from google.appengine.ext import ndb
from google.appengine.api import memcache

import tournament

class DetailPage(ndb.Model):
	name = ndb.StringProperty(required = True)
	version = ndb.IntegerProperty(required = True)
	title = ndb.StringProperty(default = "")
	content = ndb.TextProperty(default = "")
	draft = ndb.BooleanProperty(default = False)
	preview = ndb.BooleanProperty(default = False)
	last_modified = ndb.DateTimeProperty(required = True, auto_now = True)

class PageVersion(ndb.Model):
	name = ndb.StringProperty(required = True)
	published_version = ndb.IntegerProperty(default = 0)
	draft_version = ndb.IntegerProperty(default = 0)

def get_published_version(name):
	t = tournament.get_tournament()
	versions = memcache.get("%s/published_versions" % t.name)
	if not versions:
		q = PageVersion.query(ancestor = t.key)
		q = q.order(PageVersion.name)
		versions = { v.name: v.published_version for v in q }
		if versions:
			memcache.set("%s/published_versions" % t.name, versions, 60*60*24)
	if versions.has_key(name):
		return versions[name]
	return 0

def get_draft_version(name):
	t = tournament.get_tournament()
	versions = memcache.get("%s/draft_versions" % t.name)
	if not versions:
		q = PageVersion.query(ancestor = t.key)
		q = q.order(PageVersion.name)
		versions = { v.name: v.draft_version for v in q }
		if versions:
			memcache.set("%s/draft_versions" % t.name, versions, 60*60*24)
	if versions.has_key(name):
		return versions[name]
	return 0

def set_version(name, v, draft):
	t = tournament.get_tournament()
	q = PageVersion.query(ancestor = t.key)
	q = q.filter(PageVersion.name == name)
	pageversion = q.get()
	if not pageversion:
		pageversion = PageVersion(parent = t.key, name = name, published_version = 0 if draft else v, draft_version = v)
	else:
		if not draft:
			pageversion.published_version = v
		pageversion.draft_version = v
	pageversion.put()
	memcache.delete("%s/draft_versions" % t.name)
	memcache.delete("%s/published_versions" % t.name)

def detail_page_list():
	return ["home", "details", "raffle", "map", "sponsors", "sponsorships", "volunteer", "register", "tribute"]

def get_detail_page(name, draft):
	if not name in detail_page_list():
		return None
	t = tournament.get_tournament()
	v = get_draft_version(name) if draft else get_published_version(name)
	if v is None:
		v = 0
	q = DetailPage.query(ancestor = t.key)
	q = q.filter(DetailPage.name == name)
	q = q.filter(DetailPage.version == v)
	page = q.get()
	if not page:
		page = DetailPage(parent = t.key, name = name, version = v, title = name, content = "Sorry, no content yet.")
	return page
