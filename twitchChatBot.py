__module_name__ = "TwitchTV Chat Bot"
__module_version__ = "1.2"
__module_description__ = "Miscellaneous chat bot features"

import codecs
import datetime
import string
import sqlite3
import sys

import hexchat
import pytz
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

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

FB2K_NOW_PLAYING_FILE = 'E:\Pictures\Stream\currentsong/fb2k_nowPlaying_simple.txt'
YOUTUBE_NOW_PLAYING_FILE = 'E:\Pictures\Stream\currentsong/nowplaying_youtube_chat.txt'
PASS_FILE = "E:\Git/xchat-plugins/twitch_pass.txt"
COOLDOWN_PER_USER = 12
COOLDOWN_GENERAL = 10
BOT_LIST = ["kazukimouto", "nightbot", "brettbot", "rise_bot", "dj_jm09", "palebot"]
ADMIN_ACCESS = ["low_tier_bot", "saprol"] # debugging purposes
LOW_WIDTH_SPACE = u"\uFEFF" # insert into nicknames to avoid highlighting user extra times
now_playing_source = 'FB2K'
cooldown_time = local_time()
last_use = {}
time_fmt = "%H:%M %Z. %B %d, %Y"

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
    hexchat.command("say Local time in Vancouver: " + pst_dt.strftime(time_fmt))

def japan_time():
    """ Sends current time of Japan to chat """
    utc_dt = utc_time()

    jpn_tz = pytz.timezone('Japan')
    jpn_dt = jpn_tz.normalize(utc_dt.astimezone(jpn_tz))
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

    if nick.lower() in ADMIN_ACCESS:
        return False
    
    if cooldown_time > time_now:
        print "A command has been used too recently."
        return True
    elif nick not in last_use:
        flood_update(nick)
        return False
    elif last_use[nick] > time_now:
        print nick + " has used a command too recently."
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
    hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been unloaded.")

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
    global now_playing_source
    if now_playing_source == 'FB2K':
        now_playing_file = FB2K_NOW_PLAYING_FILE
    elif now_playing_source == 'YouTube':
        now_playing_file = YOUTUBE_NOW_PLAYING_FILE
        
    try:
        with open(now_playing_file, 'r') as file:
            title = file.read()
            hexchat.command('say [Saprol\'s {0}] {1}'.format(now_playing_source, title))
    except IOError as error:
        print 'ERROR: Could not read ' + now_playing_file

def set_now_playing_source(source):
    """ Change text file to read from for now_playing() """
    global now_playing_source
    if source.lower() == 'FB2K'.lower():
        now_playing_source = 'FB2K'
    elif source.lower() == 'YouTube'.lower():
        now_playing_source = 'YouTube'
    else:
        hexchat.command("say {0} is an invalid option for !sapmusic".format(source))
        return
        
    hexchat.command("say !sapmusic will now announce songs from Saprol's {0}".format(source))

def get_stream_info(channel):
    url = 'https://api.twitch.tv/kraken/streams/{0}'.format(channel[1:]) # channel starts with hash
    headers = {'accept': 'application/vnd.twitchtv.v3+json'}
    resp = requests.get(url, headers=headers)

    if not resp.status_code == 200:
        hexchat.command("say Twitch API is not currently available.")
        return
    return resp.json()

def is_stream_online(resp):
    if resp['stream']:
        return True
    else:
        return False
        
def get_channel_views(channel):
    resp = get_stream_info(channel)

    if is_stream_online(resp):
        viewers = resp['stream']['viewers']
        hexchat.command("say There are currently {0} viewers watching.".format(viewers))
    else:
        hexchat.command("say This stream is currently offline or Twitch API is down.")

def create_twitch_bookmark_title(channel, bookmark_name):
    title = bookmark_name.replace("!bookmark", "", 1).strip()
    if title:
        bookmark_title = title
    else:
        utc_dt = utc_time()
        pst_tz = pytz.timezone('Canada/Pacific')
        pst_dt = pst_tz.normalize(utc_dt.astimezone(pst_tz))
        bookmark_title = pst_dt.strftime(time_fmt)

    return bookmark_title

