import requests
import os
import logging

from typing import Optional, Union
from requests import ConnectionError, HTTPError, Timeout, TooManyRedirects
from requests.auth import HTTPBasicAuth
from datetime import datetime as dt, timezone as tz

from DeckErrors import DeckAPIRequestError as APIError, DeckInvalidInputError as InputError


class DeckAPI:
    def __init__(self, username: str, password: str, hostname: str, secure: bool):
        self.__api_base = f'{"https" if secure else "http"}://{hostname}/index.php/apps/deck/api/v1.0/'
        self.__username = username
        self.__password = password

    def request(self, binding: str) -> Optional[Union[list, dict]]:
        logging.debug(f'Making request {self.__api_base + binding}...')
        try:
            response = requests.get(self.__api_base + binding,
                                    headers={'OCS-APIRequest': 'true', 'Content-Type': 'application/json'},
                                    auth=HTTPBasicAuth(self.__username, self.__password))
        except ConnectionError:
            raise APIError(APIError.Reason.CONNECTION, 0, 'Connection error.')
        except HTTPError:
            raise APIError(APIError.Reason.RESPONSE, 0, 'Invalid HTTP response')
        except Timeout:
            raise APIError(APIError.Reason.TIMEOUT, 0, 'Timeout during connection')
        except TooManyRedirects:
            APIError(APIError.Reason.RESPONSE, 0, 'Too many redirects')
            return None

        # Check if the status code is an error or if the return type is not json data in case we screw up
        if not response.ok or 'application/json' not in response.headers['Content-Type']:
            raise APIError(APIError.Reason.RESPONSE, response.status_code, f'Server error while processing response')

        return response.json()


class DeckUser:
    def __init__(self, data: dict):
        # Internal user identifiers and types
        self.__pkey = data['primaryKey']
        self.__uuid = data['uid']
        self.__type = data['type']
        self.__name = data['displayname']

    def __str__(self) -> str:
        return f'{self.__name} (PK={self.__pkey}, UID={self.__uuid}, Type={self.__type})'

    def __repr__(self) -> str:
        return self.__pkey

    def get_name(self) -> str:
        return self.__name

    def get_primary_key(self) -> str:
        return self.__pkey

    def get_id(self) -> str:
        return self.__uuid


class DeckAcl:
    def __init__(self, acl: dict, users: dict):
        # Internal identifier and type of the ACL
        self.__id = acl['id']
        self.__board_id = acl['boardId']
        self.__permissions = {'edit': acl['permissionEdit'],
                              'share': acl['permissionShare'],
                              'manage': acl['permissionManage']}

        # TODO: Figure out what is this and properly expose it
        self.__type = acl['type']

        # ACLs are different wrt to user management than cards or every other object that contains DeckUsers
        # While the list of users obtained with the "/boards?details=1" API call contains all effective users
        # of the board, that is people that can create and modify content inside the board, ACLs can also contain
        # groups. Groups get unrolled within the previous API call into the single participants, therefore ACL
        # principals are not guaranteed to be in the DeckBoard.users dictionary. We remedy this by adding those
        # principals to that dictionary in the event they are not found at ACL creation time.
        if acl['participant']['primaryKey'] not in users:
            users[acl['participant']['primaryKey']] = DeckUser(acl['participant'])
        self.__principal = users[acl['participant']['primaryKey']]

        # If the user is the owner of the entity
        self.__owner = acl['owner']

    def __str__(self) -> str:
        return (str(self.__principal) +
                f' [{",".join(k for k, v in self.__permissions.items() if v == True)}]' +
                f' (ACL #{self.__id}, Board #{self.__board_id}, Type {self.__type}')

    def __repr__(self) -> str:
        return '.'.join([self.__board_id, self.__id])

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

    def get_id(self) -> int:
        return self.__id


class DeckLabel:
    def __init__(self, label: dict):
        # Internal identifiers for the label
        self.__board_id = label['boardId']
        self.__id = label['id']
        self.__tag = label['ETag']

        # Not sure about what this is? We'll store it but keep it private and not expose it for now...
        self.__card_id = label['cardId']

        self.__title = label['title']
        self.__color = label['color']
        self.__last_edited_date = dt.fromtimestamp(label['lastModified']).astimezone(tz.utc)

    def __str__(self) -> str:
        return (f'{self.__title} (#{self.__color.upper()} - ' +
                f'Label #{self.__id}, Board #{self.__board_id}, Last edited on {self.__last_edited_date})')

    def __repr__(self) -> str:
        return self.__tag

    def get_title(self) -> str:
        return self.__title

    def get_color(self) -> str:
        return self.__color

    def get_last_modification_time(self) -> dt:
        return self.__last_edited_date

    def get_id(self) -> int:
        return self.__id

    def get_tag(self) -> str:
        return self.__tag


