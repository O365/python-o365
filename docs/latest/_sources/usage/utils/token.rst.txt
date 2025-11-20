Token
=====

When initiating the account connection you may wish to store the token for ongoing usage, removing the need to re-authenticate every time. There are a variety of storage mechanisms available which are shown in the detailed api.

FileSystemTokenBackend
----------------------
To store the token in your local file system, you can use the ``FileSystemTokenBackend``. This takes a path and a file name as parameters.

For example:

.. code-block:: python

    from O365 import Account, FileSystemTokenBackend

    token_backend = FileSystemTokenBackend(token_path=token_path, token_filename=token_filename)

    account = Account(credentials=('my_client_id', 'my_client_secret'), token_backend=token_backend)

The methods are similar for the other token backends.

You can also pass in a cryptography manager to the token backend so encrypt the token in the store, and to decrypt on retrieval. The cryptography manager must support the ``encrypt`` and ``decrypt`` methods.

.. code-block:: python

    from O365 import Account, FileSystemTokenBackend
    from xxx import CryptoManager

    key = "my really secret key"
    mycryptomanager = CryptoManager(key)

    token_backend = FileSystemTokenBackend(token_path=token_path, token_filename=token_filename, cryptography_manager=mycryptomanager)

    account = Account(credentials=('my_client_id', 'my_client_secret'), token_backend=token_backend)