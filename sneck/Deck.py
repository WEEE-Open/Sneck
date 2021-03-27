import requests
import json
import os
import logging

from typing import Optional
from requests.auth import HTTPBasicAuth
from datetime import datetime as dt, timezone as tz


class DeckUser:
    def __init__(self, data: dict):
        # Internal user identifiers and types
        self.__pkey = data['primaryKey']
        self.__uuid = data['uid']
        self.__type = data['type']

        self.name = data['displayname']

    def __str__(self) -> str:
        # Name contains username, so returning only name is not ambiguous
        return self.name


class DeckAcl:
    def __init__(self, data: dict, users: dict):
        # Internal identifier and type of the ACL
        self.__id = data['id']
        self.__type = data['type']
        self.__permissions = {'edit': data['permissionEdit'],
                              'share': data['permissionShare'],
                              'manage': data['permissionManage']}

        # ACLs are different wrt to user management than cards or every other object that contains DeckUsers
        # While the list of users obtained with the "/boards?details=1" API call contains all effective users
        # of the board, that is people that can create and modify content inside the board, ACLs can also contain
        # groups. Groups get unrolled within the previous API call into the single participants, therefore ACL
        # principals are not guaranteed to be in the DeckBoard.users dictionary. We remedy this by adding those
        # principals to that dictionary in the event they are not found at ACL creation time.
        if data['participant']['primaryKey'] not in users:
            users[data['participant']['primaryKey']] = DeckUser(data['participant'])

        self.principal = users[data['participant']['primaryKey']]

        # If the user is the owner of the entity
        self.owner = data['owner']

    def can_edit(self) -> bool:
        return self.__permissions['edit']

    def can_share(self) -> bool:
        return self.__permissions['share']

    def can_manage(self) -> bool:
        return self.__permissions['manage']

    def __str__(self) -> str:
        return str(self.principal) + f' [{",".join(k for k,v in self.__permissions.items() if v == True)}]'


class DeckLabel:
    def __init__(self, label: dict):
        # Internal identifiers for the label
        self.__id = label['id']
        self.__tag = label['ETag']

        # Not sure about what this is? We'll store it but keep it private and not expose it for now...
        self.__card_id = label['cardId']

        self.title = label['title']
        self.color = label['color']
        self.last_edited_date = dt.fromtimestamp(label['lastModified']).astimezone(tz.utc)

    def __str__(self) -> str:
        return f'{self.title} (#{self.color.upper()})'


class DeckCard:
    def __init__(self, card: dict, labels: dict[DeckLabel], users: dict[DeckUser]):
        # Internal identifiers for the card
        self.__id = card['id']
        self.__tag = card['ETag']

        self.title = card['title']
        self.description = card['description'].strip()
        self.labels = [labels[label['ETag']] for label in card['labels']]
        self.type = card['type']
        self.attachments = [] if card['attachments'] is None else card['attachments']
        self.order = card['order']
        self.archived = card['archived']
        self.unread_comments = card['commentsUnread']
        self.overdue = card['overdue']

        # Timestamps
        self.creation_time = dt.fromtimestamp(card['createdAt']).astimezone(tz.utc)
        self.last_edited_time = dt.fromtimestamp(card['lastModified']).astimezone(tz.utc)
        self.deletion_time = dt.fromtimestamp(card['deletedAt']).astimezone(tz.utc)

        # TODO: Fix this obscenity without breaking PEP8, somehow
        self.card_due_time = None if card['duedate'] is None else \
            dt.strptime(card['duedate'], '%Y-%m-%dT%H:%M:%S%z').astimezone(tz.utc)

        # Users
        self.assignees = [users[assignee['participant']['primaryKey']] for assignee in card['assignedUsers']]
        self.creator = users[card['owner']['primaryKey']]

        # NOTE: This is just the UUID/PK of the user not the entire structure
        # TODO: Figure out whether this is a UUID or PK and in case it's the PK just get the DeckUser from dict
        self.last_editor = card['lastEditor']

    def get_shortened_description(self, max: int) -> str:
        result = " ".join([line for line in self.description.splitlines()])
        maxlen = max if max > 0 else len(result)
        return result[0:min(maxlen, len(result))].strip() + ('...' if maxlen < len(result) else '')

    def __str__(self) -> str:
        result = f'CARD "{self.title}":\n'
        result += f'    Description: "{self.get_shortened_description(50)}"\n'
        result += f'    Labels: {", ".join(label.title for label in self.labels)}\n'
        result += f'    Attachments: {"None" if len(self.attachments) == 0 else len(self.attachments)}\n'
        result += f'    Archived: {"Yes" if self.archived else "No"}\n'
        result += f'    Due date: {self.card_due_time}\n'
        result += f'    Creator: {self.creator}\n'

        if self.last_editor is not None:
            result += f'    Last edit at {self.last_edited_time} by {self.last_editor}\n'

        if len(self.assignees) > 0:
            result += '    ASSIGNEES:\n        '
            result += '\n        '.join([str(assignee) for assignee in self.assignees])

        return result


class DeckStack:
    def __init__(self, stack: dict, labels: dict[DeckLabel], users: dict[DeckUser]):
        # Internal identifiers for the board
        self.__id = stack['id']
        self.__tag = stack['ETag']

        self.last_edited_time = stack['lastModified']
        self.order = stack['order']
        self.title = stack['title']

        self.cards = [] if 'cards' not in stack else [DeckCard(card, labels, users) for card in stack['cards']]

    def __str__(self) -> str:
        result = f'STACK "{self.title}"\n'

        for card in self.cards:
            result += ('\n'.join(['    ' + line for line in str(card).splitlines()])) + '\n'

        return result

    def get_next_event(self) -> Optional[DeckCard]:
        result = None
        for card in self.cards:
            if card and card.card_due_time and (not result or (result and result.card_due_time > card.card_due_time)) \
                    and card.card_due_time >= dt.now(tz.utc):
                result = card

        return result


