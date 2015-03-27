import hexchat
import pytz
import requests

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

def is_valid_resp(resp):
    if resp.status_code == 200:
        return True
    return False

def get_stream_info(channel):
    url = 'https://api.twitch.tv/kraken/streams/{0}'.format(channel)
    headers = {'accept': 'application/vnd.twitchtv.v3+json'}
    resp = requests.get(url, headers=headers)
    return resp

def get_host_info(channel):
    url = 'http://chatdepot.twitch.tv/rooms/{0}/host_target'.format(channel)
    headers = {'accept': 'application/json'}
    resp = requests.get(url, headers=headers)
    return resp

def is_stream_online(resp):
    if resp['stream']:
        return True
    else:
        return False
        
def get_channel_views(channel, nick):
    resp = get_stream_info(channel)
    resp_json = resp.json()
    if not is_valid_resp(resp):
        return "{0} -> Twitch API is not currently available.".format(nick)
    
    if is_stream_online(resp_json):
        viewers = resp_json['stream']['viewers']
        return "{1} -> Currently {0} viewers are watching.".format(viewers, nick)
    else:
        return "{0} -> This stream is currently offline.".format(nick)

def get_hosted_channel(channel, nick):
    resp = get_host_info(channel)
    resp_json = resp.json()
    if not is_valid_resp(resp):
        return "{0} -> Twitch API is not currently available.".format(nick)
    
    hosted_chan = resp_json['host_target']
    if hosted_chan:
        host_resp = get_stream_info(hosted_chan)
        host_info = host_resp.json()

        if not is_valid_resp(host_resp):
            return "{0} -> Twitch API is not currently available.".format(nick)

        if not is_stream_online(host_info):
            return "{1} -> Currently hosting {0}. Stream is offline.".format(hosted_chan, nick)

        name = host_info['stream']['channel']['display_name']
        status = host_info['stream']['channel']['status']
        game = host_info['stream']['channel']['game']
        return "{3} -> Currently hosting {0} playing {1} | {2}".format(
            name, game, status, nick)
    return ""


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

def create_twitch_bookmark(channel, bookmark_name, nick, password_file):
    """ No API feature -> Automate browser to create TwitchTV bookmark """
    resp = get_stream_info(channel)
    if not is_stream_online(resp.json()):
        hexchat.command("say {user} -> Stream is not running.".format(user=nick))
        return

    hexchat.command("say {user} -> Attempting to create bookmark. Please wait.".format(user=nick))
    driver = webdriver.Chrome(executable_path="E:\chromedriver.exe")
    driver.set_window_size(1280, 720)
    wait = WebDriverWait(driver, 15)    

    with open(password_file, 'r') as file:
        bot_password = file.read()

    bookmark_title = create_twitch_bookmark_title(channel, bookmark_name)
    username_field = "login_user_login"
    password_field = "password"
    bookmark_xpath = "//span[text()=\"Bookmark\"]"
    login_xpath = "//span[text()=\"Log In\"]"
    title_xpath = "//input[contains(@class, \"js-title\")]"
    result_xpath = "//input[contains(@value,\"twitch.tv/m/\")]"
    submit_xpath = '//button[@type="submit"]'
    created_bookmark = False
    
    try:
        driver.get("http://www.twitch.tv/{0}".format(channel[1:]))
        # Login
        driver.find_element_by_xpath(login_xpath).click()
        wait.until(lambda driver: driver.find_element_by_id(username_field))
        driver.find_element_by_id(username_field).clear()
        driver.find_element_by_id(username_field).send_keys("low_tier_bot")
        driver.find_element_by_id(password_field).clear()
        driver.find_element_by_id(password_field).send_keys(bot_password)
        driver.find_element_by_xpath("//button[contains(text(), 'Log In')]").click()
        wait.until(lambda driver: len(driver.find_elements_by_xpath(login_xpath)) == 0)

        # Create bookmark
        wait.until(lambda driver: driver.find_element_by_xpath(bookmark_xpath))
        driver.find_element_by_xpath(bookmark_xpath).click()
        wait.until(lambda driver: driver.find_element_by_xpath(title_xpath))
        title_form = driver.find_element_by_xpath(title_xpath)
        title_form.clear()
        title_form.send_keys(bookmark_title)
        driver.find_element_by_xpath(submit_xpath).click()
        wait.until(lambda driver: driver.find_element_by_xpath(result_xpath))
        bookmark_url = driver.find_element_by_xpath(result_xpath).get_attribute("value")
        created_bookmark = True
        hexchat.command("say {user} -> Bookmark \"{name}\" created: {url} | {list}".format(name=bookmark_title, 
                                                                                           url=bookmark_url,
                                                                                           user=nick,
                                                                                           list="http://www.twitch.tv/low_tier_bot/profile/bookmarks"))
    finally:
        driver.quit()
        
    if not created_bookmark:
        hexchat.command("say {user} -> Unable to create bookmark \"{name}\".".format(name=bookmark_title,
                                                                                     user=nick))