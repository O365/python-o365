import sys
import getpass
from pyo365 import Connection, FluentInbox


def main():
    if len(sys.argv) == 1:
        sys.stderr.write("Usage: %s BY VALUE\n" % sys.argv[0])
        return 1

    username = input("Username: ")
    password = getpass.getpass("Password: ")
    authentication = (username, password)
    Connection.login(*authentication)
    inbox = FluentInbox()

    print(inbox.get_folder(by=sys.argv[1], value=sys.argv[2]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
