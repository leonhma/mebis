from html import unescape
from json import loads
from re import search

from requests import Session, Response

from .common.exceptions import LoginError, HTTPError


class UserSession():
    """Class representing the session of an logged-in user.

    Args:
        user (str, required) The username used to sign in.
        pwd (str, required) The password used to sign in.

    Attributes:
        sesskey: (str) The session key. (Made accessible for advanced users)
    """

    def __init__(self, user: str, pwd: str):
        self._login(user, pwd)
        self.helpers = self.Helpers(self)

    def _login(self, user, pwd):
        self._session = Session()
        # fill up cookie jar
        r = self.get('https://lernplattform.mebis.bayern.de')
        # sign in to get session tokens
        nexturl = 'https://idp.mebis.bayern.de'\
            + search(r'(?<=action=\").*?(?=\")', r.text).group(0)
        r = self.post(nexturl, data={'j_username': user,
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
        r = self.post(nexturl, data={'RelayState': rs,
                                     'SAMLResponse': saml})
        # get sesskey
        self.sesskey = search(r'(?<=sesskey\"\:\").*?(?=\")', r.text).group(0)

    def get(self, *args, **kwargs):
        """Make a GET request in the context of the user's session.
            (Made accessible for advanced users.)

        Raises:
            HTTPError: If the request was answered with an error.

        Note: This a wrapper around :func:`requests.get`.
            [docs here](https://docs.python-requests.org/en/master/api/)
        """
        r = self._session.get(*args, **kwargs)
        if r.status_code >= 400:
            raise HTTPError(r)
        return r

    def post(self, *args, **kwargs):
        """Make a POST request in the context of the user's session.
            (Made accessible for advanced users.)

        Raises:
            HTTPError: If the request was answered with an error.

        Note: This a wrapper around :func:`requests.post`.
            [docs here](https://docs.python-requests.org/en/master/api/)
        """
        r = self._session.post(*args, **kwargs)
        if r.status_code >= 400:
            raise HTTPError(r)
        return r

    def ajax(self, method: str, args: dict) -> Response:
        """Make an request to the ajax endpoint of mebis.
            (Made accessible for advanced users.)

        Args:
            method (str, required): The identifier of the method.
            args (dict, required): The arguments to the method.

        Returns:
            Response: The reponse of the request.
        """
        # TODO add documentation
        r = self.post(
            'https://lernplattform.mebis.bayern.de/lib/ajax/service.php',
            params={'sesskey': self.sesskey},
            json=[{"index": 0, "methodname": method, "args": args}])
        return r.json()

    class Helpers():
        def __init__(self, sess):
            self.post = sess.post
            self.get = sess.get
            self.ajax = sess.ajax
            self.sesskey = sess.sesskey

        def make_survey_choice(self,
                               survey_id: int | str,
                               choice_id: int | str) -> bool:
            """Helper for making survey choices.

            Args:
                survey_id (str | int, required) The id of the survey.
                    (Can be found in the url when looking at the survey.)
                choice_id (str | int, required) The id of your choice.
                    (Can be found through the devtools inspector.)

            Returns:
                bool: True if choice was succesfully set, False otherwise
            """

            r = self.post('https://lernplattform.mebis.bayern.de/'
                          + 'mod/choice/view.php',
                          {'answer': choice_id, 'sesskey': self.sesskey,
                           'action': 'makechoice', 'id': survey_id},
                          allow_redirects=False)
            return True if 'location' in r.headers else False
