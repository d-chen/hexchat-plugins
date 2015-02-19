__module_name__ = "User Word Counter"
__module_version__ = "2.0"
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
    
def find_log_tab():
    """ Create separate tab for debugging messages """
    context = hexchat.find_context(channel=LOG_CONTEXT_NAME)
    if context == None:
        newtofront = hexchat.get_prefs('gui_tab_newtofront')
        
        hexchat.command('set -quiet gui_tab_newtofront 0')
        hexchat.command('newserver -noconnect {0}'.format(LOG_CONTEXT_NAME))
        hexchat.command('set -quiet gui_tab_newtofront {}'.format(newtofront))
        return hexchat.find_context(channel=LOG_CONTEXT_NAME)
    else:
        return context

# setup and constants
COOLDOWN = 12
MAX_CHAR_LENGTH = 16
DIR_PATH = hexchat.get_info("configdir")
DB_PATH = DIR_PATH + "/WordCount.db"
STOP_WORD_PATH = DIR_PATH + "/stop_words.csv"
STOP_WORDS = load_stop_words(STOP_WORD_PATH)
LOG_CONTEXT_NAME = ":wordcount:"
LOG_CONTEXT = hexchat.find_context(LOG_CONTEXT_NAME)
LOW_WIDTH_SPACE = u"\uFEFF" # insert into nicknames to avoid highlighting user extra times
UNI_RE = re.compile(r'[^\W\d_]+') # match groups of unicode letters
HTTP_RE = re.compile(r'https?:\/\/.*[\r\n]*') # re.sub() remove URLs
CMD_RE = re.compile(r'\!\w+\s') # remove other chat commands

cooldown_time = local_time()
log_context = find_log_tab()
db_connection = sqlite3.connect(DB_PATH)
db_cursor = db_connection.cursor()
db_cursor.execute(("CREATE TABLE IF NOT EXISTS WordCount (user TEXT, "
                                                         "word TEXT, "
                                                         "count INTEGER, "
                                                         "UNIQUE(user, word) ON CONFLICT REPLACE)"))
db_cursor.execute(("CREATE TABLE IF NOT EXISTS EveryUser (word TEXT UNIQUE, count INTEGER)"))
db_cursor.execute(("CREATE INDEX IF NOT EXISTS idx_UserTop ON WordCount(user, word)"))
db_cursor.execute(("CREATE INDEX IF NOT EXISTS idx_WordTop ON WordCount(word, count)"))


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

def delete_user_cb(word, word_eol, userdata):
    """ Delete user from dictionary """
    nick = word_eol[1]
    sql_query = ("DELETE FROM WordCount "
                 "WHERE user=?")
    db_cursor.execute(sql_query, (nick,))
    db_connection.commit()
    print "Deleted {0} from WC database".format(nick)
    return hexchat.EAT_ALL

def delete_entry_cb(word, word_eol, userdata):
    """ Delete specific database entry """
    nick = word[1]
    word = word[2]
    sql_query = ("DELETE FROM WordCount "
                 "WHERE user=? AND word=?")
    db_cursor.execute(sql_query, (nick, word))
    db_connection.commit()
    print "Deleted {0}'s count of '{1}' from WC database".format(nick, word)
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
    result = filter(lambda x: len(x.decode('utf-8')) > 2, UNI_RE.findall(msg_no_urls))
    freq = Counter(result)
    user = data['nick']
    log_context = find_log_tab()

    for word in freq:
        if word in STOP_WORDS or word.startswith("!") or word.startswith("http"):
            continue
        elif freq[word] > 2:
            log_wc_update("Discard", freq[word], user, "Spam", word)
        elif len(word.decode('utf-8')) > MAX_CHAR_LENGTH:
            log_wc_update("Discard", freq[word], user, "Too long", word)
        elif word != " ":
            log_wc_update("Log", freq[word], user, "", word)
            wc_update_sql(data['nick'], word.decode('utf-8'), freq[word])
    db_connection.commit()

def log_wc_update(action, count, user, reason, word):
    """ Print to screen the results of wc_update """
    log_context = find_log_tab()
    color = ["\0030", "\0032", "\0037", "\0034"]

    if action == "Log":
        reason = "Count ={0} {1}".format(color[3], count)

    log = u"{c0}{act}{c1} {wrd}{c0} from{c2} {usr}{c0}. {rsn}".format(c0=color[0],
                                                                      c1=color[1],
                                                                      c2=color[2],
                                                                      act=action,
                                                                      usr=user,
                                                                      rsn=reason,
                                                                      wrd=word)
    log_context.prnt(log)
            
