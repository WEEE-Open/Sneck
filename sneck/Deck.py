import requests
import json
import os
import logging

from typing import Optional
from requests.auth import HTTPBasicAuth
from datetime import datetime as dt


class DeckUser:
    def __init__(self, data: dict):
        # Internal user identifiers and types
        self.__pkey = data['primaryKey']
        self.__uuid = data['uid']
        self.__type = data['type']

        self.name = data['displayname']


class DeckAcl:
    def __init__(self, data: dict):
        # Internal identifier and type of the ACL
        self.__id = data['id']
        self.__type = data['type']

        # User this refers to
        self.principal = DeckUser(data['participant'])

        # If the user is the owner of the entity
        self.owner = data['owner']

        # Access rights
        self.can_edit = data['permissionEdit']
        self.can_share = data['permissionShare']
        self.can_manage = data['permissionManage']


class DeckLabel:
    def __init__(self, label: dict):
        # Internal identifiers for the label
        self.__id = label['id']
        self.__tag = label['ETag']

        # Not sure about what this is? We'll store it but keep it private and not expose it for now...
        self.__card_id = label['cardId']

        self.title = label['title']
        self.color = label['color']
        self.last_edited_date = dt.fromtimestamp(label['lastModified'])


class DeckCard:
    def __init__(self, card: dict):
        # Internal identifiers for the card
        self.__id = card['id']
        self.__tag = card['ETag']

        self.title = card['title']
        self.description = card['description']
        self.labels = card['labels']
        self.type = card['type']
        self.attachments = [] if card['attachments'] is None else card['attachments']
        self.order = card['order']
        self.archived = card['archived']
        self.unread_comments = card['commentsUnread']
        self.overdue = card['overdue']

        # Timestamps
        self.creation_time = dt.fromtimestamp(card['createdAt'])
        self.last_edited_time = dt.fromtimestamp(card['lastModified'])
        self.deletion_time = dt.fromtimestamp(card['deletedAt'])
        self.card_due_time = None if card['duedate'] is None else dt.strptime(card['duedate'], '%Y-%m-%dT%H:%M:%S%z')

        # Users
        self.assignees = [DeckUser(assignee['participant']) for assignee in card['assignedUsers']]
        self.creator = DeckUser(card['owner'])

        # NOTE: This is just the UUID/PK of the user not the entire structure
        # TODO: Figure out wether this is a UUID or PK
        self.last_editor = card['lastEditor']


class DeckStack:
    def __init__(self, stack: dict):
        # Internal identifiers for the board
        self.__id = stack['id']
        self.__tag = stack['ETag']

        self.last_edited_time = stack['lastModified']
        self.order = stack['order']
        self.title = stack['title']

        self.cards = [] if 'cards' not in stack else [DeckCard(card) for card in stack['cards']]


class DeckBoard:
    def __init__(self, board: dict, stacks: list):
        # Internal identifiers for the board
        self.__id = board['id']
        self.__tag = board['ETag']

        # Internal data to be exposed through accessors
        self.__permissions = board['permissions']                       # Permissions for this user (r,w,share,manage)
        self.__notification_settings = board['settings']['notify-due']  # Notification settings for board
        self.__synchronize = board['settings']['calendar']              # Whether the board synchronizes with CalDAV

        self.title = board['title']
        self.color = board['color']
        self.labels = board['labels']

        # Access control and permissions
        self.owner = DeckUser(board['owner'])
        self.acl = [DeckAcl(acl) for acl in board['acl']]

        self.archived = board['archived']   # Board archived by current user
        self.shared = board['shared']       # Board shared to the current user (not owned by current user)

        # Timestamps for deletion and last edit. Deletion timestamp is 0 if the board has not been deleted
        self.deletion_time = None if board['deletedAt'] == 0 else dt.fromtimestamp(board['deletedAt'])
        self.last_edited_time = None if board['lastModified'] == 0 else dt.fromtimestamp(board['lastModified'])

        self.stacks = [DeckStack(stack) for stack in stacks]    # Non-empty stacks of the board

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

    def __api_request(self, api_bindpost: str) -> json:
        logging.debug(f'Making request {self.__api_base + api_bindpost}...')
        response = requests.get(self.__api_base + api_bindpost,
                                headers={'OCS-APIRequest': 'true', 'Content-Type': 'application/json'},
                                auth=HTTPBasicAuth(self.__username, self.__password))

        if not response.ok:
            logging.error(f'Request failed [Return code: {response.status_code}]!')
            logging.error(f'Unable to download deck content from API {self.__api_base + api_bindpost}')

            return
        print(response.text)
        return response.text

    def __is_outdated(self, title: str, timestamp: int):
        if self.boards is None:
            return True

    def download(self):
        d = json.JSONDecoder()

        boards = d.decode(self.__api_request('boards'))
        self.boards = {b['ETag']: DeckBoard(b, d.decode(self.__api_request(f'boards/{b["id"]}/stacks')))
                       for b in boards if b['deletedAt'] == 0 and b['title'] != 'Personal'}

    def get_all_cards(self) -> list:
        result = []
        for board in self.boards.values():
            for stack in board.stacks.values():
                result += list(stack.cards.values())
        return result

    def get_all_stacks(self) -> list:
        result = []
        for board in self.boards.values():
            result += list(board.stacks.values())
        return result


def main():
    hostname = os.environ.get("OC_DECK_HOST")
    username = os.environ.get('OC_DECK_USER')
    password = os.environ.get('OC_DECK_PASS')
    security = os.environ.get('OC_USE_HTTPS') == 'True'

    deck = Deck(hostname, username, password, security)

    for board in deck.boards:
        print(f'BOARD "{board.title}"')
        print(f'   Color: #{board.color.upper()}')
        print(f'   Archived: {board.archived}')
        print(f'   Shared to current user: {"No" if board.shared == 0 else "Yes"}')
        print(f'   Deleted: {"No" if board.deletion_time is None else f"Yes, at {board.deletion_time}"}')
        print(f'   Last modification at {board.last_edited_time}\n')


if __name__ == '__main__':
    main()
