import requests
import json
import os
import logging

from typing import Optional
from requests.auth import HTTPBasicAuth
from datetime import datetime as dt, timezone as tz


class DeckAPI:
    def __init__(self, username: str, password: str, hostname: str, secure: bool):
        self.__api_base = f'{"https" if secure else "http"}://{hostname}/index.php/apps/deck/api/v1.0/'
        self.__username = username
        self.__password = password
        self.__decoder = json.decoder.JSONDecoder()

    def request(self, binding: str) -> [list, dict]:
        logging.debug(f'Making request {self.__api_base + binding}...')
        response = requests.get(self.__api_base + binding,
                                headers={'OCS-APIRequest': 'true', 'Content-Type': 'application/json'},
                                auth=HTTPBasicAuth(self.__username, self.__password))

        # TODO: Actually handle something?
        if not response.ok:
            logging.error(f'Request failed [Return code: {response.status_code}]!')
            logging.error(f'Unable to download deck content from API {self.__api_base + binding}')

            return None
        print(response.text)
        return self.__decoder.decode(response.text)


class DeckUser:
    def __init__(self, data: dict):
        # Internal user identifiers and types
        self.__pkey = data['primaryKey']
        self.__uuid = data['uid']
        self.__type = data['type']

        self.__name = data['displayname']

    def __str__(self) -> str:
        # Name contains username, so returning only name is not ambiguous
        return self.__name

    def __repr__(self) -> str:
        return self.__pkey

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

        self.__principal = users[data['participant']['primaryKey']]

        # If the user is the owner of the entity
        self.__owner = data['owner']

    def __str__(self) -> str:
        return str(self.__principal) + f' [{",".join(k for k, v in self.__permissions.items() if v == True)}]'

    def get_principal(self) -> DeckUser:
        return self.__principal

    def can_edit(self) -> bool:
        return self.__permissions['edit']

    def can_share(self) -> bool:
        return self.__permissions['share']

    def can_manage(self) -> bool:
        return self.__permissions['manage']

    def is_owner(self) -> bool:
        return self.__owner


class DeckLabel:
    def __init__(self, label: dict, bid: int):
        # Internal identifiers for the label
        self.__board_id = bid
        self.__id = label['id']
        self.__tag = label['ETag']

        # Not sure about what this is? We'll store it but keep it private and not expose it for now...
        self.__card_id = label['cardId']

        self.__title = label['title']
        self.__color = label['color']
        self.__last_edited_date = dt.fromtimestamp(label['lastModified']).astimezone(tz.utc)

    def __str__(self) -> str:
        return f'{self.__title} (#{self.__color.upper()})'

    def __repr__(self) -> str:
        return self.__tag

    def get_title(self) -> str:
        return self.__title

    def get_color(self) -> str:
        return self.__color

    def get_last_modification_time(self) -> dt:
        return self.__last_edited_date


class DeckAttachment:
    def __init__(self, attachment: dict):
        self.__id = attachment['id']
        self.__type = attachment['type']
        self.__data = attachment['data']
        self.__size = attachment['extendedData']['filesize']
        self.__mime = attachment['extendedData']['mimetype']
        self.__name = {'dir': attachment['extendedData']['info']['dirname'],
                       'name': attachment['extendedData']['info']['filename'],
                       'ext': attachment['extendedData']['info']['extension']}

        # TODO: Is this the primary key or UUID? If the former, use it to retrieve actual DeckUser
        self.__owner = attachment['createdBy']

        self.__creation_time = dt.fromtimestamp(attachment['createdAt']).astimezone(tz.utc)
        self.__last_edit_time = dt.fromtimestamp(attachment['lastModified']).astimezone(tz.utc)
        self.__deletion_time = dt.fromtimestamp(attachment['deletedAt']).astimezone(tz.utc)

    def __str__(self) -> str:
        return f'ATTACHMENT {".".join([self.__name["name"], self.__name["ext"]])} ({self.__size} byte)'

    def get_id(self) -> int:
        return self.__id

    def get_type(self) -> str:
        return self.__type

    def get_size(self) -> int:
        return self.__size

    def get_mime(self) -> str:
        return self.__mime

    def get_full_name(self) -> str:
        # Not using os.path.join as this is nextcloud dependant and not client dependant
        # Using slash as I assume this will be the separator used (since both HTTP and Linux use it)
        # TODO: Figure out which separator NC uses (until now only the value "." has been observed for dir)
        return self.__name['dir'] + '/' + self.__name['name'] + '.' + self.__name['ext']

    def get_directory(self) -> str:
        return self.__name['dir']

    def get_name(self) -> str:
        return self.__name['name']

    def get_extension(self) -> str:
        return self.__name['ext']

    def get_owner(self) -> str:
        return self.__owner

    def get_creation_time(self) -> dt:
        return self.__creation_time

    def get_last_modification_time(self) -> dt:
        return self.__last_edit_time

    def get_deletion_time(self) -> dt:
        return self.__deletion_time