def wc_update_sql(user, word, count): 
    # sqlite3 does not support UPSERT, instead SELECT for existing field
    sql_query = (u"REPLACE INTO WordCount (user, word, count) "
                 "VALUES (?, "
                         "?, "
                         "COALESCE(((SELECT count FROM WordCount WHERE user=? AND word=?)+?), ?)"
                         ")")
    db_cursor.execute(sql_query, (user, word, user, word, count, count))
    # different table for faster aggregate data
    sql_query = (u"REPLACE INTO EveryUser (word, count) "
                 "VALUES (?, "
                 "COALESCE(((SELECT count FROM EveryUser WHERE word=?)+?), ?)"
                 ")")
    db_cursor.execute(sql_query, (word, word, count, count))

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
    db_cursor.execute(sql_query, (nick.lower(),))
    results = db_cursor.fetchall()

    msg = "say {0} -> This user's top words: ".format(caller) + report_list(results, False)
    hexchat.command(msg)
    cooldown_update()

def word_top_users(caller, word):
    """ Return the top ?? users that have said word """

    if len(word) < 3 or len(word) > MAX_CHAR_LENGTH:
        hexchat.command("say {0} -> Words of length 3 to {1} are recorded.".format(caller, MAX_CHAR_LENGTH))
        cooldown_update()
        return

    if word in STOP_WORDS or word.startswith("!"):
        msg = "say {0} -> '{1}' is excluded for being too common or another command.".format(caller, word)
        hexchat.command(msg)
        cooldown_update()
        return

    if not word.isalpha():
        msg = "say {0} -> Numbers and punctuation are not included in records.".format(caller)
        hexchat.command(msg)
        cooldown_update()
        return

    sql_query = ("SELECT user, count "
                 "FROM WordCount "
                 "WHERE word=? "
                 "ORDER BY count DESC "
                 "LIMIT 8")
    db_cursor.execute(sql_query, (word.decode('utf-8').lower(),))
    results = db_cursor.fetchall()

    results_str = report_list(results, True)
    msg = "say {0} -> Top users of '{1}': {2}".format(caller, word.lower(), results_str)
    hexchat.command(msg)
    cooldown_update()

def most_spoken_words(caller):
    """ Return the top 10 words said by all users """
    sql_query = ("SELECT word, count "
                 "FROM EveryUser "
                 "ORDER BY count DESC "
                 "LIMIT 10")
    db_cursor.execute(sql_query)
    results = db_cursor.fetchall()
    
    msg = "say {0} -> Top words recorded: {1}".format(caller) + report_list(results, False)
    hexchat.command(msg)
    cooldown_update()

def wc_print_usage(caller):
    """ Print syntax for using !words commands """
    msg = "say {0} -> Usage: !words user [USERNAME] / !words word [WORD] / !words everyone".format(caller)
    hexchat.command(msg)
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
    if is_ignored(data['nick']):
       return 
    if not data['message'].startswith("!"):
       wc_update(data)
    if data['message'].startswith("!") and not on_cooldown():
       route(data)

def is_ignored(user):
    ignore_list = hexchat.get_list("ignore")
    for item in ignore_list:
        if user in item.mask:
            return True
    return False

def route(data):
    """ Handle command calls """
    cmd_data = data['message'].split()
    length = len(cmd_data)
    
    if cmd_data[0] != "!words":
        return
    elif length >= 2 and cmd_data[1] == "everyone":
            most_spoken_words(data['nick'])
    elif length >= 3:
        if cmd_data[1] == "user":
            user_top_words(data['nick'], cmd_data[2])
        elif cmd_data[1] == "word":
            word_top_users(data['nick'], cmd_data[2])
        else:
            wc_print_usage(data['nick'])
    else:
        wc_print_usage(data['nick'])


hexchat.hook_server('PRIVMSG', parse)
hexchat.hook_unload(unload_cb)
hexchat.hook_command("wc_delete_user", delete_user_cb, help="/wc_delete_user [name] Removes user from database")
hexchat.hook_command("wc_delete_entry", delete_entry_cb, help="/wc_delete_entry [name] [word] Removes entry from database")

hexchat.prnt(__module_name__ + " v" + __module_version__ + " has been loaded.")