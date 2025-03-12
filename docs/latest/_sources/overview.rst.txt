########
Overview
########

**O365 - Microsoft Graph API made easy**

This project aims to make interacting with Microsoft Graph and Office 365 easy to do in a Pythonic way. Access to Email, Calendar, Contacts, OneDrive, etc. Are easy to do in a way that feel easy and straight forward to beginners and feels just right to seasoned python programmer.

The project is currently developed and maintained by `alejcas <https://github.com/alejcas/>`_.

Core developers
---------------
* `Alejcas <https://github.com/alejcas/>`_
* `Toben Archer <https://github.com/Narcolapser/>`_
* `Geethanadh <https://github.com/GeethanadhP/>`_

We are always open to new pull requests!

Rebuilding HTML Docs
--------------------
* Install ``sphinx`` python library::

   pip install sphinx

* Run the shell script ``build_docs.sh``, or copy the command from the file when using on windows

Why choose O365?
----------------
* Almost Full Support for MsGraph Rest Api.
* Good Abstraction layer between each Api. Change the api (Graph vs Office365) and don't worry about the api internal implementation.
* Full oauth support with automatic handling of refresh tokens.
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