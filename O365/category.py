import json

class Category(object):
    '''
    Category reads the Master Category List using in email, contact, Calendar items on office365.
    At the moment this uses a "static" manually aquirted list

    Methods:
        getName - Returns the name of the contact.
        getContactId - returns the GUID that identifies the contact on office365
        getId - synonym of getContactId
        getContacts - kicks off the process of fetching contacts.
    '''

    def __init__(self, jsonin=None):
        '''
        Loads the informtion
        '''
        self.jsonraw = jsonin

        if self.jsonraw:
            self.mastercategorylist = self.jsonraw['MasterList']
        else:
            self.mastercategorylist = []


    def get_colorid_fromname(self, categoryname):
        '''Finds the Color ID from the category name'''
        for i, c in enumerate(self.mastercategorylist):
            if c['Name'] == categoryname:
                return c['Color']
