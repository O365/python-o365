import sys
import getpass
from pyo365 import Connection, FluentInbox


def main():
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    authentication = (username, password)
    Connection.login(*authentication)
    inbox = FluentInbox()

    # If given arguments, treat them as folder_ids to use as parents
    if len(sys.argv) > 1:
        for folder_id in sys.argv[1:]:
            for folder in inbox.list_folders(parent_id=folder_id):
                print(folder['Id'], folder['DisplayName'])
    else:
        for folder in inbox.list_folders():
            print(folder['Id'], folder['DisplayName'])
    return 0


if __name__ == "__main__":
    sys.exit(main())