class DeckBoard:
    def __init__(self, board: dict, stacks: list):
        # Internal identifiers for the board
        self.__id = board['id']
        self.__tag = board['ETag']

        # Internal data to be exposed through accessors
        self.__permissions = board['permissions']  # Permissions for this user (r,w,share,manage)
        self.__notification_settings = board['settings']['notify-due']  # Notification settings for board
        self.__synchronize = board['settings']['calendar']  # Whether the board synchronizes with CalDAV

        self.title = board['title']
        self.color = board['color']
        self.labels = {label['ETag']: DeckLabel(label) for label in board['labels']}

        # Users and access control
        self.users = {user['primaryKey']: DeckUser(user) for user in board['users']}
        self.owner = self.users[board['owner']['primaryKey']]
        self.acl = [DeckAcl(acl, self.users) for acl in board['acl']]

        self.archived = board['archived']  # Board archived by current user
        self.shared = board['shared']  # Board shared to the current user (not owned by current user)

        # Timestamps for deletion and last edit. Deletion timestamp is 0 if the board has not been deleted

        # TODO: Fix this obscenity without breaking PEP8, somehow
        self.deletion_time = None if board['deletedAt'] == 0 else \
            dt.fromtimestamp(board['deletedAt']).astimezone(tz.utc)
        self.last_edited_time = None if board['lastModified'] == 0 else \
            dt.fromtimestamp(board['lastModified']).astimezone(tz.utc)

        self.stacks = [DeckStack(stack, self.labels, self.users) for stack in stacks]  # Non-empty stacks of the board

    def __str__(self):
        result = ''

        result += f'BOARD "{self.title}"\n'
        result += f'    Color: #{self.color.upper()}\n'
        result += f'    Archived: {self.archived}\n'
        result += f'    Shared to current user: {"No" if self.shared == 0 else "Yes"}\n'
        result += f'    Deleted: {"No" if self.deletion_time is None else f"Yes, at {self.deletion_time}"}\n'
        result += f'    Owner: {self.owner}\n'
        result += f'    Last modification at {self.last_edited_time}\n'

        if len(self.labels) > 0:
            result += f'    LABELS:\n'
            for label in self.labels.values():
                result += ('\n'.join(['        ' + line for line in str(label).splitlines()])) + '\n'

        if len(self.users) > 0:
            result += f'    USERS:\n'
            for user in self.users.values():
                result += ('\n'.join(['        ' + line for line in str(user).splitlines()])) + '\n'

        if len(self.acl) > 0:
            result += f'    ACL:\n'
            for acl in self.acl:
                result += ('\n'.join(['        ' + line for line in str(acl).splitlines()])) + '\n'

        result += '\n'.join(['    ' + line for stack in self.stacks for line in str(stack).splitlines()])

        return result

    def get_next_event(self) -> Optional[DeckCard]:
        result = None
        for stack in self.stacks:
            card = stack.get_next_event()
            if card and (not result or (result and result.card_due_time > card.card_due_time)) \
                    and card.card_due_time >= dt.now(tz.utc):
                result = card

        return result

    def can_read(self):
        return self.__permissions['PERMISSION_READ']

    def can_edit(self):
        return self.__permissions['PERMISSION_READ']

    def can_manage(self):
        return self.__permissions['PERMISSION_READ']

    def can_share(self):
        return self.__permissions['PERMISSION_READ']

    def deleted(self):
        return self.deletion_time is not None


class Deck:
    def __init__(self, domain: str, username: str, password: str, secure: bool):
        self.__api_base = f'{"https" if secure else "http"}://{domain}/index.php/apps/deck/api/v1.0/'
        self.__username = username
        self.__password = password

        self.next_event = None
        self.boards = {}
        self.users = {}

        self.download()

    def __str__(self):
        return '\n\n'.join([str(board) for board in self.boards.values()])

    def __api_request(self, api_bindpost: str) -> json:
        logging.debug(f'Making request {self.__api_base + api_bindpost}...')
        response = requests.get(self.__api_base + api_bindpost,
                                headers={'OCS-APIRequest': 'true', 'Content-Type': 'application/json'},
                                auth=HTTPBasicAuth(self.__username, self.__password))

        if not response.ok:
            logging.error(f'Request failed [Return code: {response.status_code}]!')
            logging.error(f'Unable to download deck content from API {self.__api_base + api_bindpost}')

            return None

        return response.text

    def download(self):
        d = json.JSONDecoder()

        boards = d.decode(self.__api_request('boards?details=1'))
        self.boards = {b['ETag']: DeckBoard(b, d.decode(self.__api_request(f'boards/{b["id"]}/stacks')))
                       for b in boards if b['deletedAt'] == 0} # and b['title'] != 'Personal'}

        self.next_event = self.get_next_event()

    def get_next_event(self) -> Optional[DeckCard]:
        result = None
        for board in self.boards.values():
            card = board.get_next_event()
            if card and (not result or (result and result.card_due_time > card.card_due_time)) \
                    and card.card_due_time >= dt.now(tz.utc):
                result = card

        return result


# Test basic program functionality
if __name__ == '__main__':
    hostname = os.environ.get("OC_DECK_HOST")
    username = os.environ.get('OC_DECK_USER')
    password = os.environ.get('OC_DECK_PASS')
    security = os.environ.get('OC_USE_HTTPS') == 'True'

    deck = Deck(hostname, username, password, security)
    print(deck)
