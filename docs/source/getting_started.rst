###############
Getting Started
###############

Installation
============
* Stable Version from Pypi
    https://pypi.org has the latest stable package.

    For installing the package using pip, run :code:`pip install o365`

* Latest Development Version from Github
    Github has the latest development version, which may have more features but could be unstable.
    So **Use as own risk**

    For installing code from github, run :code:`pip install git+https://github.com/O365/python-o365.git`


OAuth Setup (Pre Requisite)
===========================
You will need to register your application at `Microsoft Apps <https://apps.dev.microsoft.com/>`_. Steps below

#. Login to https://apps.dev.microsoft.com/
#. Create an app, note your app id (**client_id**)
#. Generate a new password (**client_secret**) under **Application Secrets** section
#. Under the **Platform** section, add a new Web platform and set "https://outlook.office365.com/owa/" as the redirect URL
#. Under "Microsoft Graph Permissions" section, Add the below delegated permission (or based on what scopes you plan to use)
    #. email
    #. Mail.ReadWrite
    #. Mail.Send
    #. User.Read

#. Note the **client_id** and **client_secret** as they will be using for establishing the connection through the api


Basic Usage
===========

Work in progress
