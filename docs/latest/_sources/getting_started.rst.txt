###############
Getting Started
###############

Installation
============
Stable Version (PyPI)
---------------------
The latest stable package is hosted on `PyPI <https://pypi.org>`_. 

To install using pip, run:

.. code-block:: console

   pip install o365

Latest Development Version (GitHub)
-----------------------------------
The latest development version is available on `GitHub <https://github.com/O365/python-o365>`_. 
This version may include new features but could be unstable. **Use at your own risk**.

To install from GitHub, run:

.. code-block:: console

   pip install git+https://github.com/O365/python-o365.git


OAuth Setup (Prerequisite)
==========================
Before you can use python-o365, you must register your application in the 
`Microsoft Entra Admin Center <https://entra.microsoft.com/>`_. Follow the steps below:

1. **Log in to the Microsoft Entra Admin Center**

   - Visit https://entra.microsoft.com/ and sign in.

2. **Create a new application and note its App (client) ID**
   
   - In the left navigation bar, select **Applications** > **App registrations**.
   - Click **+ New registration**.
   - Provide a **Name** for the application and keep all defaults.
   - From the **Overview** of your new application, copy the (client_id) **Application (client) ID** for later reference.

3. **Generate a new password (client_secret)**
   
   - In the **Overview** window, select **Certificates & secrets**.
   - Click **New client secret**.
   - In the **Add a client secret** window, provide a Description and Expiration, then click **Add**.
   - Save the (client_secret) **Value** for later reference.

4. **Add redirect URIs**
   
   - In the **Overview** window, click **Add a redirect URI**.
   - Click **+ Add a platform**, then select **Web**.
   - Add ``https://login.microsoftonline.com/common/oauth2/nativeclient`` as the redirect URI.
   - Click **Save**.

5. **Add required permissions**
   
   - In the left navigation bar, select **API permissions**.
   - Click **+ Add a permission**.
   - Under **Microsoft Graph**, select **Delegated permissions**.
   - Add the delegated permissions you plan to use (for example):
     
     - Mail.Read
     - Mail.ReadWrite
     - Mail.Send
     - User.Read
     - User.ReadBasic.All
     - offline_access

   - Click **Add permissions**.


Basic Usage
===========
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