class DeckAttachment:
    def __init__(self, attachment: dict, sid: int, bid: int):
        self.__id = attachment['id']
        self.__card_id = attachment['cardId']
        self.__stack_id = sid
        self.__board_id = bid

        # TODO: Document possible values and expose properly
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
        self.__deletion_time = (dt.fromtimestamp(attachment['deletedAt']).astimezone(tz.utc)
                                if attachment['deletedAt'] != 0 else None)

    def __str__(self) -> str:
        result = f'ATTACHMENT "{self.__name["dir"] + "/" + self.__name["name"] + "." + self.__name["ext"]}:"\n'
        result += f'    Size: {self.__size} bytes\n'
        result += f'    MIME: {self.__mime}\n'
        result += f'    Owner: {self.__owner}\n'
        result += f'    Created: {self.__creation_time}\n'
        result += f'    Last edited: {self.__last_edit_time}\n'
        result += f'    Deleted{"at" + str(self.__deletion_time) if self.__deletion_time else ": No"}\n'

        return result

    def __repr__(self) -> str:
        return '.'.join([self.__board_id, self.__stack_id, self.__card_id, self.__id])

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

    def get_deletion_time(self) -> Optional[dt]:
        return self.__deletion_time

    def get_id(self) -> int:
        return self.__id


