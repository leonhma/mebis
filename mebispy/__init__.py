from datetime import date
from html import unescape
from re import search
from time import strftime
from typing import Union

from requests import Response, Session


debug = False
"""Flag indicating whether varbose messages should be used.
Can be set via :func:`set_debug`
"""


def set_debug(val: bool):
    """Setter for the value of 'debug'.
    Enables verbose errors and debug messages.

    Args:
        val (bool, required): The value to set 'debug' to.
    """
    global debug
    debug = val


class UserSession():
    """Class representing the session of a logged-in user.

    Args:
        user (str, required): The username used to sign in.
        pwd (str, required): The password used to sign in.

    Raises:
        LoginError: If the login failed.

    Attributes:
        sesskey (str): The session key (one of them at least).
        userid (str): The user id.
    """

    def __init__(self, user: str, pwd: str):
        self._login(user, pwd)

    def _login(self, user, pwd):
        if debug:
            log(f'Logging in user "{user}".')
            log('Creating session...')
        self._session = Session()
        if debug:
            log('Getting session tokens.')
        # fill up cookie jar
        r = self._session.get('https://lernplattform.mebis.bayern.de')
        # sign in to get session tokens
        nexturl = 'https://idp.mebis.bayern.de'\
            + search(r'(?<=action=\").*?(?=\")', r.text).group(0)
        r = self._session.post(nexturl, data={'j_username': user,
                                              'j_password': pwd,
                                              '_eventId_proceed': ''})
        if 'form-error' in r.text:
            raise LoginError(self._user)
        # complete full signin
        nexturl = unescape(search(r'(?<=action=\").*?(?=\")', r.text).group(0))
        rs = unescape(search(r'(?<=name=\"RelayState\" value=\").*?(?=\")',
                             r.text).group(0))
        saml = search(r'(?<=name=\"SAMLResponse\" value=\").*?(?=\")',
                      r.text).group(0)
        r = self._session.post(nexturl, data={'RelayState': rs,
                                              'SAMLResponse': saml})
        if debug:
            log('Logged in.')
        # get sesskey
        self.sesskey = search(r'(?<=sesskey\"\:\").*?(?=\")', r.text).group(0)
        self.userid = search(r'(?<=data-userid\=\").*?(?=\")', r.text).group(0)

    def get(self, *args, **kwargs) -> Response:
        """Make a GET request in the context of the user's session.

        Raises:
            HTTPError: If the request was answered with an error.

        Note:
            This a wrapper around :func:`requests.get`.
            `docs here
            <https://docs.python-requests.org/en/master/api/#requests.get>`_
        """
        if debug:
            log(f'Getting request: {args} {kwargs}')
        r = self._session.get(*args, **kwargs)
        if r.status_code >= 400:
            raise HTTPError(r)
        return r

    def post(self, *args, **kwargs) -> Response:
        """Make a POST request in the context of the user's session.

        Raises:
            HTTPError: If the request was answered with an error.

        Note:
            This a wrapper around :func:`requests.post`.
            `docs here
            <https://docs.python-requests.org/en/master/api/#requests.post>`_
        """
        if debug:
            log(f'Posting request: {args} {kwargs}')
        r = self._session.post(*args, **kwargs)
        if r.status_code >= 400:
            raise HTTPError(r)
        return r

    def ajax(self, method: str, args: dict) -> dict:
        """Make a request to the ajax endpoint of mebis.

        Args:
            method (str, required): The identifier of the method.
            args (dict, required): The arguments to the method.

        Raises:
            ActionFailedError: If the response indicates an error.

        Returns:
            dict: The reponse data of the request in json form.
        """
        if debug:
            log(f'Posting ajax "{method}": {args}')
        # TODO add documentation
        r = self.post(
            'https://lernplattform.mebis.bayern.de/lib/ajax/service.php',
            params={'sesskey': self.sesskey},
            json=[{"methodname": method, "args": args}]).json()[0]
        if r['error'] is True:
            raise ActionFailedError(
                'The ajax request failed. Check for spelling errors or take a'
                + ' look at the docs.')
        return r['data']

    def make_survey_choice(self,
                           survey_id: Union[int, str],
                           choice_id: Union[int, str]) -> bool:
        """Helper for making survey choices.

        Args:
            survey_id (str | int, required) The id of the survey.
                (Can be found in the url when looking at the survey.)
            choice_id (str | int, required) The id of your choice.
                (Can be found through the devtools inspector.)

        Returns:
            bool: `True` if choice was succesfully set, `False` otherwise
        """
        if debug:
            log(f'Making survey choice {choice_id}'
                + f' to survey {survey_id}...')
        try:
            r = self._session.post('https://lernplattform.mebis.bayern.de/'
                                   + 'mod/choice/view.php',
                                   {'answer': choice_id,
                                    'sesskey': self.sesskey,
                                    'action': 'makechoice', 'id': survey_id},
                                   allow_redirects=False)
        except HTTPError:
            if debug:
                log('Making choice failed.')
            return False
        if 'location' in r.headers:
            if debug:
                log('Made choice.')
            return True
        if debug:
            log('Making choice failed.')
        return False


def log(msg: str):
    print(f'[mebispy:DEBUG, {strftime(r"%X")}] {msg}')