class DeckCard:
    def __init__(self, card: dict, bid: int, sid: int, labels: dict[DeckLabel], users: dict[DeckUser], api: DeckAPI):
        # Internal identifiers for the card
        self.__board_id = bid
        self.__stack_id = sid
        self.__id = card['id']
        self.__tag = card['ETag']

        # TODO: Document possible values and meaning, use it in a meaningful way?
        self.__type = card['type']

        self.__title = card['title']
        self.__description = card['description'].strip()
        self.__labels = [labels[label['ETag']] for label in card['labels']]
        self.__archived = card['archived']

        attachment_count = card['attachmentCount']
        if attachment_count > 0:
            attachments = api.request(f'boards/{bid}/stacks/{sid}/cards/{self.__id}/attachments')
            self.__attachments = [DeckAttachment(attachment) for attachment in attachments]
        else:
            self.__attachments = []

        # Timestamps
        self.__creation_time = dt.fromtimestamp(card['createdAt']).astimezone(tz.utc)
        self.__last_edited_time = dt.fromtimestamp(card['lastModified']).astimezone(tz.utc)
        self.__deletion_time = dt.fromtimestamp(card['deletedAt']).astimezone(tz.utc)

        # TODO: Fix this obscenity without breaking PEP8, somehow
        self.__card_due_time = None if card['duedate'] is None else \
            dt.strptime(card['duedate'], '%Y-%m-%dT%H:%M:%S%z').astimezone(tz.utc)

        # Users
        self.__assigned_users = [users[assignee['participant']['primaryKey']] for assignee in card['assignedUsers']]
        self.__owner = users[card['owner']['primaryKey']]

        # NOTE: This is just the UUID/PK of the user not the entire structure
        # TODO: Figure out whether this is a UUID or PK and in case it's the PK just get the DeckUser from dict
        self.__last_editor = card['lastEditor']

    def __str__(self) -> str:
        result = f'CARD "{self.__title}":\n'
        result += f'    Description: "{self.get_shortened_description(50)}"\n'
        result += f'    Labels: {", ".join(label.__title for label in self.__labels)}\n'
        result += f'    Attachments: {"None" if len(self.__attachments) == 0 else len(self.__attachments)}\n'
        result += f'    Archived: {"Yes" if self.__archived else "No"}\n'
        result += f'    Due date: {self.__card_due_time}\n'
        result += f'    Creator: {self.__owner}\n'

        if self.__last_editor is not None:
            result += f'    Last edit at {self.__last_edited_time} by {self.__last_editor}\n'

        if len(self.__assigned_users) > 0:
            result += '    ASSIGNEES:\n        '
            result += '\n        '.join([str(assignee) for assignee in self.__assigned_users])

        if len(self.__attachments) > 0:
            result += '    ATTACHMENTS:\n        '
            result += '\n        '.join([str(attachment) for attachment in self.__attachments])

        return result

    def get_title(self) -> str:
        return self.__title

    def get_description(self) -> str:
        return self.__description

    def get_shortened_description(self, length: int) -> str:
        result = " ".join([line for line in self.__description.splitlines()])
        length = length if length > 0 else len(result)
        return result[0:min(length, len(result))].strip() + ('...' if length < len(result) else '')

    def get_labels(self) -> list[DeckLabel]:
        return self.__labels

    def get_creation_time(self) -> dt:
        return self.__creation_time

    def get_last_modified_time(self) -> dt:
        return self.__last_edited_time

    def get_last_modified_user(self) -> dt:
        return self.__last_editor

    def get_deletion_time(self) -> Optional[dt]:
        return self.__deletion_time

    def get_due_time(self) -> Optional[dt]:
        return self.__card_due_time

    def get_owner(self) -> DeckUser:
        return self.__owner

    def get_assigned_users(self) -> list[DeckUser]:
        return self.__assigned_users

    def has_label(self, label: [DeckLabel, str]) -> bool:
        if isinstance(label, DeckLabel):
            for item in self.__labels:
                if item is label:
                    return True
            return False
        elif isinstance(label, str):
            for item in self.__labels:
                if item.get_title() == label:
                    return True
            return False
        else:
            # TODO: Throw an error
            return False

    def is_archived(self) -> bool:
        return self.__archived

    def get_id(self) -> int:
        return self.__id