class DeckCard:
    def __init__(self, card: dict, bid: int, labels: dict[DeckLabel], users: dict[DeckUser], api: DeckAPI):
        # Internal identifiers for the card
        self.__board_id = bid
        self.__stack_id = card['stackId']
        self.__id = card['id']
        self.__tag = card['ETag']

        # TODO: Document possible values and meaning, use it in a meaningful way?
        self.__type = card['type']

        self.__order = card['order']

        self.__title = card['title']
        self.__description = card['description'].strip()
        self.__labels = [labels[label['ETag']] for label in card['labels']]
        self.__archived = card['archived']

        self.__attachments = ([DeckAttachment(attachment, self.__stack_id, self.__board_id) for attachment in
                              api.request(f'boards/{bid}/stacks/{self.__stack_id}/cards/{self.__id}/attachments')]
                              if card['attachmentCount'] > 0 else [])

        self.__unread_comments = card['commentsUnread']

        # Timestamps
        self.__creation_time = dt.fromtimestamp(card['createdAt']).astimezone(tz.utc)
        self.__last_edited_time = dt.fromtimestamp(card['lastModified']).astimezone(tz.utc)
        self.__deletion_time = (dt.fromtimestamp(card['deletedAt']).astimezone(tz.utc)
                                if card['deletedAt'] != 0 else None)

        self.__card_due_time = (None if card['duedate'] is None else
                                dt.strptime(card['duedate'], '%Y-%m-%dT%H:%M:%S%z').astimezone(tz.utc))

        # Users
        self.__assigned_users = [users[assignee['participant']['primaryKey']] for assignee in card['assignedUsers']]
        self.__owner = users[card['owner']['primaryKey']]

        # NOTE: This is just the UUID/PK of the user not the entire structure
        # TODO: Figure out whether this is a UUID or PK and in case it's the PK just get the DeckUser from dict
        self.__last_editor = card['lastEditor']

    def __str__(self) -> str:
        result = f'CARD "{self.__title}" (Card #{self.__id}, Stack #{self.__stack_id}, Board #{self.__board_id}):\n'
        result += f'    Type: {self.__type}\n'
        result += f'    Description: "{self.get_shortened_description(50)}"\n'
        result += f'    Labels: {", ".join(label.get_title() for label in self.__labels)}\n'
        result += f'    Attachments: {"None" if len(self.__attachments) == 0 else len(self.__attachments)}\n'
        result += f'    Archived: {"Yes" if self.__archived else "No"}\n'
        result += f'    Due date: {self.__card_due_time if self.__card_due_time else "None"}\n'
        result += f'    Order: {self.__order}\n'
        result += f'    Unread comments: {self.__unread_comments}\n'
        result += f'    Deleted{" at" + str(self.__deletion_time) if self.__deletion_time else ": No"}\n'
        result += f'    Created at {self.__creation_time} by {self.__owner}\n'

        if self.__last_editor is not None:
            result += f'    Last edit at {self.__last_edited_time} by {self.__last_editor}\n'

        result += (' '*4 + 'LABELS:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__labels for e in str(i).splitlines()]) +
                   '\n' if len(self.__labels) > 0 else '')

        result += (' '*4 + 'ASSIGNED USERS:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__assigned_users for e in str(i).splitlines()]) +
                   '\n' if len(self.__assigned_users) > 0 else '')

        result += (' '*4 + 'ATTACHMENTS:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__attachments for e in str(i).splitlines()]) +
                   '\n' if len(self.__attachments) > 0 else '')

        return result

    def __repr__(self) -> str:
        return self.__tag

    def get_title(self) -> str:
        return self.__title

    def get_description(self) -> str:
        return self.__description

    def get_shortened_description(self, length: int) -> str:
        result = ' '.join([line for line in self.__description.splitlines()])
        length = length if length > 0 else len(result)
        return result[0:min(length, len(result))].strip() + ('...' if length < len(result) else '')

    def get_labels(self) -> list[DeckLabel]:
        return self.__labels

    def get_order(self) -> int:
        return self.__order

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

    def get_attachments(self) -> list[DeckAttachment]:
        return self.__attachments

    def get_attachment(self, path: str) -> Optional[DeckAttachment]:
        result = [attachment for attachment in self.get_attachments() if attachment.get_full_name() == path]
        return result[0] if len(result) == 1 else None

    def get_unread_comments(self) -> int:
        return self.__unread_comments

    def is_assigned(self, user: Union[DeckUser, str]):
        if isinstance(user, DeckUser):
            return user in self.__assigned_users
        elif isinstance(user, str):
            return user in [item.get_name() for item in self.__assigned_users]
        else:
            raise InputError(f'Invalid input type {type(user)} for argument "user" of DeckCard.is_assigned(...)')

    def has_label(self, label: Union[DeckLabel, str]) -> bool:
        if isinstance(label, DeckLabel):
            return label in [item for item in self.__labels]
        elif isinstance(label, str):
            return label in [item.get_title() for item in self.__labels]
        else:
            raise InputError(f'Invalid input type {type(label)} for argument "label" of DeckCard.has_label(...)')

    def is_archived(self) -> bool:
        return self.__archived

    def get_id(self) -> int:
        return self.__id

    def get_tag(self) -> str:
        return self.__tag


class DeckStack:
    def __init__(self, stack: dict, labels: dict[DeckLabel], users: dict[DeckUser], api: DeckAPI):
        # Internal identifiers for the stack
        self.__board_id = stack['boardId']
        self.__id = stack['id']
        self.__tag = stack['ETag']
        self.__order = stack['order']

        self.__last_edited_time = dt.fromtimestamp(stack['lastModified']).astimezone(tz.utc)
        self.__deletion_time = (dt.fromtimestamp(stack['deletedAt']).astimezone(tz.utc)
                                if stack['deletedAt'] != 0 else None)

        self.__title = stack['title']
        self.__cards = ([DeckCard(card, self.__board_id, labels, users, api) for card in stack['cards']]
                        if 'cards' in stack else [])

    def __str__(self) -> str:
        result = f'STACK "{self.__title}" (Stack #{self.__id}, Board #{self.__board_id}):\n'
        result += f'    Order: {self.__order}\n'
        result += f'    Last modification at {self.__last_edited_time}\n'
        result += f'    Deleted{" at" + str(self.__deletion_time) if self.__deletion_time else ": no"}\n'
        result += f'    CARDS:\n        '
        result += "\n            ".join([line for card in self.__cards for line in str(card).splitlines()]) + '\n'

        return result

    def __repr__(self) -> str:
        return self.__tag

    def get_title(self) -> str:
        return self.__title

    def get_last_modification_time(self) -> dt:
        return self.__last_edited_time

    def get_deletion_time(self) -> Optional[dt]:
        return self.__deletion_time

    def get_order(self) -> int:
        return self.__order

    # TODO: Order them. Add filters (label, other?)
    def get_cards(self) -> list[DeckCard]:
        return self.__cards

    def get_events(self, past=False) -> list[DeckCard]:
        return sorted([c for c in self.__cards if c.get_due_time() and (past or c.get_due_time() >= dt.now(tz.utc))],
                      key=lambda x: x.get_due_time())

    def get_card(self, cid: int) -> Optional[DeckCard]:
        result = [item for item in self.__cards if item.get_id() == cid]
        return result[0] if len(result) == 1 else None

    def get_next_event(self) -> Optional[DeckCard]:
        result = self.get_events()
        return result[0] if len(result) > 0 else None

    def get_id(self) -> int:
        return self.__id

    def get_tag(self) -> str:
        return self.__tag


