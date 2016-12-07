import json
from O365 import *

'''
Example of Master List
(Extracted from the full output from service data json,
['owaUserConfig']['MasterCategoryList'][''MasterList])


{
    "MasterList": [{
            "Name": "Red category",
            "Color": 0
        },
        {
            "Name": "Orange category",
            "Color": 1
        }
    ]
}

'''


#Load existing json and parse
with open('o365mastercategorylist.json') as fp:
    json_obj = json.load(fp)

officecategory = Category(json_obj)


#Get information by searching by Name
print 'Colorid(16):', officecategory.get_colorid_fromname('Orange category')

