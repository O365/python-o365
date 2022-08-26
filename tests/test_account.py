import pytest
from O365 import Account
from .config import Config
from O365.utils import EnvTokenBackend
import logging
log = logging.getLogger(__name__)

class TestAccount:

    @pytest.mark.parametrize("pop, key_to_pop", [
        (False, ""),
        (True, "scopes"),
        (True, "password"),
        (True, "tenant_id"),
        (True, "username"),
        (True, "auth_flow_type"),
    ])
    def test_authentication(self, pop, key_to_pop):
        """
        Test the new auth flow type "password"
        """
        kwargs = {
            "scopes" : ["basic"],
            "tenant_id" : Config.TENANT_ID,
            "username" : Config.EMAIL,
            "password" : Config.PASSWORD,
            "auth_flow_type" : 'password'
        }

        if pop:
            kwargs.pop(key_to_pop)

        # ValueError: When using the "credentials" or "password" auth_flow the "tenant_id" must be set
        if "tenant_id" in key_to_pop:
            with pytest.raises(ValueError):
                account = Account((Config.CLIENT_ID),**kwargs)

        # ValueError: auth_flow_type is needed
        if "auth_flow_type" in key_to_pop:
            with pytest.raises(ValueError):
                account = Account((Config.CLIENT_ID),**kwargs)

        if key_to_pop not in ("tenant_id", "auth_flow_type"):
            account = Account((Config.CLIENT_ID),**kwargs)
            # instantiate an account with "offline_access" (scopes="basic" is a default scope that includes "offline_access")
            # will give the possibility to use a refresh_token
            if not pop:
                account.authenticate()
                assert account.is_authenticated
                assert account.con.refresh_token()

            # instantiate an account without scopes -> no refresh_token
            if "scopes" in key_to_pop:
                account.authenticate()
                assert account.is_authenticated
                assert not account.con.refresh_token()

            # Cannot account authenticate without password or username
            if key_to_pop in ("username", "password"):
                assert not account.authenticate()


    @pytest.mark.parametrize("token", [
        "authenticate",
        "load",
        "delete",
    ])
    def test_auth_with_environment_variable_token_storage(self, token):
        """
        Test the authentication with the new token storage system.
        we will use EnvTokenBackend(BaseTokenBackend)
        default environment variable name is "O365TOKEN", initialize the class with another token_env_name to change it
        """
        env_token = EnvTokenBackend()
        kwargs = {
            "scopes": ["basic"],
            "tenant_id": Config.TENANT_ID,
            "username": Config.EMAIL,
            "password": Config.PASSWORD,
            "auth_flow_type": 'password',
            "token_backend": env_token
        }

        if token in ("authenticate", "load"):

            # if "load" the account (so the connection) will be initialized with a valid token loaded from environment variable
            # this can work only if there is an already valid token stored
            kwargs["token_backend"].token = env_token.load_token() if token == "load" else None
            account = Account((Config.CLIENT_ID), **kwargs)
            # if "authenticate" token will be requested to Microsoft server and stored in environmental variable
            account.authenticate() if token == "authenticate" else None

            assert account.is_authenticated
            assert account.con.refresh_token()
            assert account.con.token_backend.check_token()

        else:
            # The authentication fails after loading a None token.
            env_token.delete_token()
            kwargs["token_backend"].token = env_token.load_token()
            account = Account((Config.CLIENT_ID), **kwargs)

            assert not account.is_authenticated
            assert not account.con.token_backend.check_token()