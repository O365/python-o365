# python-o365 - Office365 for you server

The objective O365 is to make it easy to make utilities that are to be run against an Office 365 account. If you wanted to script sending an email it could be as simple as:

```python
from O365 import Message
authenticiation = ('YourAccount@office365.com','YourPassword')
m = Message(auth=authenticiation)
m.setRecipients('reciving@office365.com')
m.setSubject('I made an email script.')
m.setBody('Talk to the computer, cause the human does not want to hear it any more.')
m.sendMessage()
```


#### To the King!
