import pytest
import time
from O365 import Account
from O365.utils import FileSystemTokenBackend
from tests import config

TEST_SCOPES = ['offline_access', 'Channel.ReadBasic.All',
               'ChannelMessage.Read.All', 'ChannelMessage.Send',
               'Chat.ReadWrite', 'ChatMember.ReadWrite', 'Team.ReadBasic.All',
               'User.Read', 'Presence.Read', 'Channel.Create',
               'TeamsAppInstallation.ReadForTeam']


@pytest.fixture(scope='module')
def teams():
    token_backend = FileSystemTokenBackend('.//')
    credentials = (config.CLIENT_ID, config.CLIENT_SECRET)
    account = Account(credentials, scopes=TEST_SCOPES,
                      token_backend=token_backend)
    yield account.teams()


class TestTeams:

    def test_get_my_presence(self, teams):
        my_presence = teams.get_my_presence()
        assert my_presence
        assert my_presence.object_id

    def test_get_my_teams(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            assert team.main_resource == '/teams/{}'.format(team.object_id)

    def test_get_my_chats(self, teams):
        my_chats = teams.get_my_chats()
        assert my_chats
        for chat in my_chats:
            assert chat.main_resource == '/chats/{}'.format(chat.object_id)

    def test_get_channels(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = teams.get_channels(team.object_id)
            assert channels
            for channel in channels:
                assert channel.main_resource == '/channels/{}'.format(
                    channel.object_id)

    def test_create_channel(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        team_id = my_teams[0].object_id
        display_name = 'My Test Channel {}'.format(time.time())
        description = 'My Description'
        channel = teams.create_channel(team_id, display_name,
                                       description)
        assert channel
        assert channel.display_name == display_name
        assert channel.description == description
        assert channel.main_resource == '/channels/{}'.format(
            channel.object_id)

    def test_get_channel(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = teams.get_channels(team.object_id)
            assert channels
            for channel in channels:
                this_channel = teams.get_channel(team.object_id,
                                                 channel.object_id)
                assert this_channel.main_resource == '/channels/{}'.format(
                    this_channel.object_id)

    def test_get_apps_in_team(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            apps = teams.get_apps_in_team(team.object_id)
            assert apps
            for app in apps:
                assert app.object_id


class TestTeam:

    def test_get_channels(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = team.get_channels()
            assert channels
            for channel in channels:
                assert channel.main_resource == '/teams/{}/channels/{}'.format(
                    team.object_id, channel.object_id)

    def test_get_channel(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = team.get_channels()
            assert channels
            for channel in channels:
                this_channel = team.get_channel(channel.object_id)
                assert this_channel.main_resource == '/teams/{}/channels/{}'.format(
                    team.object_id, this_channel.object_id)


class TestChannel:

    def test_get_messages(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = team.get_channels()
            assert channels
            for channel in channels:
                messages = channel.get_messages()
                for message in messages:
                    assert message.main_resource == '/teams/{}/channels/{}/messages/{}'.format(
                        team.object_id, channel.object_id, message.object_id)

    def test_get_message(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = team.get_channels()
            assert channels
            for channel in channels:
                messages = channel.get_messages()
                for message in messages:
                    this_message = channel.get_message(message.object_id)
                    assert this_message.main_resource == '/teams/{}/channels/{}/messages/{}'.format(
                        team.object_id, channel.object_id,
                        this_message.object_id)

    def test_send_message(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        channels = my_teams[0].get_channels()
        assert channels

        content_text = 'My Test Text'
        message_text = channels[0].send_message(content_text)
        assert message_text.content == content_text
        assert message_text.content_type == 'text'

        content_html = '<h1>My Test HTML</h1>'
        message_html = channels[0].send_message(content_html,
                                                content_type='html')
        assert message_html.content == content_html
        assert message_html.content_type == 'html'


class TestChat:

    def test_get_messages(self, teams):
        my_chats = teams.get_my_chats()
        assert my_chats
        for chat in my_chats:
            messages = chat.get_messages()
            assert messages
            for message in messages:
                assert message.main_resource == '/chats/{}/messages/{}'.format(
                    chat.object_id, message.object_id)

    def test_get_message(self, teams):
        my_chats = teams.get_my_chats()
        assert my_chats
        for chat in my_chats:
            messages = chat.get_messages()
            assert messages
            for message in messages:
                this_message = chat.get_message(message.object_id)
                assert this_message.main_resource == '/chats/{}/messages/{}'.format(
                    chat.object_id, this_message.object_id)

    def test_send_message(self, teams):
        my_chats = teams.get_my_chats()
        assert my_chats
        chat = my_chats[0]

        content_text = 'My Test Text'
        message_text = chat.send_message(content_text)
        assert message_text.content == content_text
        assert message_text.content_type == 'text'

        content_html = '<h1>My Test HTML</h1>'
        message_html = chat.send_message(content_html, content_type='html')
        assert message_html.content == content_html
        assert message_html.content_type == 'html'

    def test_get_members(self, teams):
        my_chats = teams.get_my_chats()
        assert my_chats
        for chat in my_chats:
            members = chat.get_members()
            assert members
            for member in members:
                assert member.main_resource == '/chats/{}/members/{}'.format(
                    chat.object_id, member.object_id)

    def test_get_member(self, teams):
        my_chats = teams.get_my_chats()
        assert my_chats
        for chat in my_chats:
            members = chat.get_members()
            assert members
            for member in members:
                this_member = chat.get_member(member.object_id)
                assert this_member.main_resource == '/chats/{}/members/{}'.format(
                    chat.object_id, this_member.object_id)


class TestChannelMessage:

    def test_get_replies(self, teams):
        count = 0
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = team.get_channels()
            assert channels
            for channel in channels:
                messages = channel.get_messages()
                for message in messages:
                    replies = message.get_replies()

                    for reply in replies:
                        count += 1
                        assert reply.main_resource == '/teams/{}/channels/{}/messages/{}/replies/{}'.format(
                            team.object_id, channel.object_id,
                            message.object_id, reply.object_id)
        assert count

    def test_get_reply(self, teams):
        count = 0
        my_teams = teams.get_my_teams()
        assert my_teams
        for team in my_teams:
            channels = team.get_channels()
            assert channels
            for channel in channels:
                messages = channel.get_messages()
                for message in messages:
                    replies = message.get_replies()

                    for reply in replies:
                        count += 1
                        this_reply = message.get_reply(reply.object_id)
                        assert this_reply.main_resource == '/teams/{}/channels/{}/messages/{}/replies/{}'.format(
                            team.object_id, channel.object_id,
                            message.object_id, this_reply.object_id)
        assert count


    def test_send_reply(self, teams):
        my_teams = teams.get_my_teams()
        assert my_teams
        channels = my_teams[0].get_channels()
        assert channels
        messages = channels[0].get_messages()
        assert messages

        message = None
        for _ in messages:
            message = _
            break

        content_text = 'My Test Text'
        reply_text = message.send_reply(content_text)
        assert reply_text.content == content_text
        assert reply_text.content_type == 'text'

        content_html = '<h1>My Test HTML</h1>'
        reply_html = message.send_reply(content_html,
                                                content_type='html')
        assert reply_html.content == content_html
        assert reply_html.content_type == 'html'
