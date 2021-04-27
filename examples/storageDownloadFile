#!/usr/bin/python3

# To generate an Office365 token:

# python3
# from O365 import Account
# account = Account(credentials=('yourregisteredappname', 'yoursecret')) 
# account.authenticate(scopes=['files.read', 'user.read', 'offline_access'])

# It will return a URL, go to this in a browser, accept the permissions, then paste in the URL you are redirected to
# YOU MAY HAVE TO SWITCH TO THE 'OLD' VIEW TO DO THIS!

import pandas as pd
from O365 import Account

# Generated on the app registration portal
registered_app_name='yourregisteredappname'
registered_app_secret='yoursecret'

# File to download, and location to download to
dl_path='/path/to/download'
f_name='myfile.xlsx'

print("Connecting to O365")
account = Account(credentials=(registered_app_name, registered_app_secret), scopes=['files.read', 'user.read', 'offline_access'])

storage = account.storage()  # here we get the storage instance that handles all the storage options.

# get the default drive
my_drive = storage.get_default_drive()

print("Searching for {}...".format(f_name))
files = my_drive.search(f_name, limit=1)
if files:
    numberDoc = files[0]
    print("... copying to local machine")
    operation = numberDoc.download(to_path=dl_path)
else:
    print("File not found!")
    exit()

print("Reading sheet to dataframe")
df = pd.read_excel('{}/{}'.format(dl_path, f_name))

with pd.option_context('display.max_rows', None, 'display.max_columns', None):
    print(df)
