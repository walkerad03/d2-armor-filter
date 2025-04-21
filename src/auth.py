from flask import Flask, request
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv
import os
import json
import threading
import webbrowser


class BungieAuth:
    def __init__(self):
        load_dotenv()

        self.api_key = os.getenv("BUNGIE_API_KEY")
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")

        self.redirect_url = "https://localhost:7777/callback"
        self.base_auth_url = "https://www.bungie.net/en/OAuth/Authorize"
        self.token_url = "https://www.bungie.net/platform/app/oauth/token/"
        self.token_file = "data/oauth_token.json"

        self.app = Flask(__name__)
        self.auth_token = {}
        self.auth_session = None

        self.app.add_url_rule("/callback", "callback", self.callback)

        self.init_auth_session()

    def load_token(self):
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                return json.load(f)
        return None

    def save_token(self, token):
        with open(self.token_file, "w") as f:
            json.dump(token, f)

    def run_flask(self):
        self.app.run(ssl_context=("ssl/localhost.crt", "ssl/localhost.key"), port=7777)

    def callback(self):
        global auth_token
        full_url = request.url

        if not os.path.exists("data"):
            os.makedirs("data")

        auth_token = self.auth_session.fetch_token(
            token_url=self.token_url,
            authorization_response=full_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

        self.save_token(auth_token)

        shutdown = request.environ.get("werkzeug.server.shutdown")
        if shutdown:
            shutdown()

        return "Authorization complete. You can close this tab."

    def init_auth_session(self):
        token_data = self.load_token()

        if token_data:
            self.auth_session = OAuth2Session(
                client_id=self.client_id,
                token=token_data,
                auto_refresh_url=self.token_url,
                auto_refresh_kwargs={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                token_updater=self.save_token,
            )
        else:
            self.auth_session = OAuth2Session(
                client_id=self.client_id, redirect_uri=self.redirect_url
            )
            auth_url, state = self.auth_session.authorization_url(self.base_auth_url)

            flask_thread = threading.Thread(target=self.run_flask)
            flask_thread.start()

            print("Opening browser for authorization...")
            webbrowser.open(auth_url)

            flask_thread.join()
            print("Token acquired and saved.")

    def get_membership_for_user(self):
        additional_headers = {"X-API-Key": self.api_key}
        user_details_endpoint = (
            "https://www.bungie.net/Platform/User/GetMembershipsForCurrentUser/"
        )
        response = self.auth_session.get(
            url=user_details_endpoint, headers=additional_headers
        )

        data = response.json()["Response"]
        primary_mem_id = data["primaryMembershipId"]

        mem_type, mem_id = None, None

        for membership in data["destinyMemberships"]:
            if membership["membershipId"] == primary_mem_id:
                mem_id = membership["membershipId"]
                mem_type = membership["membershipType"]
                break

        return mem_id, mem_type

    def query_protected_endpoint(self, endpoint: str):
        additional_headers = {"X-API-Key": self.api_key}
        res = self.auth_session.get(url=endpoint, headers=additional_headers)

        return res.json()