class DeckBoard:
    def __init__(self, board: dict, api: DeckAPI):
        # Internal identifiers for the board
        self.__id = board['id']
        self.__tag = board['ETag']

        # Internal board settings
        self.__permissions = board['permissions']  # Permissions for this user (r,w,share,manage)
        # TODO: These are not documented, find possible values and their meaning and expose them accordingly
        self.__notification_settings = board['settings']['notify-due']  # Notification settings for board
        self.__synchronize = board['settings']['calendar']  # Whether the board synchronizes with CalDAV

        self.__title = board['title']
        self.__color = board['color']
        self.__labels = {label['ETag']: DeckLabel(label) for label in board['labels']}

        # Users and access control
        self.__users = {user['primaryKey']: DeckUser(user) for user in board['users']}
        self.__owner = self.__users[board['owner']['primaryKey']]
        self.__acl = [DeckAcl(acl, self.__users) for acl in board['acl']]

        self.__archived = board['archived']  # Board archived by current user
        self.__shared = board['shared']  # Board shared to the current user (not owned by current user)

        # Timestamps for deletion and last edit. Deletion timestamp is 0 if the board has not been deleted
        self.__deletion_time = (dt.fromtimestamp(board['deletedAt']).astimezone(tz.utc)
                                if board['deletedAt'] != 0 else None)

        self.__last_edited_time = (None if board['lastModified'] == 0
                                   else dt.fromtimestamp(board['lastModified']).astimezone(tz.utc))

        self.__stacks = [DeckStack(stack, self.__labels, self.__users, api)
                         for stack in api.request(f'boards/{self.__id}/stacks')]

    def __str__(self):
        result = f'BOARD "{self.__title}" (Board #{self.__id}):\n'
        result += f'    Color: #{self.__color.upper()}\n'
        result += f'    Archived: {self.__archived}\n'
        result += f'    Shared to current user: {"No" if self.__shared == 0 else "Yes"}\n'
        result += f'    Deleted: {"No" if self.__deletion_time is None else f"Yes, at {self.__deletion_time}"}\n'
        result += f'    Owner: {self.__owner}\n'
        result += f'    Last modification at {self.__last_edited_time}\n'
        result += f'    Deleted{" at" + str(self.__deletion_time) if self.__deletion_time else ": No"}\n'
        result += f'    PERMISSIONS:\n'
        result += f'        Read: {self.__permissions["PERMISSION_READ"]}\n'
        result += f'        Edit: {self.__permissions["PERMISSION_EDIT"]}\n'
        result += f'        Manage: {self.__permissions["PERMISSION_MANAGE"]}\n'
        result += f'        Share: {self.__permissions["PERMISSION_SHARE"]}\n'

        result += (' '*4 + 'LABELS:\n' + ' '*8 +
                   '\n        '.join([e for i in [v for k, v in self.__labels.items()] for e in str(i).splitlines()]) +
                   '\n' if len(self.__labels) > 0 else '')

        result += (' '*4 + 'USERS:\n' + ' '*8 +
                   '\n        '.join([e for i in [v for k, v in self.__users.items()] for e in str(i).splitlines()]) +
                   '\n' if len(self.__users) > 0 else '')

        result += (' '*4 + 'ACL:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__acl for e in str(i).splitlines()])
                   + '\n' if len(self.__users) > 0 else '')

        result += (' '*4 + 'STACKS:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__stacks for e in str(i).splitlines()])
                   if len(self.__users) > 0 else '')

        return result

    def __repr__(self) -> str:
        return self.__tag

    def can_read(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_READ']
        else:
            return pk in [repr(item.get_principal()) for item in self.__acl]

    def can_edit(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_EDIT']
        else:
            return pk in [repr(item.get_principal()) for item in self.__acl if item.can_edit()]

    def can_manage(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_MANAGE']
        else:
            return pk in [repr(item.get_principal()) for item in self.__acl if item.can_manage()]

    def can_share(self, pk=None) -> bool:
        if not pk:
            return self.__permissions['PERMISSION_SHARE']
        else:
            return pk in [repr(item.get_principal()) for item in self.__acl if item.can_share()]

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

    # TODO: Order them. Add filters (which ones?)
    def get_stacks(self) -> list[DeckStack]:
        return self.__stacks

    def get_stack(self, sid: int) -> Optional[DeckStack]:
        result = [item for item in self.__stacks if item.get_id() == sid]
        return result[0] if len(result) == 1 else None

    # TODO: Order them. Add filters (label, other?)
    def get_cards(self) -> list[DeckCard]:
        return [card for stack in self.__stacks for card in stack.get_cards()]

    def get_events(self, past=False) -> list[DeckCard]:
        return sorted([c for events in [stack.get_events(past=past) for stack in self.__stacks] for c in events
                       if c.get_due_time() and (past or c.get_due_time() >= dt.now(tz.utc))],
                      key=lambda x: x.get_due_time())

    def get_card(self, cid: int) -> Optional[DeckCard]:
        result = [card for card in [stack.get_card(cid) for stack in self.__stacks] if card is not None]
        return result[0] if len(result) > 0 else None

    def get_next_event(self) -> Optional[DeckCard]:
        result = self.get_events()
        return result[0] if len(result) > 0 else None

    def get_id(self) -> int:
        return self.__id

    def get_tag(self) -> str:
        return self.__tag


class Deck:
    def __init__(self, domain: str, username: str, password: str, secure: bool):
        self.__username = username
        self.__password = password
        self.__api = DeckAPI(username, password, domain, secure)

        self.__events = []
        self.__boards = {}
        self.__users = {}

        self.download()

    def __str__(self):
        return '\n\n'.join([str(board) for board in self.__boards.values()])

    def download(self):
        # Not handling exception is intentional: let the client handle it according to application
        boards = self.__api.request('boards?details=1')

        self.__boards = {b['ETag']: DeckBoard(b, self.__api) for b in boards if b['deletedAt'] == 0}
        self.__events = sorted([e for ls in [v.get_events(past=True) for k, v in self.__boards.items()] for e in ls],
                               key=lambda x: x.get_due_time())

    def update(self):
        # TODO: Try to be smart and only re-download data that actually changed
        # Not handling exception is intentional: let the client handle it according to application
        self.download()

    def get_events(self, past=False) -> list[DeckCard]:
        return [e for e in self.__events if past or e.get_due_time >= dt.now(tz.utc)]

    def get_next_event(self) -> Optional[DeckCard]:
        return self.__events[0]

    # TODO: Order them. Add filters (label, other?)
    def get_cards(self) -> list[DeckCard]:
        return [card for board in self.__boards for stack in board.get_stacks() for card in stack]

    def get_card(self, cid: int) -> Optional[DeckCard]:
        for board in self.get_boards():
            card = board.get_card(cid)
            if card is not None:
                return card
        return None

    def get_boards(self) -> list[DeckBoard]:
        return [v for k, v in self.__boards]

    def get_board(self, bid: int) -> Optional[DeckBoard]:
        for board in self.__boards:
            if board.get_id() == bid:
                return board
        return None

    def get_users(self) -> list[DeckUser]:
        return [v for k, v in self.__users]

    def get_user(self, pk: str) -> Optional[DeckUser]:
        return self.__users[pk] if pk in self.__users else None


# Test basic program functionality
if __name__ == '__main__':
    deck_hostname = os.environ.get("OC_DECK_HOST")
    deck_username = os.environ.get('OC_DECK_USER')
    deck_password = os.environ.get('OC_DECK_PASS')
    deck_security = os.environ.get('OC_USE_HTTPS') == 'True'

    deck = Deck(deck_hostname, deck_username, deck_password, deck_security)
    print(deck)
