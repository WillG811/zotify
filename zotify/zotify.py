import json
from pathlib import Path
import time
import requests
from librespot.audio.decoders import VorbisOnlyAudioQuality
from librespot.core import Session
from librespot.mercury import MercuryRequests
from librespot.oauth import OAuth

from zotify.const import TYPE, \
    PREMIUM, USER_READ_EMAIL, OFFSET, LIMIT, \
    PLAYLIST_READ_PRIVATE, USER_LIBRARY_READ, USER_FOLLOW_READ
from zotify.config import Config

OAUTH_REDIRECT_URL = 'http://127.0.0.1:5588/login'
OAUTH_SUCCESS_PAGE = '<h2>Login OK. You can close this tab.</h2>'

RATE_LIMIT_FIRST_WAIT = 10
RATE_LIMIT_MAX_WAIT = 600
RATE_LIMIT_MAX_RETRIES = 10

class Zotify:    
    SESSION: Session = None
    DOWNLOAD_QUALITY = None
    CONFIG: Config = Config()

    def __init__(self, args):
        Zotify.CONFIG.load(args)
        Zotify.login(args)

    @classmethod
    def login(cls, args):
        """ Authenticates with Spotify via OAuth and saves credentials to a file """

        cred_location = str(Config.get_credentials_location())

        if Path(cred_location).is_file():
            try:
                conf = Session.Configuration.Builder().set_store_credentials(False).build()
                cls.SESSION = Session.Builder(conf).stored_file(cred_location).create()
                return
            except RuntimeError:
                pass

        if Config.get_save_credentials():
            conf = Session.Configuration.Builder().set_stored_credential_file(cred_location).build()
        else:
            conf = Session.Configuration.Builder().set_store_credentials(False).build()
        builder = Session.Builder(conf)
        builder.login_credentials = OAuth(
            MercuryRequests.keymaster_client_id, OAUTH_REDIRECT_URL, cls.print_oauth_url
        ).set_success_page_content(OAUTH_SUCCESS_PAGE).flow()
        cls.SESSION = builder.create()

    @staticmethod
    def print_oauth_url(url):
        print(f'OAUTH_URL {url}', flush=True)
        print('Open the link above in your browser to log in to Spotify.', flush=True)

    @classmethod
    def get_content_stream(cls, content_id, quality):
        return cls.SESSION.content_feeder().load(content_id, VorbisOnlyAudioQuality(quality), False, None)

    @classmethod
    def __get_auth_token(cls):
        return cls.SESSION.tokens().get_token(
            USER_READ_EMAIL, PLAYLIST_READ_PRIVATE, USER_LIBRARY_READ, USER_FOLLOW_READ
        ).access_token

    @classmethod
    def get_auth_header(cls):
        return {
            'Authorization': f'Bearer {cls.__get_auth_token()}',
            'Accept-Language': f'{cls.CONFIG.get_language()}',
            'Accept': 'application/json',
            'app-platform': 'WebPlayer'
        }

    @classmethod
    def get_auth_header_and_params(cls, limit, offset):
        return {
            'Authorization': f'Bearer {cls.__get_auth_token()}',
            'Accept-Language': f'{cls.CONFIG.get_language()}',
            'Accept': 'application/json',
            'app-platform': 'WebPlayer'
        }, {LIMIT: limit, OFFSET: offset}

    @classmethod
    def api_get(cls, url, headers, params=None):
        """ GET that waits and retries when Spotify answers 429 (rate limited) """
        # we need to import that here, otherwise we will get circular imports!
        from zotify.termoutput import Printer, PrintChannel
        wait = RATE_LIMIT_FIRST_WAIT
        for attempt in range(RATE_LIMIT_MAX_RETRIES):
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 429:
                return response
            retry_after = response.headers.get('Retry-After', '')
            delay = int(retry_after) + 1 if retry_after.isdigit() else wait
            if delay > RATE_LIMIT_MAX_WAIT:
                raise RuntimeError(f'Spotify rate limit: asked to wait {delay}s, giving up. Try again later.')
            Printer.print(PrintChannel.WARNINGS, f'Spotify rate limit (429), waiting {delay}s ({attempt + 1}/{RATE_LIMIT_MAX_RETRIES})...')
            time.sleep(delay)
            wait = min(wait * 2, RATE_LIMIT_MAX_WAIT)
        return response

    @classmethod
    def invoke_url_with_params(cls, url, limit, offset, **kwargs):
        headers, params = cls.get_auth_header_and_params(limit=limit, offset=offset)
        params.update(kwargs)
        resp = cls.api_get(url, headers, params).json()
        if 'error' in resp:
            raise RuntimeError(f"Spotify API Error ({resp['error'].get('status')}): {resp['error'].get('message')} [{url}]")
        return resp

    @classmethod
    def invoke_url(cls, url, tryCount=0):
        # we need to import that here, otherwise we will get circular imports!
        from zotify.termoutput import Printer, PrintChannel
        headers = cls.get_auth_header()
        response = cls.api_get(url, headers)
        responsetext = response.text
        try:
            responsejson = response.json()
        except json.decoder.JSONDecodeError:
            responsejson = {"error": {"status": "unknown", "message": "received an empty response"}}

        if not responsejson or 'error' in responsejson:
            if tryCount < (cls.CONFIG.get_retry_attempts() - 1):
                Printer.print(PrintChannel.WARNINGS, f"Spotify API Error (try {tryCount + 1}) ({responsejson['error']['status']}): {responsejson['error']['message']}")
                time.sleep(5)
                return cls.invoke_url(url, tryCount + 1)

            Printer.print(PrintChannel.API_ERRORS, f"Spotify API Error ({responsejson['error']['status']}): {responsejson['error']['message']}")

        return responsetext, responsejson

    @classmethod
    def check_premium(cls) -> bool:
        """ If user has spotify premium return true """
        return (cls.SESSION.get_user_attribute(TYPE) == PREMIUM)
