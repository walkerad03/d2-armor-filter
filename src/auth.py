import base64
import datetime
import json
import os
import threading
import webbrowser
from datetime import timedelta

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from dotenv import load_dotenv
from flask import Flask, request


class BungieOAuth:
    def __init__(self, cert_filepath, key_filepath):
        self.cert_filepath = cert_filepath
        self.key_filepath = key_filepath

        load_dotenv()

        self.bungie_api_key = os.getenv("BUNGIE_API_KEY")
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")

        self.authorization_url = f"https://www.bungie.net/en/OAuth/Authorize?client_id={self.client_id}&response_type=code"
        self.redirect_url = "https://localhost:7777/callback"
        self.token_url = "https://www.bungie.net/platform/app/oauth/token"

        self.auth_token_filepath = os.path.join("data", "oauth_token.json")

        self.app = Flask(__name__)
        self._auth_code_callback_event = threading.Event()
        self._flask_thread = threading.Thread(target=self._run_flask_app, daemon=True)

        self.auth_code = None
        self._configure_callback_route()

    def _configure_callback_route(self):
        @self.app.route("/callback", methods=["GET"])
        def handle_callback():
            global auth_code
            auth_code = request.args.get("code")
            self._auth_code_callback_event.set()
            return "You can close this window.", 200

    def _run_flask_app(self):
        ssl_dir_path = os.path.join("data", "ssl")

        if not os.path.exists(ssl_dir_path):
            os.makedirs(ssl_dir_path)

        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "North Carolina"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Chapel Hill"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SelfSigned Inc."),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc) + timedelta(days=365)
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        with open(os.path.join(ssl_dir_path, "localhost.key"), "wb") as f:
            f.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        with open(os.path.join(ssl_dir_path, "localhost.crt"), "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        self.app.run(
            port=7777,
            ssl_context=(
                os.path.join(ssl_dir_path, "localhost.crt"),
                os.path.join(ssl_dir_path, "localhost.key"),
            ),
            debug=True,
            use_reloader=False,
        )

    def authenticate(self):
        if not os.path.exists(self.auth_token_filepath):
            token_data = self._get_access_token()
        else:
            with open(self.auth_token_filepath, "r") as f:
                token_data = json.load(f)

        access_expires_at = datetime.datetime.fromisoformat(
            token_data["access_expires_at"].rstrip("Z")
        )
        refresh_expires_at = datetime.datetime.fromisoformat(
            token_data["refresh_expires_at"].rstrip("Z")
        )

        access_expired = (
            datetime.datetime.now(datetime.timezone.utc) >= access_expires_at
        )
        refresh_expired = (
            datetime.datetime.now(datetime.timezone.utc) >= refresh_expires_at
        )

        refresh_token = token_data["refresh_token"]

        if access_expired and not refresh_expired:
            token_data = self._refresh_token(refresh_token)
        elif refresh_expired:
            token_data = self._get_access_token()

        return token_data["access_token"]

    def _get_access_token(self):
        self._flask_thread.start()

        webbrowser.open(self.authorization_url)

        self._auth_code_callback_event.wait()

        auth_string = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {"grant_type": "authorization_code", "code": auth_code}

        res = requests.post(self.token_url, headers=headers, data=data)

        res_json = res.json()

        now = datetime.datetime.now(datetime.timezone.utc)
        access_expires_at = now + timedelta(seconds=res_json["expires_in"])
        refresh_expires_at = now + timedelta(seconds=res_json["refresh_expires_in"])

        res_json["access_expires_at"] = access_expires_at.isoformat() + "Z"
        res_json["refresh_expires_at"] = refresh_expires_at.isoformat() + "Z"

        with open(self.auth_token_filepath, "w") as f:
            json.dump(res_json, f, indent=2)

        return res_json

    def _refresh_token(self, refresh_token):
        auth_string = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {"grant_type": "refresh_token", "refresh_token": refresh_token}

        res = requests.post(self.token_url, headers=headers, data=data)

        res_json = res.json()

        now = datetime.datetime.now(datetime.timezone.utc)
        access_expires_at = now + timedelta(seconds=res_json["expires_in"])
        refresh_expires_at = now + timedelta(seconds=res_json["refresh_expires_in"])

        res_json["access_expires_at"] = access_expires_at.isoformat() + "Z"
        res_json["refresh_expires_at"] = refresh_expires_at.isoformat() + "Z"

        with open(self.auth_token_filepath, "w") as f:
            json.dump(res_json, f, indent=2)

        return res_json
