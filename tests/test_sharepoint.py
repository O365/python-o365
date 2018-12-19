from O365 import Account
from O365 import Message

credentials = ("789592f7-5cf3-43ca-8e47-241a4e17989a", "fhleJPOY6572)(??ntsXPD6")
acc = Account(credentials)
#result = acc.authenticate(scopes=['basic', 'Sites.Read.All'])
sp = acc.sharepoint()
root = sp.get_root_site()
print(root.display_name)
print(root.get_lists()[0].get_items())
root = sp.get_site("myappsdomain.sharepoint.com" ,"/sites/dev1")
print(root.get_lists())
print(root.display_name)
lst = root.get_list_by_name("Documents")
print(lst.display_name)
items = lst.get_items()
print(root.get_lists()[0].get_items())
