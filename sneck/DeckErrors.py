from enum import Enum


class DeckAPIRequestError(Exception):
    """
    When an API request to Deck's REST API fails. Reasons can be multiple:

    - Connection failure
    - Timeout
    - Invalid HTTP response
    - Status code is not 2xx
    - Data type is not application/json (maybe the request is invalid and we got redirected to an error page)
    """
    class Reason(Enum):
        TIMEOUT = 1
        CONNECTION = 2
        RESPONSE = 3

    def __init__(self, reason: Reason, status: int, text: str):
        self.reason = reason
        self.status = status
        self.text = text
