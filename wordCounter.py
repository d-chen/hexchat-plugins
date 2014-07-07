__module_name__ = "User Word Counter"
__module_version__ = "1.0"
__module_description__ = "Records the times a user has said a word"

from collections import Counter
import cPickle as pickle
import csv
import datetime
import string
import os
import sys
import re

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

def load_stop_words(file_path):
    stop_list = []
    with open(file_path, 'rb') as file:
        reader = csv.reader(file, delimiter=",")
        for row in reader:
            stop_list += row
    return set(stop_list)

# setup and constants
COOLDOWN = 5
COOLDOWN_TIME = local_time()
FILE_PATH = hexchat.get_info("configdir") + "/wordfreq.pickle"
STOP_WORD_PATH = hexchat.get_info("configdir") + "/stop_words.csv"
STOP_WORDS = load_stop_words(STOP_WORD_PATH)
LOW_WIDTH_SPACE = u"\u200B" # insert into nicknames to avoid highlighting user extra times
REGEX = re.compile(r'[\s]+')

if os.path.isfile(FILE_PATH):
    word_count = pickle.load(open(FILE_PATH, "rb"))
else:
    word_count = {}

def on_cooldown():
    """ Return true if script has made a response recently """
    time_now = local_time()
    if COOLDOWN_TIME > time_now:
        return True
    else:
        return False

def cooldown_update():
    """ Update earliest time a new command can be called """
    time_now = local_time()
    COOLDOWN_TIME = time_now + datetime.timedelta(seconds=COOLDOWN)

def unload_cb(userdata):
    pickle.dump(word_count, open(FILE_PATH, "wb"))

def clearstop_cb(word, word_eol, userdata):
    for nick in word_count:
        for stop_word in STOP_WORDS:
            del word_count[nick][stop_word]
    print "Deleted stop words from word count dictionary"
    return hexchat.EAT_ALL

def break_nickname(nick):
    """ Insert zero-width spaces into name to avoid extra IRC highlights """
    new_nick = u""
    for c in nick:
        new_nick += c
        new_nick += LOW_WIDTH_SPACE
    return new_nick

def wc_update(data):
    """ Update count of words said by user """
    nick = data['nick']
    result = filter(lambda x: len(x.decode('utf-8')) > 2, REGEX.split(data['message']))
    freq = Counter(result)

    if nick not in word_count:
        word_count[nick] = Counter()

    for word in freq:
        if word.lower() in STOP_WORDS:
            continue
        elif word != " " and not word.startswith("!"):
            word_count[nick][word.lower()] += freq[word]

def user_top_words(nick):
    """ Return the top 10 words a user has said """
    if nick.lower() not in word_count:
        return

    top_words = word_count[nick.lower()].most_common(10)
    broken_nick = break_nickname(nick)

    report = broken_nick + "'s top words: "
    for word, count in top_words:
        partial = "'{0}' ({1}), ".format(word, count)
        report += partial
    hexchat.command("say " + report)

    cooldown_update()

def word_top_users(word):
    """ Return the top ?? users that have said word """
    if len(word) < 3:
        hexchat.command("say Words longer than 2 letters are recorded.")
        cooldown_update()
        return

    user_list = Counter()
    for nick in word_count:
        if word.lower() in word_count[nick]:
            user_list[nick] = word_count[nick][word.lower()]

    top_users = user_list.most_common(10)
    report = "Top users of '" + word.lower() + "': "
    for user, count in top_users:
        broken_nick = break_nickname(nick)
        partial = "{0} ({1}), ".format(broken_nick, count)
        report += partial
    hexchat.command("say " + report)

    cooldown_update()

def wc_print_usage():
    """ Print syntax for using !words commands """
    hexchat.command("say " + "Usage: !words topwords NAME / !words topusers WORD")
    cooldown_update()

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
    wc_update(data)
    if data['message'].startswith("!") and not on_cooldown():
        route(data)

def route(data):
    """ Handle command calls """
    cmd_data = data['message'].split()
    length = len(cmd_data)

    if cmd_data[0] != "!words":
        return
    elif length == 3:
        if cmd_data[1] == "topwords":
            user_top_words(cmd_data[2])
        if cmd_data[1] == "topusers":
            word_top_users(cmd_data[2])
        else:
            wc_print_usage()
    elif length == 4 and cmd_data[1] == "userfreq":
        #user_own_word_count(cmd_data[2], cmd_data[3])
        return
    else:
        wc_print_usage()


hexchat.hook_server('PRIVMSG', parse)
hexchat.hook_unload(unload_cb)
hexchat.hook_command("CLEARSTOP", clearstop_cb, help="/CLEARSTOP Removes stop words from the dictionary")

hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been loaded.")