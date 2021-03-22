import requests
import json
import os
import logging

from typing import Optional
from requests.auth import HTTPBasicAuth
from datetime import datetime


class DeckUser:
    def __init__(self, key: str, uid: str, utype: int, name: str):
        self.__pkey = key     # Used as index in dictionary
        self.__uuid = uid
        self.__type = utype

        self.name = name


class DeckAcl:
    def __init__(self, aid: int, user: DeckUser, atype: int, edit: bool, share: bool, manage: bool, owner: bool):
        # Internal ID of ACL
        self.__id = aid

        # User this refers to
        self.user = user
        self.type = atype

        # If the user is the owner of the entity
        self.is_owner = owner

        # Access rights
        self.can_edit = edit
        self.can_share = share
        self.can_manage = manage


class DeckCard:
    def __init__(self, cid: int, etag: str, title: str, descr: str, labels: list, ctype: int, attachments: list,
                 create: datetime, modify: datetime, delete: datetime, target: datetime, assignees: list,
                 creator: DeckUser, editor: DeckUser, order: int, archived: bool, unread_comments: int, overdue: int):
        # Internal card id and entity tag
        self.__id = cid
        self.__tag = etag

        # Card information
        self.title = title
        self.description = descr
        self.labels = labels
        self.type = ctype
        self.attachments = attachments

        # Timestamps
        self.create_time = create
        self.modify_time = modify
        self.delete_time = delete
        self.target_time = target   # Due date of the card

        # Users
        self.assignees = assignees
        self.creator = creator
        self.last_editor = editor

        # Metadata
        self.order = order
        self.archived = archived
        self.unread_comments = unread_comments
        self.overdue = overdue


class DeckStack:
    def __init__(self, stack: dict):
        # Internal identifiers for the board
        self.__id = stack['id']
        self.__tag = stack['ETag']

        self.last_edit_time = stack['lastModified']
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
        self.acl = DeckAcl(board['acl'])

        self.archived = board['archived']   # Board archived by current user
        self.shared = board['shared']       # Board shared to the current user (not owned by current user)

        # Timestamps for deletion and last edit. Deletion timestamp is 0 if the board has not been deleted
        self.deletion_time = None if board['deletedAt'] == 0 else datetime.fromtimestamp(board['deletedAt'])
        self.last_edit_time = None if board['lastModified'] == 0 else datetime.fromtimestamp(board['lastModified'])

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

        if title in self.boards and self.boards[title].last_edit == timestamp:
            return False
        else:
            return True

    def __parse_user(self, user_json: dict) -> DeckUser:
        index = user_json if isinstance(user_json, str) else user_json['primaryKey']
        if index not in self.users:
            pkey = index
            uuid = user_json['uid']
            nick = user_json['displayname']
            utype = user_json['type']

            self.users[pkey] = DeckUser(pkey, uuid, utype, nick)
        return self.users[index]

    def __parse_acls(self, acls_json) -> list:
        return [self.__parse_acl(acl_json) for acl_json in acls_json]

    def __parse_acl(self, acl_json: dict):
        user = self.__parse_user(acl_json['participant'])
        owner = acl_json['owner']
        edit = acl_json['owner']
        share = acl_json['owner']
        manage = acl_json['owner']
        atype = acl_json['type']
        aid = acl_json['id']
        return DeckAcl(aid, user, atype, edit, share, manage, owner)

    def __parse_card(self, data: dict):
        cid = data['id']
        tag = data['ETag']
        title = data['title']
        descr = data['description']
        labels = data['labels']
        ctype = data['type']
        attachments = data['attachments']

        create = datetime.fromtimestamp(data['createdAt'])
        delete = datetime.fromtimestamp(data['deletedAt'])
        modify = datetime.fromtimestamp(data['lastModified'])

        target = None if data['duedate'] is None else datetime.strptime(data['duedate'], '%Y-%m-%dT%H:%M:%S%z')

        assignees = [self.__parse_user(d['participant']) for d in data['assignedUsers']]
        owner = self.__parse_user(data['owner'])
        editor = None if data['lastEditor'] is None else self.__parse_user(data['lastEditor'])

        order = data['order']
        archived = data['archived']
        unread = data['commentsUnread']
        overdue = data['overdue']

        return DeckCard(cid, tag, title, descr, labels, ctype, attachments, create, modify, delete, target, assignees,
                        owner, editor, order, archived, unread, overdue)

    def __parse_cards(self, data: list):
        return [self.__parse_card(d) for d in data]

    def __parse_stack(self, data: dict):
        sid = data['id']
        tag = data['ETag']
        order = data['order']
        modify = datetime.fromtimestamp(data['lastModified'])
        title = data['title']
        cards = None if 'cards' not in data else self.__parse_cards(data['cards'])

        return DeckStack(sid, tag, modify, order, title, cards)

    def __parse_stacks(self, data: list):
        return [self.__parse_stack(d) for d in data]

    def __parse_board(self, board_json: dict) -> DeckBoard:
        bid = board_json['id']
        tag = board_json['ETag']

        permissions = list(board_json['permissions'].values())

        notifications = board_json['settings']['notify-due']
        calendar = board_json['settings']['calendar']

        title = board_json['title']
        color = board_json['color']
        labels = board_json['labels']

        # ACL and owner of the board
        acl = self.__parse_acls(board_json['acl'])
        owner = self.__parse_user(board_json['owner'])

        archived = board_json['archived']
        shared = board_json['shared']

        delete = datetime.fromtimestamp(board_json['deletedAt'])
        modify = datetime.fromtimestamp(board_json['lastModified'])

        stacks = self.__parse_stacks(json.JSONDecoder().decode(self.__api_request(f'boards/{bid}/stacks')))

        return DeckBoard(bid, tag, permissions, stacks, calendar, title, shared, acl, archived, color, labels, owner,
                         delete, modify, notifications)

    def download(self):
        decoder = json.JSONDecoder()

        boards = decoder.decode(self.__api_request('boards'))
        self.boards = [DeckBoard(b, self.__api_request(f'boards/{b["id"]}/stacks')) for b in boards]

        # for b in boards:
        #   if not self.__is_outdated(b['title'], b['lastModified']) or b['deletedAt'] != 0 or b['title'] == 'Personal':
        #        continue

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

    dw = Deck(hostname, username, password, security)
    pass


if __name__ == '__main__':
    main()
