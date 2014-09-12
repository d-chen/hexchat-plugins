__module_name__ = "TwitchTV Chat Bot"
__module_version__ = "1.1"
__module_description__ = "Miscellaneous chat bot features"

import codecs
import datetime
import string
import sqlite3
import sys

import hexchat
import pytz
import requests

# HACK: Set default encoding to UTF-8
if (sys.getdefaultencoding() != "utf-8"):
    oldout, olderr = sys.stdout, sys.stderr         # Backup stdout and stderr
    reload(sys)                                     # This call resets stdout and stderr
    sys.setdefaultencoding('utf-8')
    sys.stdout = codecs.getwriter('utf-8')(oldout)  # Set old stdout
    sys.stderr = codecs.getwriter('utf-8')(olderr)  # Set old stderr

def local_time():
    """ Return current time according to the Pacific time zone """
    loc_dt = datetime.datetime.now(pytz.timezone('US/Pacific'))
    return loc_dt

NOW_PLAYING_FILE = 'E:\Pictures\Stream\currentsong/fb2k_nowPlaying_simple.txt'
COOLDOWN_PER_USER = 12
COOLDOWN_GENERAL = 8
BOT_LIST = ["kazukimouto", "nightbot", "brettbot", "rise_bot", "dj_jm09", "palebot"]
COOLDOWN_IMMUNE = ["low_tier_bot", "saprol"] # debugging purposes
LOW_WIDTH_SPACE = u"\uFEFF" # insert into nicknames to avoid highlighting user extra times
cooldown_time = local_time()
last_use = {}

def utc_time():
    """ Return current time in UTC """
    utc_dt = datetime.datetime.utcnow()
    utc_dt = utc_dt.replace(tzinfo=pytz.timezone('UTC'))
    return utc_dt
    
def pacific_time():
    """ Sends current time of Pacific time zone to chat """
    utc_dt = utc_time()
    
    pst_tz = pytz.timezone('Canada/Pacific')
    pst_dt = pst_tz.normalize(utc_dt.astimezone(pst_tz))
    time_fmt = "%H:%M %Z. %B %d, %Y"
    hexchat.command("say Local time in Vancouver: " + pst_dt.strftime(time_fmt))

def japan_time():
    """ Sends current time of Japan to chat """
    utc_dt = utc_time()

    jpn_tz = pytz.timezone('Japan')
    jpn_dt = jpn_tz.normalize(utc_dt.astimezone(jpn_tz))
    time_fmt = "%H:%M %Z. %B %d, %Y"
    hexchat.command("say Local time in Japan: " + jpn_dt.strftime(time_fmt))

def flood_update(nick):
    """ Update earliest time a new command can be called """
    global cooldown_time
    time_now = local_time()
    cooldown_time = time_now + datetime.timedelta(seconds=COOLDOWN_GENERAL)
    last_use[nick] = time_now + datetime.timedelta(seconds=COOLDOWN_PER_USER)

def on_global_cooldown():
    """ Return true if script has made a response recently """
    time_now = local_time()
    if cooldown_time > time_now:
        return True
    else:
        return False

def on_cooldown(nick):
    """ Return true if a command has been used too recently """
    time_now = local_time()

    if nick.lower() in COOLDOWN_IMMUNE:
        return False
    
    if cooldown_time > time_now:
        print "Global cooldown is still up."
        return True

    if nick not in last_use:
        flood_update(nick)
        return False
    elif last_use[nick] > time_now:
        print nick + " has used a command too recently."
        return True
    elif cooldown_time > time_now:
        print "A command has been used too recently."
        return True
    else:
        flood_update(nick)
        return False

def break_nickname(nick):
    """ Insert zero-width spaces into name to avoid extra IRC highlights """
    new_nick = u""
    for c in nick:
        new_nick += c
        new_nick += LOW_WIDTH_SPACE
    return new_nick

# database setup
db_path = hexchat.get_info("configdir") + "/seen.db"
db_connection = sqlite3.connect(db_path)
db_cursor = db_connection.cursor()
db_cursor.execute("CREATE TABLE IF NOT EXISTS seen (nick TEXT UNIQUE, message TEXT)")

