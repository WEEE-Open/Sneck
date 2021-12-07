#!/usr/bin/env python

import requests
import os
import logging
import json

from typing import Optional, Union
from requests import ConnectionError, HTTPError, Timeout, TooManyRedirects
from requests.auth import HTTPBasicAuth
from datetime import datetime as dt, timezone as tz
from time import time
from enum import Enum, unique

from DeckErrors import DeckAPIRequestError as APIError, DeckInvalidInputError as InputError


class DeckAPI:
    def __init__(self, username: str, password: str, hostname: str, secure: bool) -> None:
        self.__api_base = f'{"https" if secure else "http"}://{hostname}/index.php/apps/deck/api/v1.0/'
        self.__username = username
        self.__password = password

    def request(self, binding: str) -> Optional[Union[list, dict]]:
        logging.debug(f'Making request {self.__api_base + binding}...')
        try:
            print(f'Requesting: {self.__api_base}{binding}')
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
            print(response.json())
            raise APIError(APIError.Reason.RESPONSE, response.status_code, f'Server error while processing response')
        
        print(f'Request succesful, response: {response.status_code}')
        return response.json()

    def post(self, binding: str, payload: dict) -> Optional[Union[list, dict]]:
        try:
            print(f'Requesting [POST]: {self.__api_base}{binding}')
            response = requests.post(self.__api_base + binding, data=json.dumps(payload),
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
            print(response.json())
            raise APIError(APIError.Reason.RESPONSE, response.status_code, f'Server error while processing response')

        print(f'Request succesful, response: {response.status_code}')
        return response.json()

    # Getting an Internal Server Error when using PUT
    def put(self, binding: str, payload: dict) -> None:
        try:
            print(f'Requesting [PUT]: {self.__api_base}{binding}')
            # Must provide an owner inside the payload
            # The owner has to be a dictionary and provide all the info required (namely the uid)
            response = requests.put(self.__api_base + binding, data=json.dumps(payload),
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
            print(response.json())
            raise APIError(APIError.Reason.RESPONSE, response.status_code, f'Server error while processing response')

        print(f'Request succesful, response: {response.status_code}')
    
    def delete(self, binding: str) -> None:
        try:
            print(f'Requesting [DELETE]: {self.__api_base}{binding}')
            response = requests.delete(self.__api_base + binding,
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
            print(response.json())
            raise APIError(APIError.Reason.RESPONSE, response.status_code, f'Server error while processing response')
        
        print(f'Request succesful, response: {response.status_code}')
        

class DeckUser:
    @unique
    class Type(Enum):
        USER = 0
        GROUP = 1
        CIRCLE = 7

    __types = {
        '0': Type.USER,
        '1': Type.GROUP,
        '7': Type.CIRCLE
    }

    def __init__(self, data: dict) -> None:
        # Internal user identifiers and types
        self.__uuid = data['uid']
        self.__type = self.__types[str(data['type'])]
        self.__name = data['displayname']

    def __str__(self) -> str:
        return f'{self.__name} (UID={self.__uuid}, Type={self.__type})'

    def __repr__(self) -> str:
        return self.__uuid

    def update(self, user: dict) -> None:
        self.__init__(user)
        print(f'[UPDATE] Updated user {self.__uuid}.')

    def serialize(self) -> dict:
        return {'uid': self.__uuid, 'type': self.__type, 'displayname': self.__name}

    def get_name(self) -> str:
        return self.__name

    def get_type(self) -> Type:
        return self.__type

    def get_id(self) -> str:
        return self.__uuid


class DeckAcl:
    @unique
    class Type(Enum):
        USER = 0
        GROUP = 1
        CIRCLE = 7

    __types = {
        '0': Type.USER,
        '1': Type.GROUP,
        '7': Type.CIRCLE
    }

    def __init__(self, acl: dict, users: dict) -> None:        
        # Reference to the list of users of the board
        self.__users = users

        # Internal identifier and type of the ACL
        self.__id = acl['id']
        self.__board_id = acl['boardId']
        self.__permissions = {'edit': acl['permissionEdit'],
                              'share': acl['permissionShare'],
                              'manage': acl['permissionManage']}

        # ACLs are different wrt to user management than cards or every other object that contains DeckUsers
        # While the list of users obtained with the "/boards?details=1" API call contains all effective users
        # of the board, that is people that can create and modify content inside the board, ACLs can also contain
        # groups. Groups get unrolled within the previous API call into the single participants, therefore ACL
        # principals are not guaranteed to be in the DeckBoard.users dictionary. We remedy this by adding those
        # principals to that dictionary in the event they are not found at ACL creation time.
        if acl['participant']['uid'] not in users:
            users[acl['participant']['uid']] = DeckUser(acl['participant'])
        self.__principal = users[acl['participant']['uid']]

        # Same as the type for DeckUser
        #self.__type = self.__principal.get_type()
        self.__type = self.__types[str(acl['type'])]

        # If the user is the owner of the entity
        self.__owner = acl['owner']
        
        print(f'[UPDATE] Created ACL {self.__id}.')

    def __str__(self) -> str:
        return (str(self.__principal) +
                f' [{",".join(k for k, v in self.__permissions.items() if v == True)}]' +
                f' (ACL #{self.__id}, Board #{self.__board_id}, Type {self.__type}')

    def __repr__(self) -> str:
        return '.'.join([self.__board_id, self.__id])

    def update(self, acl: dict) -> None:
        self.__init__(self, acl, self.__users)
        print(f'[UPDATE] Updated ACL {self.__id}.')

    def get_principal(self) -> DeckUser:
        return self.__principal

    def get_type(self) -> Type:
        return self.__type

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
    def __init__(self, label: dict) -> None:
        # Internal identifiers for the label
        self.__board_id = label['boardId']
        self.__id = label['id']
        self.__tag = label['ETag']

        # Not sure about what this is? We'll store it but keep it private and not expose it for now...
        self.__card_id = label['cardId']

        self.__title = label['title']
        self.__color = label['color']
        self.__last_edited_date = dt.fromtimestamp(label['lastModified']).astimezone(tz.utc)

        print(f'[UPDATE] Created label {self.__id}.')

    def __str__(self) -> str:
        return (f'{self.__title} (#{self.__color.upper()} - ' +
                f'Label #{self.__id}, Board #{self.__board_id}, Last edited on {self.__last_edited_date})')

    def __repr__(self) -> str:
        return self.__tag

    def update(self, label: dict) -> None:
        self.__init__(label)
        print(f'[UPDATE] Updated label {self.__id}.')

    def serialize(self) -> dict:
        return {'boardId': self.__board_id, 'id': self.__id, 'ETag': self.__tag, 'title': self.__title, 'color': self.__color,
                'lastModified': dt.timestamp(self.__last_edited_date)}

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
    @unique
    class Type(Enum):
        # Types of attachments
        NEXTCLOUD_FILE = 1      # Files already present in the NextCloud storage and linked to the card
        DECK_FILE = 2           # Files uploaded as Deck attachments and stored in the DB

    # Mappings between the literal value of the "type" field and the corresponding enum item
    __types = {
        'deck_file': Type.DECK_FILE,
        'file': Type.NEXTCLOUD_FILE
    }

    def __init__(self, attachment: dict, sid: int, bid: int, users: dict[DeckUser]) -> None:
        self.__id = attachment['id']
        self.__card_id = attachment['cardId']
        self.__stack_id = sid
        self.__board_id = bid
        self.__users_dict = users

        # I was not able to clearly understand the intent of this field by looking at Deck's code. It looks to be a
        # metadata storage of sorts, as of now, it only stores the name of the uploaded file
        self.__data = attachment['data']

        self.__type = self.__types[attachment['type']]
        self.__size = attachment['extendedData']['filesize']
        self.__mime = attachment['extendedData']['mimetype']
        self.__name = {'dir': attachment['extendedData']['info']['dirname'],
                       'name': attachment['extendedData']['info']['filename'],
                       'ext': attachment['extendedData']['info']['extension']}

        self.__owner = users[attachment['createdBy']]
        self.__creation_time = dt.fromtimestamp(attachment['createdAt']).astimezone(tz.utc)
        self.__last_edit_time = dt.fromtimestamp(attachment['lastModified']).astimezone(tz.utc)
        self.__deletion_time = (dt.fromtimestamp(attachment['deletedAt']).astimezone(tz.utc)
                                if attachment['deletedAt'] != 0 else None)
        
        print(f'[UPDATE] Created attachment #{self.__id}.')

    def __str__(self) -> str:
        result = f'ATTACHMENT "{self.__name["dir"] + "/" + self.__name["name"] + "." + self.__name["ext"]}:"\n'
        result += f'    Size: {self.__size} bytes\n'
        result += f'    MIME: {self.__mime}\n'
        result += f'    Owner: {self.__owner}\n'
        result += f'    Created: {self.__creation_time}\n'
        result += f'    Last edited: {self.__last_edit_time}\n'
        result += f'    Deleted{"at" + str(self.__deletion_time) if self.__deletion_time else ": No"}\n'

        return result
    
    def update(self, attachment: dict) -> None:
        self.__init__(attachment, self.__stack_id, self.__board_id, self.__users_dict)
        print(f'[UPDATE]: Updated attachment #{self.__id}.')

    def __repr__(self) -> str:
        return '.'.join([self.__board_id, self.__stack_id, self.__card_id, self.__id])

    def get_size(self) -> int:
        return self.__size

    def get_mime(self) -> str:
        return self.__mime

    def get_full_name(self) -> str:
        # Using slash as path separator as I assume this will be the separator used (since both HTTP and Linux use it)
        return self.__name['dir'] + '/' + self.__name['name'] + '.' + self.__name['ext']

    def get_directory(self) -> str:
        return self.__name['dir']

    def get_name(self) -> str:
        return self.__name['name']

    def get_extension(self) -> str:
        return self.__name['ext']

    def get_owner(self) -> DeckUser:
        return self.__owner

    def get_creation_time(self) -> dt:
        return self.__creation_time

    def get_last_modification_time(self) -> dt:
        return self.__last_edit_time

    def get_deletion_time(self) -> Optional[dt]:
        return self.__deletion_time

    def get_data(self) -> str:
        return self.__data

    def get_id(self) -> int:
        return self.__id


class DeckCard:
    @unique
    class Type(Enum):
        PLAIN = 0
        TEXT = 1

    __types = {
        'plain': Type.PLAIN,
        'text': Type.TEXT       # Documentation says this type should not exist, but example cards use it
    }

    # References to the users and labels dictionaries.
    def __init__(self, card: dict, bid: int, labels: dict[DeckLabel], users: dict[DeckUser], api: DeckAPI, updateAttachments: bool = True,
                newCard: bool = False) -> None:
        if newCard:
            # Set everything to None except the API (this might not be an optimal or a clean solution)
            self.__api = api
            self.__board_id = None
            self.__stack_id = None
            self.__users_dict = None
            self.__labels_dict = None
            self.__id = None
            self.__tag = None
            self.__type = None
            self.__order = None
            self.__title = None
            self.__description = None
            self.__labels = None
            self.__archived = None
            self.__unread_comments_count = None
            self.__overdue = None
            self.__creation_time = None
            self.__last_edited_time = None
            self.__deletion_time = None
            self.__card_due_time = None
            self.__assigned_users = None
            self.__owner = None
            self.__last_editor = None
            self.__attachment_count = None
            self.__attachments = None
        elif card is not None and bid is not None and labels is not None and users is not None:
            # IDs of the parents of the card
            self.__board_id = bid
            self.__stack_id = card['stackId']

            # References to the label and user dictionaries and the API.
            self.__users_dict = users
            self.__labels_dict = labels
            self.__api = api

            # Attributes of the card
            self.__id = card['id']
            self.__tag = card['ETag']
            self.__type = self.__types[card['type']]
            self.__order = card['order']
            self.__title = card['title']
            self.__description = card['description'].strip()
            self.__labels = (None if card['labels'] is None else 
                            [labels[label['ETag']] for label in card['labels']])
            self.__archived = card['archived']
            self.__unread_comments_count = card['commentsUnread']
            self.__overdue = card['overdue']

            # Timestamps
            self.__creation_time = dt.fromtimestamp(card['createdAt']).astimezone(tz.utc)
            self.__last_edited_time = dt.fromtimestamp(card['lastModified']).astimezone(tz.utc)
            self.__deletion_time = (dt.fromtimestamp(card['deletedAt']).astimezone(tz.utc)
                                    if card['deletedAt'] is not None and card['deletedAt'] != 0 else None)
            self.__card_due_time = (None if card['duedate'] is None else
                                    dt.strptime(card['duedate'], '%Y-%m-%dT%H:%M:%S%z').astimezone(tz.utc))

            # Users
            self.__assigned_users = (None if card['assignedUsers'] is None else 
                                    [users[assignee['participant']['uid']] for assignee in card['assignedUsers']])
            self.__owner = (users[card['owner']['uid']] if isinstance(card['owner'], dict) else
                            users[card['owner']])
            self.__last_editor = users[card['lastEditor']] if card['lastEditor'] is not None else None

            # Card attachments
            self.__attachment_count = card['attachmentCount']
            self.__attachments = ({attachment['id']: DeckAttachment(attachment, self.__stack_id, self.__board_id, users) for attachment in
                                api.request(f'boards/{bid}/stacks/{self.__stack_id}/cards/{self.__id}/attachments')}
                                if self.__attachment_count is not None and self.__attachment_count > 0 else {})
                                
            print(f'[UPDATE] Created card {self.__id}.')

    def __str__(self) -> str:
        result =  f'CARD "{self.__title}" (Card #{self.__id}, Stack #{self.__stack_id}, Board #{self.__board_id}):\n'
        result += f'    Type: {self.__type}\n'
        result += f'    Description: "{self.get_shortened_description(50)}"\n'
        result += f'    Labels: {"None" if self.__labels is None else ", ".join(label.get_title() for label in self.__labels)}\n'
        result += f'    Attachments: {"None" if self.__attachments is None or len(self.__attachments) == 0 else len(self.__attachments)}\n'
        result += f'    Archived: {"Yes" if self.__archived else "No"}\n'
        result += f'    Due date: {self.__card_due_time if self.__card_due_time else "None"}\n'
        result += f'    Order: {self.__order}\n'
        result += f'    Unread comments: {self.__unread_comments_count}\n'
        result += f'    Deleted{" at" + str(self.__deletion_time) if self.__deletion_time else ": No"}\n'
        result += f'    Created at {self.__creation_time} by {self.__owner}\n'

        if self.__last_editor is not None:
            result += f'    Last edit at {self.__last_edited_time} by {self.__last_editor}\n'

        result += (' '*4 + 'LABELS:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__labels for e in str(i).splitlines()]) +
                   '\n' if self.__labels is not None and len(self.__labels) > 0 else '')

        result += (' '*4 + 'ASSIGNED USERS:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__assigned_users for e in str(i).splitlines()]) +
                   '\n' if self.__assigned_users is not None and len(self.__assigned_users) > 0 else '')

        result += (' '*4 + 'ATTACHMENTS:\n' + ' '*8 +
                   '\n        '.join([e for i in self.__attachments for e in str(i).splitlines()]) +
                   '\n' if self.__attachments is not None and len(self.__attachments) > 0 else '')

        return result

    def __repr__(self) -> str:
        return self.__tag
    
    def update(self, card: dict) -> None:
        self.__init__(card, self.__board_id, self.__labels_dict, self.__users_dict, self.__api, updateAttachments=False)

        if card['attachmentCount'] == 0:
            while len(self.__attachments) != 0:
                attachment = self.__attachments.popitem()
                print(f'[UPDATE] Removed attachment {attachment.get_id()} from card {self.__id}.')
            return
        
        attachments = self.__api.request(f'boards/{self.__board_id}/stacks/{self.__stack_id}/cards/{self.__id}/attachments')

        for attachment in attachments:
            if attachment['id'] not in self.__attachments:
                self.__attachments[attachment['id']] = DeckAttachment(attachment, self.__stack_id, self.__board_id, users)
                print(f'[UPDATE] Added attachment {attachment["id"]} to card {self.__id}.')
            elif attachment['id'] in self.__attachments and self.__attachments[attachment['id']].get_tag() != attachment['ETag']:
                self.__attachments[attachment['id']].update(attachment)
                print(f'[UPDATE] Updated attachment {attachment["id"]} of card {self.__id}.')
            elif attachment['id'] in self.__attachments and attachment['deletedAt'] != 0:
                self.__attachments.pop(attachment['id'])
                print(f'[UPDATE] Removed attachment {attachment["id"]} from card {self.__id}.')
        
        print(f'[UPDATE]: Updated card {self.__id}.')

    def serialize(self, complete: bool = False) -> dict:
        if(complete):
            return {'title': self.__title, 'type': "plain" if self.__type == 0 else "text", 'order': self.__order, 'description': self.__description,
                    'duedate': self.__card_due_time, 'boardId': self.__board_id, 'stackId': self.__stack_id, 'id': self.__id, 'ETag': self.__tag, 
                    'labels': [label.serialize() for label in self.__labels], 'archived': self.__archived, 
                    'commentsUnread': self.__unread_comments_count, 'overdue': self.__overdue, 'createdAt': dt.timestamp(self.__creation_time), 
                    'lastModified': dt.timestamp(self.__last_edited_time), 
                    'deletedAt': None if self.__deletion_time is None else dt.timestamp(self.__deletion_time), 
                    'duedate': None if self.__card_due_time is None else self.__card_due_time.strftime('%Y-%m-%dT%H:%M:%S%z'), 
                    'assignedUsers': self.__assigned_users, 'owner': self.__owner.serialize(), 'lastEditor': self.__last_editor, 
                    'attachmentCount': self.__attachment_count, 'attachments': self.__attachments}
        else:
            return {'title': self.__title, 'type': "plain" if self.__type == 0 else "text", 'order': self.__order, 'description': self.__description,
                'duedate': self.__card_due_time}

    def set_board_id(self, bid: int) -> None:
        self.__board_id = bid

    def set_stack_id(self, sid: int) -> None:
        self.__stack_id = sid

    def set_users_dict(self, users: dict[DeckUser]) -> None:
        self.__users_dict = users
    
    def set_labels_dict(self, labels: dict[DeckLabel]) -> None:
        self.__labels_dict = labels
    
    def set_id(self, id: int) -> None:
        self.__id = id

    def set_tag(self, ETag: str) -> None:
        self.__tag = ETag

    def set_title(self, title: str) -> None:
        self.__title = title
    
    def set_type(self, c_type: str) -> None:
        self.__type = self.__types[c_type]

    def set_order(self, order: int) -> None:
        self.__order = order
    
    def set_description(self, description: str) -> None:
        self.__description = description

    def set_labels(self, labels_dict: dict[DeckLabel]) -> None:
        self.__labels = (None if self.__labels_dict is None else
                         [self.__labels_dict[label.get_tag()] for label in self.__labels_dict.values()])

    def set_unread_comments_count(self, unread_comments_count: int) -> None:
        self.__unread_comments_count = unread_comments_count

    def set_archived(self, archived: bool) -> None:
        self.__archived = archived

    def set_overdue(self, overdue: int) -> None:
        self.__overdue = overdue

    def set_creation_time(self, creation_time: dt) -> None:
        self.__creation_time = dt.fromtimestamp(creation_time).astimezone(tz.utc)

    def set_last_edited_time(self, last_edited_time: dt) -> None:
        self.__last_edited_time = dt.fromtimestamp(last_edited_time).astimezone(tz.utc)

    def set_deletion_time(self, deletion_time: Union[dt, int]) -> None:
        self.__deletion_time = (dt.fromtimestamp(deletion_time).astimezone(tz.utc)
                                if deletion_time != 0 else None)

    def set_card_due_time(self, card_due_time: dt) -> None:
        self.__card_due_time = (None if card_due_time is None else
                                dt.strptime(card_due_time, '%Y-%m-%dT%H:%M:%S%z').astimezone(tz.utc))

    def set_assigned_users(self, assigned_users: dict[DeckUser]) -> None:
        self.__assigned_users = (None if assigned_users is None else
                                 [self.__users_dict[assignee['participant']['uid']] for assignee in assigned_users])

    def set_owner(self, owner: Union[DeckUser, str]) -> None:
        self.__owner = (self.__users_dict[owner['uid']] if isinstance(owner, dict) else
                        self.__users_dict[owner])
    
    def set_last_editor(self, last_editor: Union[DeckUser, str]) -> None:
        self.__last_editor = self.__users_dict[last_editor] if last_editor is not None else None

    def set_attachment_count(self, attachment_count: int) -> None:
        self.__attachment_count = attachment_count

    def set_attachments(self, attachments) -> None:
        self.__attachments = ({attachment['id']: DeckAttachment(attachment, self.__stack_id, self.__board_id, self.__users_dict) for attachment in
                                api.request(f'boards/{bid}/stacks/{self.__stack_id}/cards/{self.__id}/attachments')}
                                if self.__attachment_count is not None and self.__attachment_count > 0 else {})

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

    def get_last_modified_user(self) -> DeckUser:
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
        return self.__attachments.items()

    def get_attachment(self, path: str) -> Optional[DeckAttachment]:
        result = [attachment for attachment in self.get_attachments() if attachment.get_full_name() == path]
        return result[0] if len(result) == 1 else None

    def get_unread_comments_count(self) -> int:
        return self.__unread_comments_count

    def is_assigned(self, user: Union[DeckUser, str]) -> bool:
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

    def is_deleted(self) -> bool:
        return self.__deletion_time is not None

    def is_overdue(self) -> bool:
        return self.__overdue == 1

    def get_id(self) -> int:
        return self.__id

    def get_tag(self) -> str:
        return self.__tag


class DeckStack:
    def __init__(self, stack: dict, labels: dict[DeckLabel], users: dict[DeckUser], api: DeckAPI, updateCards: bool = True) -> None:
        # Internal identifiers for the stack
        self.__board_id = stack['boardId']
        self.__id = stack['id']
        self.__tag = stack['ETag']
        self.__order = stack['order']

        self.__labels_dict = labels
        self.__users_dict = users
        self.__api = api

        self.__last_edited_time = dt.fromtimestamp(stack['lastModified']).astimezone(tz.utc)
        self.__deletion_time = (dt.fromtimestamp(stack['deletedAt']).astimezone(tz.utc)
                                if stack['deletedAt'] is not None and stack['deletedAt'] != 0 else None)

        self.__title = stack['title']
        self.__cards = ({card['id']: DeckCard(card, self.__board_id, labels, users, api) for card in stack['cards'] if card is dict}
                        if 'cards' in stack else {})
        
        print(f'[UPDATE] Created stack {self.__id}.')

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

    def update(self, stack: dict) -> None:
        self.__init__(stack, self.__labels_dict, self.__users_dict, self.__api, updateCards=False)

        if 'cards' not in stack:
            while len(self.__cards) != 0:
                card = self.__cards.popitem()
                print(f'Updating stack #{self.__id}: Removing card #{card.get_id()}.')
            return

        for card in stack['cards']:
            if card['id'] not in self.__cards:
                self.__cards[card['id']] = DeckCard(card, self.__board_id, self.__labels_dict, self.__users_dict, self.__api)
                print(f'[UPDATE] Added card #{card["id"]} to stack #{self.__id}.')
            elif card['id'] in self.__cards and self.__cards[card['id']].get_tag() != card['ETag']:
                self.__cards[card['id']].update(card)
                print(f'[UPDATE] Updated card #{card["id"]} of stack #{self.__id}.')
            elif card['id'] in self.__cards and card['deletedAt'] is not None and card['deletedAt'] != 0:
                self.__cards.pop(card['id'])
                print(f'[UPDATE] Removed card #{card["id"]} from stack #{self.__id}.')
        
        print(f'[UPDATE] Updated stack {self.__id}.')

    def serialize(self, complete: bool = False) -> dict:
        result = {'boardId': self.__board_id, 'id': self.__id, 'ETag': self.__tag, 'order': self.__order, 
                'lastModified': dt.timestamp(self.__last_edited_time),
                'deletedAt': self.__deletion_time, 'title': self.__title, 'cards': [c for c in self.__cards.values()]}

        if complete:
            result | {}

        return result

    def add_card(self, card: DeckCard) -> DeckCard:
        new_card = self.__api.post(f'boards/{self.__board_id}/stacks/{self.__id}/cards', card.serialize())
        
        self.__cards[new_card['id']] = new_card
        self.update(self.serialize())

        print('[UPDATE] Created card {0}.'.format(new_card['id']))

        return self.get_card(new_card['id'])

    def get_title(self) -> str:
        return self.__title

    def get_last_modification_time(self) -> dt:
        return self.__last_edited_time

    def get_deletion_time(self) -> Optional[dt]:
        return self.__deletion_time

    def get_order(self) -> int:
        return self.__order

    def get_cards(self, label: Optional[Union[str, DeckLabel]] = None,
                  assigned: Optional[Union[str, DeckUser]] = None,
                  deleted: Optional[bool] = None) -> list[DeckCard]:
        return sorted(
            [card for card in self.__cards.items() if (not label or card.has_label(label))
             and (not assigned or card.is_assigned(assigned)) and (deleted is None or card.is_deleted() == deleted)],
            key=lambda c: c[1].get_order())

    def get_events(self, past: bool = False) -> list[DeckCard]:
        return sorted([c for c in self.__cards.values() if c.get_due_time() and (past or c.get_due_time() >= dt.now(tz.utc))],
                      key=lambda x: x.get_due_time())

    def get_card(self, cid: int) -> Optional[DeckCard]:
        return self.__cards[cid] if cid in self.__cards else None

    def get_next_event(self) -> Optional[DeckCard]:
        result = self.get_events()
        return result[0] if len(result) > 0 else None

    def get_id(self) -> int:
        return self.__id

    def get_tag(self) -> str:
        return self.__tag


class DeckBoard:
    @unique
    class NotificationType(Enum):
        OFF = 0         # No notifications for events
        ASSIGNED = 1    # Notifications only for events to which the user is assigned
        ALL = 2         # Notifications for all events

    __notification_type = {
        'off': NotificationType.OFF,
        'assigned': NotificationType.ASSIGNED,
        'all': NotificationType.ALL
    }

    def __init__(self, board: dict, api: DeckAPI, updateStacks: bool = True) -> None:
        # Internal identifiers for the board
        self.__id = board['id']
        self.__tag = board['ETag']

        self.__api = api

        # Internal board settings
        self.__permissions = board['permissions']  # Permissions for this user (r,w,share,manage)
        self.__notifications = self.__notification_type[board['settings']['notify-due']]
        self.__synchronize = board['settings']['calendar']  # Whether the board synchronizes with CalDAV

        self.__title = board['title']
        self.__color = board['color']
        self.__labels = {label['ETag']: DeckLabel(label) for label in board['labels']}

        # Users and access control
        self.__users = {user['uid']: DeckUser(user) for user in board['users']}
        self.__owner = self.__users[board['owner']['uid']]

        self.__acl = {acl['participant']['uid']: DeckAcl(acl, self.__users) for acl in board['acl']}

        self.__archived = board['archived']  # Board archived by current user
        self.__shared = board['shared']  # Board shared to the current user (not owned by current user)

        # Timestamps for deletion and last edit. Deletion timestamp is 0 if the board has not been deleted
        self.__deletion_time = (dt.fromtimestamp(board['deletedAt']).astimezone(tz.utc)
                                if board['deletedAt'] != 0 else None)

        self.__last_edited_time = (None if board['lastModified'] == 0
                                   else dt.fromtimestamp(board['lastModified']).astimezone(tz.utc))

        self.__stacks = {stack['id']: DeckStack(stack, self.__labels, self.__users, api)
                         for stack in api.request(f'boards/{self.__id}/stacks')}
        
        print(f'[UPDATE] Created board {self.__id}.')

    def __str__(self) -> str:
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

    def update(self, board: dict) -> None:
        board = self.__api.request(f'boards/{self.__id}')
        self.__init__(board, self.__api, updateStacks=False)

        stacks = api.request(f'boards/{self.__id}/stacks')
        for stack in board['stacks']:
            if stack['id'] not in self.__stacks:
                self.__stacks[stack['id']] = DeckStack(stack, self.__labels, self.__users, api)
            elif stack['id'] in self.__stacks and self.__stacks[stack['id']].get_tag() != stack['ETag']:
                self.__stacks[stack['id']].update(stack)
            elif stack['id'] in self.__stacks and stack['deletedAt'] != 0:
                self.__stacks.pop(stack['id'])
        
        print(f'[UPDATE] Updated board {self.__id}.')

    def add_card(self, sid: int, card: DeckCard) -> DeckCard:
        return self.get_stack(sid).add_card(card)

    def can_read(self, uid: Optional[str] = None) -> bool:
        if not uid:
            return self.__permissions['PERMISSION_READ']
        else:
            return uid in [repr(item.get_principal()) for item in self.__acl]

    def can_edit(self, uid: Optional[str] = None) -> bool:
        if not uid:
            return self.__permissions['PERMISSION_EDIT']
        else:
            return uid in [repr(item.get_principal()) for item in self.__acl if item.can_edit()]

    def can_manage(self, uid: Optional[str] = None) -> bool:
        if not uid:
            return self.__permissions['PERMISSION_MANAGE']
        else:
            return uid in [repr(item.get_principal()) for item in self.__acl if item.can_manage()]

    def can_share(self, uid: Optional[str] = None) -> bool:
        if not uid:
            return self.__permissions['PERMISSION_SHARE']
        else:
            return uid in [repr(item.get_principal()) for item in self.__acl if item.can_share()]

    def is_archived(self) -> bool:
        return self.__archived

    def is_shared(self) -> bool:
        return self.__shared

    def is_calendar_synchronized(self) -> bool:
        return self.__synchronize

    def get_title(self) -> str:
        return self.__title

    def get_color(self) -> str:
        return self.__color

    def get_labels(self) -> list[DeckLabel]:
        return [v for k, v in self.__labels.items()]

    def get_users(self) -> list[DeckUser]:
        return [v for k, v in self.__users.items()]

    def get_user(self, uid: str = None, name: str = None) -> Optional[DeckUser]:
        if uid is not None:
            return self.__users[uid] if uid in self.__users else None
        elif name is not None:
            for k, v in self.__users:
                if k.get_name() == name:
                    return k
            return None
        return None

    def get_acl(self, user: DeckUser) -> Optional[DeckAcl]:
        return self.__acl[user.get_id()] if user.get_id() in self.__acl else None

    def get_owner(self) -> DeckUser:
        return self.__owner

    def get_deletion_time(self) -> Optional[dt]:
        return self.__deletion_time

    def get_last_modification_time(self) -> dt:
        return self.__last_edited_time

    def get_notification_settings(self) -> NotificationType:
        return self.__notifications

    def get_stacks(self) -> list[DeckStack]:
        return sorted(self.__stacks.values(), key=lambda s: s.get_order())

    def get_stack(self, sid: int) -> Optional[DeckStack]:
        result = [item for item in self.__stacks.values() if item.get_id() == sid]
        return result[0] if len(result) == 1 else None

    def get_cards(self, label: Optional[Union[str, DeckLabel]] = None,
                  assigned: Optional[Union[str, DeckUser]] = None,
                  deleted: Optional[bool] = None) -> list[DeckCard]:
        return sorted(
            [card for stack in self.__stacks for card in stack.get_cards()
             if (not label or card.has_label(label)) and (not assigned or card.is_assigned(assigned))
             and (deleted is None or card.is_deleted() == deleted)], key=lambda c: c.get_oder())

    def get_events(self, past: bool = False) -> list[DeckCard]:
        return sorted([c for events in [stack.get_events(past=past) for stack in self.__stacks.values()] for c in events
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
    def __init__(self, domain: str, username: str, password: str, secure: bool) -> None:
        self.__username = username
        self.__password = password
        self.__api = DeckAPI(username, password, domain, secure)

        self.__events = []
        self.__boards = {}
        self.__users = {}

        self.update()

    def __str__(self) -> str:
        return '\n\n'.join([str(board) for board in self.__boards.values()])

    def update(self) -> None:
        # Not handling exception is intentional: let the client handle it according to application
        boards = self.__api.request('boards?details=1')

        for board in boards:
            if board['id'] not in self.__boards:
                self.__boards[board['id']] = DeckBoard(board, self.__api)
            elif board['id'] in self.__boards and self.__boards[board['id']].get_tag() != board['ETag']:
                self.__boards[board['id']].update()
            elif board['id'] in self.__boards and board['deletedAt'] != 0:
                self.__boards.pop(board['id'])
        
        self.__events = sorted([e for ls in [v.get_events(past=True) for k, v in self.__boards.items()] for e in ls],
                               key=lambda x: x.get_due_time())
    
    def new_card(self) -> DeckCard:
        return DeckCard(None, None, None, None, self.__api, False, True)

    def add_card(self, bid: int, sid: int, card: DeckCard) -> DeckCard:
        return self.get_board(bid).add_card(sid, card)

    def get_events(self, past: bool = False) -> list[DeckCard]:
        return [e for e in self.__events if past or e.get_due_time >= dt.now(tz.utc)]

    def get_next_event(self) -> Optional[DeckCard]:
        return self.__events[0]

    def get_cards(self, label: Optional[Union[str, DeckLabel]] = None,
                  assigned: Optional[Union[str, DeckUser]] = None,
                  deleted: Optional[bool] = None) -> list[DeckCard]:
        return sorted(
            [card for board in self.__boards.values() for stack in board.get_stacks() for card in stack.get_cards()
             if (not label or card.has_label(label)) and (not assigned or card.is_assigned(assigned))
             and (deleted is None or card.is_deleted() == deleted)], key=lambda c: c[1].get_order())

    def get_card(self, cid: int) -> Optional[DeckCard]:
        for board in self.get_boards():
            card = board.get_card(cid)
            if card is not None:
                return card
        return None

    def get_boards(self) -> list[DeckBoard]:
        return [v for k, v in self.__boards]

    def get_board(self, bid: int) -> Optional[DeckBoard]:
        for board in self.__boards.values():
            if board.get_id() == bid:
                return board
        return None

    def get_users(self) -> list[DeckUser]:
        return [v for k, v in self.__users]

    def get_user(self, uid: str = None, name: str = None) -> Optional[DeckUser]:
        if uid is not None:
            return self.__users[uid] if uid in self.__users else None
        elif name is not None:
            for k, v in self.__users:
                if k.get_name() == name:
                    return k
            return None
        return None
    
    def request(self, endpoint: str) -> Optional[Union[list, dict]]:
        return self.__api.request(endpoint)
    
    def post(self, endpoint: str, payload: dict) -> Optional[Union[list, dict]]:
        return self.__api.post(endpoint, payload)
    
    def put(self, endpoint: str, payload: dict) -> None:
        self.__api.put(endpoint, payload)

    def delete(self, endpoint: str) -> None:
        self.__api.delete(endpoint)


def testApi(deck: Deck):
    while True:
        while True:
            try:
                oper = int(input('\nChoose operation:\n(1)get\n(2)post\n(3)put\n(4)delete\n: '))
                if oper >= 1 and oper <= 4:
                    break
                else:
                    print(f'Try again')
            except KeyboardInterrupt:
                print()
                exit(1)
            except:
                print(f'Try again')
            
        endpoint = input('> ')

        if oper == 1:
            print(deck.request(endpoint))
        elif oper == 2:
            card_title = input('title: ')
            card_type = input('type: ')
            card_order = int(input('order: '))
            card_description = input('description: ')
            payload_dict = {'title': card_title, 'type': card_type, 'order': card_order, 'description': card_description}
            print(deck.post(endpoint, payload_dict))
        elif oper == 3:
            card_title = input('title: ')
            card_type = input('type: ')
            card_order = int(input('order(int): '))
            card_description = input('description: ')
            payload_dict = {'title': card_title, 'type': card_type, 'order': card_order, 'description': card_description, 
            'duedate': dt.now(tz.utc).isoformat(), 'owner': {'uid': "omgrly"}}
            deck.put(endpoint, payload_dict)
        elif oper == 4:
            deck.delete(endpoint)

# TODO:
# Check the handling of labels
# Check setting types with Type

# Test basic program functionality
if __name__ == '__main__':
    deck_hostname = os.environ.get("OC_DECK_HOST")
    deck_username = os.environ.get('OC_DECK_USER')
    deck_password = os.environ.get('OC_DECK_PASS')
    deck_security = os.environ.get('OC_USE_HTTPS') == 'True'

    deck = Deck(deck_hostname, deck_username, deck_password, deck_security)
    print(deck)

    n_card = deck.new_card()
    n_card.set_title("Best Card Ever")
    n_card.set_type("plain")
    n_card.set_order(999)
    n_card.set_description("Lorem ipsum dolor sit amet, consectetur")
    n_card = deck.add_card(1, 1, n_card)

    print(deck.get_board(1).get_stack(1).get_card(n_card.get_id()))

    #testApi(deck)
    