class DeckStack:
    def __init__(self, stack: dict, bid: int, labels: dict[DeckLabel], users: dict[DeckUser], api: DeckAPI):
        # Internal identifiers for the board
        self.__board_id = bid
        self.__id = stack['id']
        self.__tag = stack['ETag']
        self.__order = stack['order']

        self.__last_edited_time = dt.fromtimestamp(stack['lastModified']).astimezone(tz.utc)
        self.__title = stack['title']

        if 'cards' in stack:
            self.cards = [DeckCard(card, bid, stack['id'], labels, users, api) for card in stack['cards']]
        else:
            self.cards = []

    def __str__(self) -> str:
        result = f'STACK "{self.__title}"\n'

        for card in self.cards:
            result += ('\n'.join(['    ' + line for line in str(card).splitlines()])) + '\n'

        return result

    def __repr__(self) -> str:
        return self.__tag

    def get_title(self) -> str:
        return self.__title

    def get_last_modified(self) -> dt:
        return self.__last_edited_time

    # TODO: Order them. Add filters (label, other?)
    def get_cards(self) -> list[DeckCard]:
        return self.cards

    def get_events(self) -> list[DeckCard]:
        return [card for card in self.cards if card.__card_due_time and card.__card_due_time >= dt.now(tz.utc)]

    def get_card(self, cid: int) -> Optional[DeckCard]:
        for card in self.cards:
            if card.get_id() == cid:
                return card
        return None

    def get_next_event(self) -> Optional[DeckCard]:
        result = None
        for card in self.cards:
            # TODO: Fix this obscenity without breaking PEP8, somehow
            if card and card.__card_due_time and (not result or (result and result.card_due_time > card.__card_due_time)) \
                    and card.__card_due_time >= dt.now(tz.utc):
                result = card

        return result

    def get_id(self) -> int:
        return self.__id


