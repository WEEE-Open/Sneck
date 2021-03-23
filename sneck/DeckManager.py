from typing import Optional

from Deck import Deck,DeckBoard,DeckStack,DeckCard
from threading import Thread,Condition
from datetime import datetime


class DeckManager:
    def __init__(self, domain: str, username: str, password: str, ssl: bool, cooldown: int, callback):
        self.__deck = Deck(domain, username, password, ssl)

        # Thread locks
        self.__update_lock = Condition()
        self.__notify_lock = Condition()
        self.__nevent_lock = Condition()
        self.__access_lock = Condition()

        self.__next_event = None

        # Do all the timed checks in two separate threads
        self.__update_thread = Thread(target=self.__update, args=(cooldown,), daemon=True)
        self.__events_thread = Thread(target=self.__events, args=(callback,), daemon=True)

        self.__update_thread.start()
        self.__events_thread.start()

    def update(self):
        self.__update_lock.notify()

    def __update(self, cooldown: int):
        print('Updating...')
        self.__update_lock.acquire()

        while True:
            self.__deck.download()

            if self.__next_event is not None:
                old_date = datetime.strptime(self.__next_event.date, '%Y-%m-%dT%H:%M:%S%z')
            else:
                old_date = None


            self.__nevent_lock.acquire()
            self.__next_event_card = self.__deck.next_event
            self.__nevent_lock.release()

            if self.__next_event is not None:
                new_date = datetime.strptime(self.__next_event.date, '%Y-%m-%dT%H:%M:%S%z')
            else:
                new_date = None

            if old_date and new_date and new_date < old_date:
                self.__notify_lock.notify()

            self.__update_lock.wait(cooldown)

    def __events(self, callback):
        self.__notify_lock.acquire()

        while True:
            if self.__next_event is not None:
                delay = (datetime.now() - datetime.strptime(self.__next_event.date, '%Y-%m-%dT%H:%M:%S%z')).seconds
                self.__notify_lock.wait(delay)
            else:
                self.__notify_lock.wait()

            if datetime.now == self.get_next_reminder():
                callback(self.get_next_card())


def callback(card: DeckCard):
    pass


# Test basic program functionality
if __name__ == '__main__':
    import os,time

    hostname = os.environ.get("OC_DECK_HOST")
    username = os.environ.get('OC_DECK_USER')
    password = os.environ.get('OC_DECK_PASS')
    security = os.environ.get('OC_USE_HTTPS') == 'True'

    manager = DeckManager(hostname, username, password, security, 30, callback)

    while True:
        time.sleep(9999999)
