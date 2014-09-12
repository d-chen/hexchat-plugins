__module_name__ = "User Word Counter"
__module_version__ = "2.0 Beta"
__module_description__ = "Records the times a user has said a word"

from collections import Counter
import cPickle as pickle
import csv
import datetime
import string
import os
import sqlite3
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
COOLDOWN = 10
DIR_PATH = hexchat.get_info("configdir")
DB_PATH = DIR_PATH + "/WordCount.db"
STOP_WORD_PATH = DIR_PATH + "/stop_words.csv"
STOP_WORDS = load_stop_words(STOP_WORD_PATH)
LOW_WIDTH_SPACE = u"\uFEFF" # insert into nicknames to avoid highlighting user extra times
REGEX = re.compile(r'\W+')
HTTP_RE = re.compile(r'https?:\/\/.*[\r\n]*') # re.sub() remove URLs
CMD_RE = re.compile(r'\!\w+\s') # remove other chat commands

cooldown_time = local_time()
db_connection = sqlite3.connect(DB_PATH)
db_cursor = db_connection.cursor()
db_cursor.execute(("CREATE TABLE IF NOT EXISTS WordCount (user TEXT, "
                                                         "word TEXT, "
                                                         "count INTEGER, "
                                                         "UNIQUE(user, word) ON CONFLICT REPLACE)"))

def on_cooldown():
    """ Return true if script has made a response recently """
    time_now = local_time()
    if cooldown_time > time_now:
        return True
    else:
        return False

def cooldown_update():
    """ Update earliest time a new command can be called """
    global cooldown_time
    time_now = local_time()
    cooldown_time = time_now + datetime.timedelta(seconds=COOLDOWN)

def unload_cb(userdata):
    """ Commit and close database when unloading """
    db_connection.commit()
    db_connection.close()
    hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been unloaded.")

def deleteuser_cb(word, word_eol, userdata):
    """ Delete user from dictionary """
    nick = word_eol[1]
    sql_query = ("DELETE FROM WordCount "
                 "WHERE user=?")
    db_cursor.execute(sql_query, (nick,))
    db_connection.commit()
    print "Deleted {0} from word count dictionary".format(nick)
    return hexchat.EAT_ALL

def break_nickname(nick):
    """ Insert zero-width spaces into name to avoid extra IRC highlights """
    new_nick = u""
    length = len(nick)
    new_nick = nick[0] + LOW_WIDTH_SPACE + nick[1:(length - 1)] + LOW_WIDTH_SPACE + nick[(length - 1):]
    return new_nick

def wc_update(data):
    """ Update count of words said by user """
    msg_no_cmds = CMD_RE.sub(' ', data['message'].lower())
    msg_no_urls = HTTP_RE.sub('', msg_no_cmds)
    result = filter(lambda x: len(x.decode('utf-8')) > 2, REGEX.split(msg_no_urls))
    freq = Counter(result)

    for word in freq:
        if word in STOP_WORDS or word.startswith("!") or word.startswith("http"):
            continue
        elif word != " " and freq[word] <= 3 and len(word.decode('utf-8')) <= 16:
            # likely bot abuse / spam if exceeding these limits for normal chat
            wc_update_sql(data['nick'], word.decode('utf-8'), freq[word])
    db_connection.commit()
            
def wc_update_sql(user, word, count): 
    # sqlite3 does not support UPSERT, instead SELECT for existing field
    sql_query = (u"REPLACE INTO WordCount (user, word, count) "
                 "VALUES (?, "
                         "?, "
                         "COALESCE(((SELECT count FROM WordCount WHERE user=? AND word=?)+?), ?)"
                         ")")
    db_cursor.execute(sql_query, (user, word, user, word, count, count))

def report_list(items, break_text):
    """ Generate message based on a list of items """
    report = ""
    for row in items:
        text = row[0]
        count = row[1]
        if break_text:
            text = break_nickname(text)
        partial = "{0} ({1}), ".format(text, count)
        report += partial
    return report

def user_top_words(caller, nick):
    """ Return the top words a user has said """
    sql_query = ("SELECT word, count "
                 "FROM WordCount "
                 "WHERE user=? "
                 "ORDER BY count DESC "
                 "LIMIT 8")
    db_cursor.execute(sql_query, (nick,))
    results = db_cursor.fetchall()

    msg_command = "say {0} -> This user's top words: ".format(caller) + report_list(results, False)
    hexchat.command(msg_command)
    cooldown_update()

def word_top_users(word):
    """ Return the top ?? users that have said word """
    if len(word) <= 3:
        hexchat.command("say Words longer than 3 letters are recorded.")
        cooldown_update()
        return

    if word in STOP_WORDS or word.startswith("!"):
        hexchat.command("say '" + word + "' is excluded for being too common or part of another chat command.")
        cooldown_update()
        return

    sql_query = ("SELECT user, count "
                 "FROM WordCount "
                 "WHERE word=? "
                 "ORDER BY count DESC "
                 "LIMIT 8")
    db_cursor.execute(sql_query, (word.decode('utf-8'),))
    results = db_cursor.fetchall()

    msg_command = "say Top users of '{0}': ".format(word.lower()) + report_list(results, True)
    hexchat.command(msg_command)
    cooldown_update()

def most_spoken_words():
    """ Return the top 10 words said by all users """
    sql_query = ("SELECT word, SUM(count) "
                 "FROM WordCount "
                 "GROUP BY word "
                 "ORDER BY SUM(count) DESC "
                 "LIMIT 10")
    db_cursor.execute(sql_query)
    results = db_cursor.fetchall()
    
    msg_command = "say Top words recorded: " + report_list(results, False)
    hexchat.command(msg_command)
    cooldown_update()

def wc_print_usage():
    """ Print syntax for using !words commands """
    hexchat.command("say " + "Examples: !words user [USERNAME] / !words word [WORD] / !words everyone")
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
    if not data['message'].startswith("!"):
       wc_update(data)
    if data['message'].startswith("!") and not on_cooldown():
       route(data) 

def route(data):
    """ Handle command calls """
    cmd_data = data['message'].split()
    length = len(cmd_data)
    
    if not data['nick'] == 'saprol':
        return
    
    if cmd_data[0] != "!words":
        return
    elif cmd_data[1] == "everyone":
            most_spoken_words()
    elif length >= 3:
        if cmd_data[1] == "user":
            user_top_words(data['nick'], cmd_data[2])
        elif cmd_data[1] == "word":
            word_top_users(cmd_data[2])
        else:
            wc_print_usage()
    else:
        wc_print_usage()


hexchat.hook_server('PRIVMSG', parse)
hexchat.hook_unload(unload_cb)
hexchat.hook_command("wc_delete", deleteuser_cb, help="/wc_delete [name] Removes user from database")

hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been loaded.")