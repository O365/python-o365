import sys
import getpass
from O365 import Connection, FluentInbox


def main():
    if len(sys.argv) == 1:
        sys.stderr.write("Usage: %s 'subject to search for'\n" % sys.argv[0])
        return 1

    username = input("Username: ")
    password = getpass.getpass("Password: ")
    authentication = (username, password)
    Connection.login(*authentication)
    inbox = FluentInbox()

    trash_folder = inbox.get_folder(by='DisplayName', value='Trash')

    for message in inbox.search("Subject:%s" % sys.argv[1]).fetch(count=1):
        print(message.moveToFolder(trash_folder['Id']))

    return 0


if __name__ == "__main__":
    sys.exit(main())
