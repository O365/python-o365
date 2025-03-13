########
Overview
########

**O365 - Microsoft Graph API made easy**

.. important::

   With version 2.1 old access tokens will not work, and the library will require a new authentication flow to get new access and refresh tokens.

This project aims to make interacting with Microsoft Graph easy to do in a Pythonic way. Access to Email, Calendar, Contacts, OneDrive, etc. Are easy to do in a way that feel easy and straight forward to beginners and feels just right to seasoned python programmer.

The project is currently developed and maintained by `alejcas <https://github.com/alejcas/>`_.

Core developers
---------------
* `Alejcas <https://github.com/alejcas/>`_
* `Toben Archer <https://github.com/Narcolapser/>`_
* `Geethanadh <https://github.com/GeethanadhP/>`_

We are always open to new pull requests!

Rebuilding HTML Docs
--------------------
* Install ``sphinx`` python library:

.. code-block:: console 

   pip install sphinx

* Run the shell script ``build_docs.sh``, or copy the command from the file when using on Windows

Quick example
-------------
Here is a simple example showing how to send an email using python-o365. 
Create a Python file and add the following code:

.. code-block:: python

   from O365 import Account

   credentials = ('client_id', 'client_secret')
   account = Account(credentials)

   m = account.new_message()
   m.to.add('to_example@example.com')
   m.subject = 'Testing!'
   m.body = "George Best quote: I've stopped drinking, but only while I'm asleep."
   m.send()


Why choose O365?
----------------
* Almost Full Support for MsGraph Rest Api.
* Full OAuth support with automatic handling of refresh tokens.
* Automatic handling between local datetimes and server datetimes. Work with your local datetime and let this library do the rest.
* Change between different resource with ease: access shared mailboxes, other users resources, SharePoint resources, etc.
* Pagination support through a custom iterator that handles future requests automatically. Request Infinite items!
* A query helper to help you build custom OData queries (filter, order, select and search).
* Modular ApiComponents can be created and built to achieve further functionality.

----

This project was also a learning resource for us. This is a list of not so common python idioms used in this project:

* New unpacking technics: ``def method(argument, *, with_name=None, **other_params)``:
* Enums: from enum import Enum
* Factory paradigm
* Package organization
* Timezone conversion and timezone aware datetimes
* Etc. (see the code!)
* What follows is kind of a wiki...