import getpass
from O365 import Connection, FluentInbox


def main():
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    authentication = (username, password)
    Connection.login(*authentication)
    inbox = FluentInbox()

    # set inbox as current folder to use as parent, self.folder attribute
    inbox.from_folder("Inbox")
    
    # reset current folder as subfolder
    inbox.from_folder("Subfolder", parent_id=inbox.folder["Id"])
    for msg in inbox.search("Subject:Urgent").fetch_first(10):
        print(msg.getSubject())
    
    # reset current folder as a child folder of Subfolder
    inbox.from_folder("Sub_subfolder", parent_id=inbox.folder["Id"])
    for msg in inbox.fetech_first(10):
        print(msg.getSubject())
    
    return 0


if __name__ == "__main__":
    main()