#This file is a mock the requests library used for unit testing.

def delete(url,**params):
	pass

def get(url,**params):
	print url,params

def patch(url,**params):
	pass

def post(url,**params):
	pass

def put(url,**params):
	pass

def head(url,**params):
	pass

def options(url,**params):
	pass




#############################################################################################################
#######################################     RESPONSES    ####################################################
#############################################################################################################
class response:

	def __init__(self,url,**params):
		'''
		translates the the url and params given to the correct response for this test.
		'''

		if url == 'https://outlook.office365.com/EWS/OData/Me/Calendars':
			self.resp = schedule_resp

	def json(self):
		return self.resp


schedule_resp = '''{
   u'value':[
      {
         u'Name':u'Calendar',
         u'Color':u'Auto',
         u'@odata.id':         u"https://outlook.office365.com/EWS/OData/Users('test@unit.org')/Calendars('bigolguid=')",
         u'ChangeKey':u'littleguid=',
         u'Id':u'bigolguid=',
         u'@odata.etag':u'W/"littleguid="'
      },
      {
         u'Name':u'dat other cal',
         u'Color':u'Auto',
         u'@odata.id':         u"https://outlook.office365.com/EWS/OData/Users('test@unit.org')/Calendars('bigolguid2=')",
         u'ChangeKey':u'littleguid2=',
         u'Id':u'bigolguid2=',
         u'@odata.etag':u'W/"littleguid2="'
      }
   ],
   u'@odata.context':   u'https://outlook.office365.com/EWS/OData/$metadata#Me/Calendars'
}

'''
