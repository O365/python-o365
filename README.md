[![Downloads](https://pepy.tech/badge/O365)](https://pepy.tech/project/O365)
[![PyPI](https://img.shields.io/pypi/v/O365.svg)](https://pypi.python.org/pypi/O365)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/O365.svg)](https://pypi.python.org/pypi/O365/)

# O365 - Microsoft Graph and Office 365 API made easy

This project aims to make interacting with Microsoft Graph and Office 365 easy to do in a Pythonic way.
Access to Email, Calendar, Contacts, OneDrive, etc. Are easy to do in a way that feel easy and straight forward to beginners and feels just right to seasoned python programmer.

The project is currently developed and maintained by [alejcas](https://github.com/alejcas).

#### Core developers
- [Alejcas](https://github.com/alejcas)
- [Toben Archer](https://github.com/Narcolapser)
- [Geethanadh](https://github.com/GeethanadhP)

**We are always open to new pull requests!**

## Detailed docs and api reference on [O365 Docs site](https://o365.github.io/python-o365/latest/index.html)

### Quick example on sending a message:

```python
from O365 import Account

credentials = ('client_id', 'client_secret')

account = Account(credentials)
m = account.new_message()
m.to.add('to_example@example.com')
m.subject = 'Testing!'
m.body = "George Best quote: I've stopped drinking, but only while I'm asleep."
m.send()
```


### Why choose O365?
- Almost Full Support for MsGraph and Office 365 Rest Api.
- Good Abstraction layer between each Api. Change the api (Graph vs Office365) and don't worry about the api internal implementation.
- Full oauth support with automatic handling of refresh tokens.
- Automatic handling between local datetimes and server datetimes. Work with your local datetime and let this library do the rest.
- Change between different resource with ease: access shared mailboxes, other users resources, SharePoint resources, etc.
- Pagination support through a custom iterator that handles future requests automatically. Request Infinite items!
- A query helper to help you build custom OData queries (filter, order, select and search).
- Modular ApiComponents can be created and built to achieve further functionality.

___

This project was also a learning resource for us. This is a list of not so common python idioms used in this project:
- New unpacking technics: `def method(argument, *, with_name=None, **other_params):`
- Enums: `from enum import Enum`
- Factory paradigm
- Package organization
- Timezone conversion and timezone aware datetimes
- Etc. ([see the code!](https://github.com/O365/python-o365/tree/master/O365))
