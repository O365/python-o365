"""
A simple python library to interact with Microsoft Graph and Office 365 API
"""
import warnings

from .__version__ import __version__

from .account import Account


# allow Deprecation warnings to appear
warnings.simplefilter('always', DeprecationWarning)
