import json
from O365 import *

'''
Example of Master List
(Pre merged with colour details)
[
    {
        'id': '5a9a6aa8-b65f-4357-b1f9-60c6bf6330d8',
        'displayName': 'Red category',
        'color': {
            'colorid': 0,
            'outlookname': 'preset0',
            'rgb': '240,125,136',
            'hex': '#F07D88',
            'name': 'Red'
        }
    },
    {
        'id': '4b1c2495-54c9-4a5e-90a2-0ab0b31987d8',
        'displayName': 'Orange category',
        'color': {
            'colorid': 1,
            'outlookname': 'preset1',
            'rgb': '255,140,0',
            'hex': '#FF9509',
            'name': 'Orange'
        }
    }
]

'''

mycredentials = (your_application_idkey, your_endpoint_client_secret)
myscopes = ['basic', 'MailboxSettings.Read']
account = Account(mycredentials)

if not account.is_authenticated:  # will check if there is a token and has not expired
    # ask for a login
    print("not authed, login please")
    account.authenticate(scopes=myscopes)


#Init User Settings
usrsettings = account.settings()

#Output Master Categories
print(usrsettings.get_categories())