class DeckBoard:
    def __init__(self, board: dict, api: DeckAPI):
        # Internal identifiers for the board
        self.__id = board['id']
        self.__tag = board['ETag']

        # Internal boaard settings
        self.__permissions = board['permissions']  # Permissions for this user (r,w,share,manage)
        # TODO: These are not documented, find possible values and their meaning and expose them accordingly
        self.__notification_settings = board['settings']['notify-due']  # Notification settings for board
        self.__synchronize = board['settings']['calendar']  # Whether the board synchronizes with CalDAV

        self.__title = board['title']
        self.__color = board['color']
        self.__labels = {label['ETag']: DeckLabel(label, self.__id) for label in board['labels']}

        # Users and access control
        self.__users = {user['primaryKey']: DeckUser(user) for user in board['users']}
        self.__owner = self.__users[board['owner']['primaryKey']]
        self.__acl = [DeckAcl(acl, self.__users) for acl in board['acl']]

        self.__archived = board['archived']  # Board archived by current user
        self.__shared = board['shared']  # Board shared to the current user (not owned by current user)

        # Timestamps for deletion and last edit. Deletion timestamp is 0 if the board has not been deleted

        # TODO: Fix this obscenity without breaking PEP8, somehow
        self.__deletion_time = None if board['deletedAt'] == 0 else \
            dt.fromtimestamp(board['deletedAt']).astimezone(tz.utc)
        self.__last_edited_time = None if board['lastModified'] == 0 else \
            dt.fromtimestamp(board['lastModified']).astimezone(tz.utc)

        stacks = api.request(f'boards/{self.__id}/stacks')
        self.__stacks = [DeckStack(stack, board['id'], self.__labels, self.__users, api) for stack in stacks]

    def __str__(self):
        result = ''

        result += f'BOARD "{self.__title}"\n'
        result += f'    Color: #{self.__color.upper()}\n'
        result += f'    Archived: {self.__archived}\n'
        result += f'    Shared to current user: {"No" if self.__shared == 0 else "Yes"}\n'
        result += f'    Deleted: {"No" if self.__deletion_time is None else f"Yes, at {self.__deletion_time}"}\n'
        result += f'    Owner: {self.__owner}\n'
        result += f'    Last modification at {self.__last_edited_time}\n'

        if len(self.__labels) > 0:
            result += f'    LABELS:\n'
            for label in self.__labels.values():
                result += ('\n'.join(['        ' + line for line in str(label).splitlines()])) + '\n'

        if len(self.__users) > 0:
            result += f'    USERS:\n'
            for user in self.__users.values():
                result += ('\n'.join(['        ' + line for line in str(user).splitlines()])) + '\n'

        if len(self.__acl) > 0:
            result += f'    ACL:\n'
            for acl in self.__acl:
                result += ('\n'.join(['        ' + line for line in str(acl).splitlines()])) + '\n'

        result += '\n'.join(['    ' + line for stack in self.__stacks for line in str(stack).splitlines()])

        return result

    def __repr__(self) -> str:
        return self.__tag

    def can_read(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_READ']
        else:
            for acl in self.__acl:
                if repr(acl.__principal) == pk:
                    return True
            return False

    def can_edit(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_EDIT']
        else:
            for acl in self.__acl:
                if repr(acl.__principal) == pk:
                    return acl.can_edit()
            return False

    def can_manage(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_MANAGE']
        else:
            for acl in self.__acl:
                if repr(acl.__principal) == pk:
                    return acl.can_manage()
            return False

    def can_share(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_SHARE']
        else:
            for acl in self.__acl:
                if repr(acl.__principal) == pk:
                    return acl.can_share()
            return False

    def is_archived(self) -> bool:
        return self.__archived

    def is_shared(self) -> bool:
        return self.__shared

    def get_title(self) -> str:
        return self.__title

    def get_color(self) -> str:
        return self.__color

    def get_labels(self) -> list[DeckLabel]:
        return [v for k, v in self.__labels.items()]

    def get_users(self) -> list[DeckUser]:
        return [v for k, v in self.__users.items()]

    def get_owner(self) -> DeckUser:
        return self.__owner

    def get_deletion_time(self) -> Optional[dt]:
        return self.__deletion_time

    def get_last_modification_time(self) -> dt:
        return self.__last_edited_time

    def get_id(self) -> int:
        return self.__id

    # TODO: Order them. Add filters (which ones?)
    def get_stacks(self) -> list[DeckStack]:
        return self.__stacks

    def get_stack(self, sid: int) -> Optional[DeckStack]:
        for stack in self.__stacks:
            if stack.get_id() == sid:
                return stack
        return None

    # TODO: Order them. Add filters (label, other?)
    def get_cards(self) -> list[DeckCard]:
        return [card for stack in self.__stacks for card in stack.get_cards()]

    def get_events(self) -> list[DeckCard]:
        return [card for card in self.get_cards() if card.__card_due_time and card.__card_due_time >= dt.now(tz.utc)]

    def get_next_event(self) -> Optional[DeckCard]:
        result = None
        for stack in self.__stacks:
            card = stack.get_next_event()
            # TODO: Fix this obscenity without breaking PEP8, somehow
            if card and (not result or (result and result.__card_due_time > card.__card_due_time)) \
                    and card.__card_due_time >= dt.now(tz.utc):
                result = card

        return result


class Deck:
    def __init__(self, domain: str, username: str, password: str, secure: bool):
        self.__username = username
        self.__password = password
        self.__api = DeckAPI(username, password, domain, secure)

        self.next_event = None
        self.boards = {}
        self.users = {}

        self.download()

    def __str__(self):
        return '\n\n'.join([str(board) for board in self.boards.values()])

    def __search_next_event(self) -> Optional[DeckCard]:
        result = None
        for board in self.boards.values():
            card = board.get_next_event()
            # TODO: Fix this obscenity without breaking PEP8, somehow
            if card and (not result or (result and result.card_due_time > card.__card_due_time)) \
                    and card.__card_due_time >= dt.now(tz.utc):
                result = card

        return result

    def download(self):
        boards = self.__api.request('boards?details=1')
        self.boards = {b['ETag']: DeckBoard(b, self.__api) for b in boards if b['deletedAt'] == 0}

        self.next_event = self.__search_next_event()

    def get_next_event(self) -> Optional[DeckCard]:
        return self.next_event

    # TODO: Order them. Add filters (label, other?)
    def get_cards(self) -> list[DeckCard]:
        return [card for board in self.boards for stack in board.get_stacks() for card in stack]

    def get_boards(self) -> list[DeckBoard]:
        return self.boards

    def get_board(self, bid: int) -> Optional[DeckBoard]:
        for board in self.boards:
            if board.get_id() == bid:
                return board
        return None


# Test basic program functionality
if __name__ == '__main__':
    hostname = os.environ.get("OC_DECK_HOST")
    username = os.environ.get('OC_DECK_USER')
    password = os.environ.get('OC_DECK_PASS')
    security = os.environ.get('OC_USE_HTTPS') == 'True'

    deck = Deck(hostname, username, password, security)
    print(deck)
