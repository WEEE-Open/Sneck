from typing import Optional

from Deck import Deck, DeckBoard, DeckStack, DeckCard
from threading import Thread, Condition
from datetime import datetime, timezone
import logging


class DeckManager:
    def __init__(self, domain: str, username: str, password: str, ssl: bool, cooldown: int, callback):
        self.__deck = Deck(domain, username, password, ssl)

        # Thread locks
        self.__update_lock = Condition()
        self.__notify_lock = Condition()
        self.__nevent_lock = Condition()
        self.__access_lock = Condition()

        # Do all the timed checks in two separate threads
        self.__update_thread = Thread(target=self.__update, args=(cooldown,), daemon=True)
        self.__events_thread = Thread(target=self.__events, args=(callback,), daemon=True)

        self.__update_thread.start()
        self.__events_thread.start()

    def update(self):
        self.__update_lock.notify()

    def __update(self, cooldown: int):
        logging.info('[UT] Starting update thread...')
        self.__update_lock.acquire()
        logging.debug('[UT] Acquired update lock.')

        while True:
            self.__update_lock.wait(cooldown)

            prev = self.__deck.get_next_event()

            logging.debug('[UT] Downloading deck data from server...')
            self.__deck.download()
            logging.debug('[UT] Downloaded deck data from server.')

            curr = self.__deck.get_next_event()

            if (not prev and curr) or (curr and not prev) or (curr and curr.card_due_time != prev.card_due_time):
                logging.info(f'[UT] Next event {f"changed to {curr}" if curr else "got deleted"}.')
                self.__notify_lock.acquire()
                self.__notify_lock.notify()
                self.__notify_lock.release()

    def __events(self, callback):
        self.__notify_lock.acquire()

        while True:
            if self.__deck.next_event is not None:
                print(f'Waiting for next event at {self.__deck.next_event.card_due_time}')
                delay = (self.__deck.next_event.card_due_time - datetime.now(timezone.utc)).seconds
                logging.debug(f'[NT] Waiting on notification lock with delay of {delay} seconds.')
                self.__notify_lock.wait(delay)
            else:
                self.__notify_lock.wait()

            if datetime.now == self.__deck.next_event.card_due_time:
                callback(self.get_next_card())


def c(card: DeckCard):
    pass


# Test basic program functionality
if __name__ == '__main__':
    import os
    import time

    hostname = os.environ.get("OC_DECK_HOST")
    username = os.environ.get('OC_DECK_USER')
    password = os.environ.get('OC_DECK_PASS')
    security = os.environ.get('OC_USE_HTTPS') == 'True'

    logging.basicConfig(level=logging.DEBUG)
    manager = DeckManager(hostname, username, password, security, 30, c)

    while True:
        time.sleep(9999999)
