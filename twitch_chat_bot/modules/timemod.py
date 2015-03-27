import datetime
import pytz

time_fmt = "%H:%M %Z. %B %d, %Y"

def utc_time():
    """ Return current time in UTC """
    utc_dt = datetime.datetime.utcnow()
    utc_dt = utc_dt.replace(tzinfo=pytz.timezone('UTC'))
    return utc_dt

def local_time():
    """ Return current time according to the Pacific time zone """
    loc_dt = datetime.datetime.now(pytz.timezone('US/Pacific'))
    return loc_dt
    
def pacific_time():
    utc_dt = utc_time()
    
    pst_tz = pytz.timezone('Canada/Pacific')
    pst_dt = pst_tz.normalize(utc_dt.astimezone(pst_tz))
    return "Local time in Vancouver: " + pst_dt.strftime(time_fmt)

def eastern_time():
	utc_dt = utc_time()

	est_tz = pytz.timezone('Canada/Eastern')
	est_dt = est_tz.normalize(utc_dt.astimezone(est_tz))
	return "Local time in New York: " + est_dt.strftime(time_fmt)

def japan_time():
    utc_dt = utc_time()

    jpn_tz = pytz.timezone('Japan')
    jpn_dt = jpn_tz.normalize(utc_dt.astimezone(jpn_tz))
    return "Local time in Japan: " + jpn_dt.strftime(time_fmt)