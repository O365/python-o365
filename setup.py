#!/usr/bin/env python

from distutils.core import setup

CLASSIFIERS = [
	'Development Status :: 4 - Beta',
	'Intended Audience :: Developers',
	'License :: OSI Approved :: Apache Software License',
	'Topic :: Office/Business :: Office Suites',
	'Topic :: Software Development :: Libraries'
]
long_desc = '''When I started making this library I was looking for something that would provide a simple interface to an office365 mailbox. I was creating a system that would allow people send an email to our printer without having to require they install drivers or be inside the office firewall (important for students). As I found working with the office API to be fairly easy, I quickly built up solid general use library for working with office 365. 

The objective here is to make it easy to make utilities that are to be run against an office 365 account. for example, the code for sending an email is:


from O365 import Message

authenticiation = ('YourAccount@office365.com','YourPassword')

m = Message(auth=authenticiation)

m.setRecipients('reciving@office365.com')

m.setSubject('I made an email script.')

m.setBody('Talk to the computer, cause the human does not want to hear it any more.')

m.sendMessage()


That's it. making and sending emails and events is now very simple and straight forward. I've used it for emailing the printer and creating a overview of our car booking system. simple, easy, but still in development. Any suggestions or advice are quite welcome at the projects github page:
https://github.com/Narcolapser/python-o365'''

setup(name='O365',
	version='0.9.8',
	description='Python library for working with Microsoft Office 365',
	long_description=long_desc,
	author='Toben Archer',
	author_email='sandslash+O365@gmail.com',
	maintainer='Toben Archer',
	maintainer_email='sandslash+O365@gmail.com',
	url='https://github.com/Narcolapser/python-o365',
	packages=['O365'],
	install_requires=['requests'],
	license='Apache 2.0',
	classifiers=CLASSIFIERS
	)


#so I don't have to keep looking it up: python setup.py sdist upload -r pypi