def create_twitch_bookmark(channel, bookmark_name, nick):
    """ No API feature -> Automate browser to create TwitchTV bookmark """
    resp = get_stream_info(channel)
    if not is_stream_online(resp):
        hexchat.command("say {user} -> Stream is not running.".format(user=nick))
        return

    hexchat.command("say {user} -> Attempting to create bookmark. Please wait.".format(user=nick))

    with open(PASS_FILE, 'r') as file:
        bot_password = file.read()

    bookmark_title = create_twitch_bookmark_title(channel, bookmark_name)

    driver = webdriver.PhantomJS(executable_path='E:\phantomjs-1.9.7-windows/phantomjs.exe')
    driver.set_window_size(1600, 900)
    wait = WebDriverWait(driver, 15)
    try:
        driver.get("http://www.twitch.tv/{0}".format(channel[1:]))
        # Login
        driver.find_element_by_xpath("//span[text()=\"Log In\"]").click()
        wait.until(lambda driver: driver.find_element_by_id("login_user_login"))
        driver.find_element_by_id("login_user_login").clear()
        driver.find_element_by_id("login_user_login").send_keys("low_tier_bot")
        driver.find_element_by_id("user[password]").clear()
        driver.find_element_by_id("user[password]").send_keys(bot_password)
        driver.find_element_by_xpath("(//button[contains(text(), 'Log In')])").click()

        # Create bookmark
        driver.find_element_by_xpath("//span[text()=\"Bookmark\"]").click()
        wait.until(lambda driver: driver.find_element_by_xpath("(//input[contains(@class, \"js-title\")])"))
        driver.find_element_by_xpath("(//input[contains(@class, \"js-title\")])").clear()
        driver.find_element_by_xpath("(//input[contains(@class, \"js-title\")])").send_keys(bookmark_title)
        driver.find_element_by_xpath("//button[@type='submit']").click()
        wait.until(lambda driver: driver.find_element_by_xpath("//input[contains(@value,\"twitch.tv/m/\")]"))
        bookmark_url = driver.find_element_by_xpath("//input[contains(@value,\"twitch.tv/m/\")]").get_attribute("value")
        hexchat.command("say {user} -> Bookmark \"{name}\" created: {url} | Bookmarks: {list}".format(name=bookmark_title, 
                                                                                                      url=bookmark_url,
                                                                                                      user=nick,
                                                                                                      list="http://www.twitch.tv/low_tier_bot/profile/bookmarks"))
    finally:
        driver.quit()
        hexchat.command("say {user} -> Unable to create bookmark \"{name}\".".format(name=bookmark_title,
                                                                                     user=nick))

def is_mod(nick):
    mod_list = hexchat.get_list("users")
    for i in mod_list:
        if i.nick.lower() == nick.lower() and i.prefix == "@":
            return True
    return False

def is_ignored(user):
    ignore_list = hexchat.get_list("ignore")
    for item in ignore_list:
        if user in item.mask:
            return True
    return False

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
    db_update(data)
    if is_ignored(data['nick']):
        return
    if data['nick'].lower() in ADMIN_ACCESS or not on_global_cooldown():
        route(data)

def route(data):
    """ Call commands if trigger present """
    command_data = data['message'].split()
    cmd = command_data[0].lower()
    length = len(command_data)
    
    if cmd == '!ltb':
        if not on_cooldown(data['nick']):
            hexchat.command("say " + data['nick'] + " -> Current active commands: !bookmark !viewers !seen !jptime !wctime !sapmusic")
                
    if cmd == '!seen':
        if on_cooldown(data['nick']):
            return
        elif length == 2:
            if command_data[1].lower() in BOT_LIST:
                hexchat.command("say " + data['nick'] + " -> No messing with other bots.")
                return
            seen(data['nick'], command_data[1])
        else:
            hexchat.command("say Usage: !seen NICKNAME")

    if cmd == "!wctime":
        if not on_cooldown(data['nick']):
            pacific_time()
            
    if cmd == '!jptime':
        if not on_cooldown(data['nick']):
            japan_time()

    if cmd == '!sapmusic':
        if length == 2 and data['nick'] in ADMIN_ACCESS:
            set_now_playing_source(command_data[1])
        if not on_cooldown(data['nick']):
            now_playing()
            
    if cmd == '!viewers':
        if not on_cooldown(data['nick']):
            get_channel_views(data['channel'])

    if cmd == "!bookmark":
        if not on_cooldown(data['nick']):
            if length == 1:
                hexchat.command("say LTB Bookmarks: http://www.twitch.tv/low_tier_bot/profile/bookmarks")
            elif length > 1 and is_mod(data['nick']):
                create_twitch_bookmark(data['channel'], data['message'], data['nick'])
            

hexchat.hook_unload(db_unload)
hexchat.hook_server('PRIVMSG', parse)
hexchat.hook_timer(120000, db_commit)

hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been loaded.")