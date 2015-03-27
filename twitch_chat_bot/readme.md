##Twitch Chat Bot
HexChat plugin that provides additional TwitchTV chat features in response to user input.

#### Plugin Requirements:
* **PYTZ**:        [http://pytz.sourceforge.net/](http://pytz.sourceforge.net/)
* **Requests**:    [http://docs.python-requests.org/en/latest/](http://docs.python-requests.org/en/latest/)
* **Selenium WebDriver**: [https://pypi.python.org/pypi/selenium](https://pypi.python.org/pypi/selenium)

#### Main Features:
* Ignores excessive input from users to avoid TwitchTV ban for spam
* **!seen [user]**: Returns the last line this user has said
* **!viewers**: Returns the current number of users watching this TwitchTV stream
* **!bookmark [title]**: Automates creation of TwitchTV bookmark with given title
* **!wctime**: Returns local time for North America's west coast (PST/PDT)
* **!ectime**: Returns local time for North America's east coast (EST/EDT)
* **!jptime**: Returns local time for Japan (JST)
* **!status**: Used alongside Nightbot's **!status** to inform users when hosting another channel