def db_commit(userdata):
    db_connection.commit()
    return 1 # keep hook_timer running

def db_unload(userdata):
    db_connection.commit()
    db_connection.close()

def db_update(data):
    """ Update the last time somebody was seen talking """
    time_now = local_time().strftime('%b %d, %Y at %H:%M %Z')

    msg = u'This user was last seen saying \'{msg}\' on {date}'.format(msg=data['message'], 
                                                                       date=time_now)

    sql_query = u"REPLACE INTO seen (nick, message) VALUES (?, ?)"
    db_cursor.execute(sql_query, (data['nick'], msg))

def seen(searcher, target):
    """ Report the last time somebody was seen talking """
    target_str = target.lower()
    sql_query = "SELECT message FROM seen WHERE nick = ?"
    db_cursor.execute(sql_query, (target_str,)) # need that comma to make 1-arg tuples
    row = db_cursor.fetchone()
    if row:
        hexchat.command("say {0} -> ".format(searcher) + row[0])
    else:
        hexchat.command("say Could not find records of " + target)

def now_playing():
    """ Announce current song playing, through generated .txt """
    try:
        with open(NOW_PLAYING_FILE, 'r') as file:
            title = file.read()
            hexchat.command('say [Saprol\'s FB2K]' + title)
    except IOError as error:
        print 'ERROR: Could not read ' + NOW_PLAYING_FILE

def get_channel_views(channel):
    url = 'https://api.twitch.tv/kraken/streams/{0}'.format(channel[1:]) # channel starts with hash
    headers = {'accept': 'application/vnd.twitchtv.v3+json'}
    resp = requests.get(url, headers=headers)
    
    if not resp.status_code == 200:
        hexchat.command("say Twitch API is not currently available.")
        return
        
    resp_json = resp.json()
    if resp_json['stream']:
        viewers = resp_json['stream']['viewers']
        hexchat.command("say There are currently {0} viewers in this channel.".format(viewers))
    else:
        hexchat.command("say This stream is currently offline.")

def parse(word, word_eol, userdata):
    """ Prepare messages for processing """
    str_data = word_eol[0].replace("!"," ", 1).split(None,4)    
    data = {
        "nick" : str_data[0].lstrip(":").lower().decode('ascii').encode('utf-8'),
        "host" : str_data[1].decode('ascii').encode('utf-8'),
        "type" : str_data[2].decode('ascii').encode('utf-8'),
        "channel" : str_data[3].decode('ascii').encode('utf-8'),
        "message" : str_data[4][1:].encode('utf-8')
        }
    if not data['message'].startswith("!"):
        db_update(data)
    if data['nick'].lower() in COOLDOWN_IMMUNE or not on_global_cooldown():
        route(data)

def route(data):
    """ Call commands if trigger present """
    command_data = data['message'].split()
    length = len(command_data)
    
    if command_data[0] == '!ltb':
        if not on_cooldown(data['nick']):
            hexchat.command("say " + data['nick'] + " -> Current active commands: !viewers !seen !jptime !wctime !sapmusic")
                
    if command_data[0] == '!seen':
        if on_cooldown(data['nick']):
            return
        elif length == 2:
            if command_data[1].lower() in BOT_LIST:
                hexchat.command("say " + data['nick'] + " -> No messing with other bots.")
                return
            seen(data['nick'], command_data[1])
        else:
            hexchat.command("say Usage: !seen NICKNAME")

    if command_data[0] == "!wctime":
        if not on_cooldown(data['nick']):
            pacific_time()
            
    if command_data[0] == '!jptime':
        if not on_cooldown(data['nick']):
            japan_time()

    if command_data[0] == '!sapmusic':
        if not on_cooldown(data['nick']):
            now_playing()
            
    if command_data[0] == '!viewers':
        if not on_cooldown(data['nick']):
            get_channel_views(data['channel'])
            


hexchat.hook_unload(db_unload)
hexchat.hook_server('PRIVMSG', parse)
hexchat.hook_timer(120000, db_commit)

hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been loaded.")