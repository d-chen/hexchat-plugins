__module_name__ = "TwitchTV Chat Bot"
__module_version__ = "1.0"
__module_description__ = "Miscellaneous chat bot features"

import codecs
import datetime
import string
import sqlite3
import sys

import hexchat
import pytz

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
COOLDOWN_PER_USER = 8
COOLDOWN_GENERAL = 6
BOT_LIST = ["kazukimouto", "nightbot", "brettbot", "rise_bot"]
LOW_WIDTH_SPACE = u"\uFEFF" # insert into nicknames to avoid highlighting user extra times
cooldown_time = local_time()
last_use = {}

def japan_time():
    """ Sends current time of Japan to chat """
    utc_dt = datetime.datetime.utcnow()
    utc_dt = utc_dt.replace(tzinfo=pytz.timezone('UTC'))

    jpn_tz = pytz.timezone('Japan')
    jpn_dt = jpn_tz.normalize(utc_dt.astimezone(jpn_tz))
    time_fmt = "%H:%M %Z. %B %d, %Y"
    hexchat.command("say Local time in Japan: " + jpn_dt.strftime(time_fmt))

def flood_update(nick):
    """ Update earliest time a new command can be called """
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
    if not on_global_cooldown():
        route(data)

def route(data):
    """ Call commands if trigger present """
    command_data = data['message'].split()
    length = len(command_data)
    
    if command_data[0] == '!sapmusic':
        if on_cooldown(data['nick']):
            return
        else:
            now_playing()

    if command_data[0] == '!seen':
        if on_cooldown(data['nick']):
            return
        elif length == 2:
            if command_data[1] in BOT_LIST:
                hexchat.command("say " + data['nick'] + " -> Quit that shit.")
                return
            seen(data['nick'], command_data[1])
        else:
            hexchat.command("say Usage: !seen <nickname>")

    if command_data[0] == '!jptime':
        if on_cooldown(data['nick']):
            return
        else:
            japan_time()


hexchat.hook_unload(db_unload)
hexchat.hook_server('PRIVMSG', parse)
hexchat.hook_timer(120000, db_commit)

hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been loaded.")