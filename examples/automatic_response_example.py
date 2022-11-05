from O365 import Account

client_id = ''  # Your client_id
client_secret = ''  # Your client_secret, create an (id, secret) at https://apps.dev.microsoft.com

print("Connecting to O365")
account = Account(credentials=(client_id, client_secret), auth_flow_type='authorization')
if account.authenticate(scopes=['basic', 'MailboxSettings.ReadWrite']):
   print('Authenticated!')
mailbox = account.mailbox()  # here we get the storage instance that handles all the storage options.
success = mailbox.set_automatic_reply("Internal response", "External response", "2022-11-05T08:00:00.0000000", "2022-12-09T16:00:00.00000000", 'Europe/Berlin')

