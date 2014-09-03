from datetime import tzinfo, timedelta, datetime

ZERO = timedelta(0)
HOUR = timedelta(hours=1)

class UTC(tzinfo):

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()

def first_sunday_on_or_after(dt):
	days_to_go = 6 - dt.weekday()
	if days_to_go:
		dt += timedelta(days_to_go)
	return dt

# In the US, since 2007, DST starts at 2am (standard time) on the second
# Sunday in March, which is the first Sunday on or after Mar 8.
DSTSTART_2007 = datetime(1, 3, 8, 2)
# and ends at 2am (DST time; 1am standard time) on the first Sunday of Nov.
DSTEND_2007 = datetime(1, 11, 1, 1)

class USTimeZone(tzinfo):

	def __init__(self, hours, reprname, stdname, dstname):
		self.stdoffset = timedelta(hours=hours)
		self.reprname = reprname
		self.stdname = stdname
		self.dstname = dstname

	def __repr__(self):
		return self.reprname

	def tzname(self, dt):
		if self.dst(dt):
			return self.dstname
		else:
			return self.stdname

	def utcoffset(self, dt):
		return self.stdoffset + self.dst(dt)

	def dst(self, dt):
		if dt is None or dt.tzinfo is None:
			return ZERO
		assert dt.tzinfo is self

		if 2006 < dt.year:
			dststart, dstend = DSTSTART_2007, DSTEND_2007
		else:
			return ZERO

		start = first_sunday_on_or_after(dststart.replace(year=dt.year))
		end = first_sunday_on_or_after(dstend.replace(year=dt.year))

		if start <= dt.replace(tzinfo=None) < end:
			return HOUR
		else:
			return ZERO

pacific = USTimeZone(-8, "Pacific",  "PST", "PDT")