class LoginError(Exception):
    def __init__(self, username: str):
        self._username = username
        super().__init__(f'Error during login for user "{username}".'
                         + ' Most likely the password is incorrect.')


class ActionFailedError(Exception):
    def __init__(self, message='Action failed to complete.'):
        super().__init__(message)


class HTTPError(Exception):  # Craft more sophisticated messages.
    def __init__(self, r: Response):
        c = r.status_code
        t = date.today()
        a = None
        if t.strftime(r'%d-%m') == '01-04':
            a = str(int(t.strftime(r'%Y')) - 1998)
            o = ('st' if a.endswith('1') else
                 'nd' if a.endswith('2') else
                 'rd' if a.endswith('3') else
                 'th')
        t = (r.headers['Retry-After'] if 'Retry-After' in r.headers
             else None)
        m = ('Bad request. The server could not understand the'
             ' request due to invalid syntax.'
             if c == 400 else
             'Unauthorized. The client lacked authentication.'
             if c == 401 else
             'Forbidden. The client authorized to the server but'
             ' does not have the rights to access this resource.'
             if c == 403 else
             'Not found. The requested resource could not be found'
             ' on this server.'
             if c == 404 else
             'Method not allowed. The request mothod has been disabled'
             ' by the server. Most likely POST was used wrongly.'
             if c == 405 else
             'Not acceptable. The content type set in the request'
             ' headers can not be matched by the server.'
             if c == 406 else
             'Proxy authentication required. The cllient did not'
             ' authorize (correctly). Authorization should be done by'
             ' a proxy.'
             if c == 407 else
             'Request timeout. The connection to the server has been'
             ' inactive for too long.'
             if c == 408 else
             'Conflict. The request conflicted with the current state'
             ' of the server.'
             if c == 409 else
             'Gone. The requested resource has been deleted from the'
             ' server.'
             if c == 410 else
             'Length required. Header field "Content-Length" is'
             ' missing.'
             if c == 411 else
             'Precontidion failed. The client has indicated conditions'
             ' in the headers, which the server does not meet.'
             if c == 412 else
             'Payload too large. The request payload is too large.'
             if c == 413 else
             'URI too long. The URI specified is too long for the'
             ' server to interpret.'
             if c == 414 else
             'Unsupported media type. The requested media type is not'
             ' supported by the server.'
             if c == 415 else
             'The range specified in the "Range" header field could'
             ' not be satisfied.'
             if c == 416 else
             'Expactation failed. The expectation present in the'
             ' "Expect" header field could not be met.'
             if c == 417 else
             'I´m a teapot. The server did not wish to fulfill this'
             ' request.'
             if c == 418 and not a else
             f'I´m a teapot. Happy 1st of April and {a}{o}'
             ' anniversary of the Hyper Text Coffee Pot Control'
             ' Protocol!'
             if c == 418 else
             'Misdirected request. The request was sent to a server is'
             ' not able to create a response to your request.'
             if c == 421 else
             'Unprocessable entity. The request could not be processed'
             ' due to semantic errors.'
             if c == 422 else
             'Locked. The resource you are trying to access is locked.'
             if c == 423 else
             'Failed Dependency. The request failed due to failure of'
             ' a previous request.'
             if c == 424 else
             'Upgrade required. The server refuses to perform the'
             ' request using the current protocol but might be willing'
             ' to do so after the client upgrades to one of these'
             f' protocols: {r.headers["Upgrade"]}'
             if c == 426 else
             'Precondition required. The client has to indicate'
             ' preconditions in the headers.'
             if c == 428 else
             'Too many requests. The user has sent too many requests'
             ' in a given amount of time ("rate limiting").'
             if c == 429 else
             'Request header fields too large. The client has sent too'
             'many headers.'
             if c == 431 else
             'Unavailable for legal reasons. The requested resource'
             ' cannot legally be provided, such as a web page censored by'
             ' a government.'
             if c == 451 else
             'Internal server error. The server has encountered a'
             'situation it doesn´t know how to handle.'
             if c == 500 else
             'Not implemented. The request method is not supported by'
             ' the server and cannot be handled.'
             if c == 501 else
             'Bad gateway. The server working as a gateway got a bad'
             ' response.'
             if c == 502 else
             ('Service unavailable. The server is not currently able to'
              ' respond due to maintenance, overload, etc.'
              f' Try again after {t}.' if t else '')
             if c == 503 else
             'Gateway timeout. The server requested by the gateway did'
             ' not respond in time.'
             if c == 504 else
             'Internal configuration error.'
             if c == 506 else
             'Insufficient storage. The request could not be met'
             ' because of insufficient storage on the server side.'
             if c == 507 else
             'Loop detected. The server stopped processing the request'
             ' since it detected an infinite loop.'
             if c == 508 else
             'Not extended. The request must be extended for the'
             ' server to fulfill it.'
             if c == 510 else
             'Network authentication required. The client need to'
             ' authenticate to access the network.'
             if c == 511 else
             'Unknown error.')
        msg = f'"{r.url}" responded with: ' if debug else ''
        msg += ('Client error,' if c < 500 else
                'Server error,' if c < 600 else
                'Unknown,')
        super().__init__(f'{msg} {c}: {m} If this issue persists,'
                         + ' please open an issue in the GitHub repository.')
