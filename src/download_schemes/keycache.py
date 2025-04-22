import dataclasses
import hashlib
import json
import logging
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from rauth import OAuth1Service, OAuth1Session

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class KeyCache:
    secrets_file: Path
    host_config_file: Path
    cache_file: Path

    __logged_in_session: dict[str, requests.Session] = dataclasses.field(
        default_factory=dict
    )

    def __post_init__(self):
        self.__secrets: dict[str, dict[str, dict[str, str]]] = self.load_secrets()
        self.__host_config: dict[str, dict[str, str | dict[str, str]]] = self.load_config(self.host_config_file)
        self.__cache: dict[str, dict[str, dict[str, str]]] = self.load_cache()
        self.__initialize_cache_from_secrets()

    @staticmethod
    def __is_bigsdb(host: str) -> bool:
        return host in ["pubmlst", "pasteur"]

    def __initialize_cache_from_secrets(self):
        for host, host_data in self.__secrets.items():
            if host not in self.__cache:
                self.__cache[host] = {}
            for key_type, key_data in host_data.items():
                if key_type not in ["user", "consumer"]:
                    self.__cache[host][key_type] = key_data
        self.save_cache()

    def load_secrets(self) -> dict[str, dict[str, dict[str, str]]]:
        if not self.secrets_file.exists():
            raise FileNotFoundError(f"Secrets file not found: {self.secrets_file}")
        with open(self.secrets_file, "r") as f:
            return json.load(f)

    def load_cache(self) -> dict[str, dict[str, dict[str, str]]]:
        if not self.cache_file.exists():
            return {}
        with open(self.cache_file, "r") as f:
            return json.load(f)

    def save_cache(self) -> None:
        with open(self.cache_file, "w") as f:
            json.dump(self.__cache, f, indent=2)

    def get_key(self, key_type: str, host: str) -> tuple[str, str] | None:
        if not self.__is_bigsdb(host):
            return None
        if key_type in ["user", "consumer"]:
            if host not in self.__secrets or key_type not in self.__secrets[host]:
                raise KeyError(f"{key_type.capitalize()} for {host} not found in secrets file")
            return self.__secrets[host][key_type]["TOKEN"], self.__secrets[host][key_type]["TOKEN SECRET"]
        else:
            if host in self.__cache and key_type in self.__cache[host]:
                return self.__cache[host][key_type]["TOKEN"], self.__cache[host][key_type]["TOKEN SECRET"]
            return None

    def set_key(self, key_type: str, host: str, token: str, token_secret: str) -> None:
        if key_type in ["user", "consumer"]:
            logger.warning(f"Attempt to set {key_type} token for {host} ignored.")
            return
        if host not in self.__cache:
            self.__cache[host] = {}
        self.__cache[host][key_type] = {"TOKEN": token, "TOKEN SECRET": token_secret}
        self.save_cache()

    def delete_key(self, key_type: str, host: str) -> None:
        if key_type in ["user", "consumer"]:
            logger.warning(f"Attempt to delete {key_type} token for {host} ignored.")
            return
        else:
            if host in self.__cache and key_type in self.__cache[host]:
                del self.__cache[host][key_type]
                self.save_cache()

    def get_user_credentials(self, host: str) -> tuple[str, str]:
        return self.get_key("user", host)

    def get_consumer_key(self, host: str) -> tuple[str, str]:
        return self.get_key("consumer", host)

    def get_request_key(self, host: str, database: str) -> tuple[str, str] | None:
        key = self.get_key("request", host)
        if key is None:
            key = self.fetch_request_key(host, database)
            if key:
                self.set_key("request", host, key[0], key[1])
        return key

    def get_session_key(self, host: str, database: str) -> tuple[str, str] | None:
        key = self.get_key("session", host)
        if key is None:
            key = self.fetch_session_key(host, database)
            if key:
                self.set_key("session", host, key[0], key[1])
        return key

    def get_access_key(self, host: str, database: str) -> tuple[str, str] | None:
        key = self.get_key("access", host)
        if key is None:
            key = self.fetch_access_key(host, database)
            if key:
                self.set_key("access", host, key[0], key[1])
        return key

    def fetch_request_key(self, host: str, database: str) -> tuple[str, str]:
        logger.debug(f"Fetching request key for {host}...")
        consumer_key = self.get_consumer_key(host)
        service = create_oauth_service(
            consumer_key, self.__host_config[host]["REST_URL"], database
        )
        try:
            r = service.get_raw_request_token(params={"oauth_callback": "oob"})
            if r.status_code == 200:
                token = r.json()["oauth_token"]
                secret = r.json()["oauth_token_secret"]
                logger.debug(f"Request Token: {token}")
                logger.debug(f"Request Token Secret: {secret}")
                return token, secret
            elif r.status_code == 301:
                logger.error(
                    f"Failed to authenticate for request key on {host}: {r.text}"
                )
                raise Exception(
                    f"Unable to get aa request token due to authentication failure ({host}), check your credentials and consumer key+secret"
                )
            else:
                logger.error(f"Failed to get request token: {r.json()['message']}")
                raise Exception(f"Failed to get request token for {host}")
        except Exception as e:
            logger.error(f"Error getting request token: {str(e)}")
            raise Exception(f"Error getting request token for {host}")

    def fetch_session_key(self, host, database) -> tuple[str, str]:
        logger.debug(f"Fetching session key for {host}...")
        access_key = self.get_access_key(host, database)
        consumer_key = self.get_consumer_key(host)
        session_request = OAuth1Session(
            consumer_key[0],
            consumer_key[1],
            access_token=access_key[0],
            access_token_secret=access_key[1],
        )
        url = f"{self.__host_config[host]['REST_URL']}/pubmlst_{database}_seqdef/oauth/get_session_token"
        r = session_request.get(url)
        if r.status_code == 200:
            session_token = r.json()["oauth_token"]
            session_secret = r.json()["oauth_token_secret"]
        elif r.status_code == 301:
            print(
                f"Session access denied. Attempting to regenerate keys as needed for {host}"
            )
            # Access key is out of date/revoked. Delete and re-run fetch_session_key
            self.delete_key("access", host)
            session_token, session_secret = self.fetch_session_key(host, database)
        else:
            print(f"{r.status_code}: Failed to get session token for {host}: {r.text}")
            raise Exception(f"Failed to get session token for {host}")
        return session_token, session_secret

    def fetch_access_key(self, host: str, database: str) -> tuple[str, str]:
        """Fetch an access key for the specified host and database. This will log in at the host as the user
        and get a verification code"""
        logger.debug(f"Fetching access key for {host}...")
        request_key: tuple[str, str] = self.get_request_key(host, database)
        consumer_key = self.get_consumer_key(host)

        """Automatically authorize the application."""
        logger.info(f"Authorising application for {host} - {database}...")
        session = self.__get_bigsdb_session(host)
        if not KeyCache.__logged_in(session, self.__host_config[host]['WEB_URL']):
            raise Exception(f"Failed to log in to {host}")
        authorise_url = f"{self.__host_config[host]['WEB_URL']}?db=pubmlst_{database}_seqdef&page=authorizeClient&oauth_token={request_key[0]}"
        logger.debug(f"Authorise client URL: {authorise_url}")
        auth_response = session.get(authorise_url)
        if "The request token has already been redeemed" in auth_response.text:
            logger.info("Request token has already been redeemed. Using cached access token.")
            self.delete_key("request", host)
            return self.fetch_access_key(host, database)
        auth_soup = BeautifulSoup(auth_response.text, "html.parser")
        auth_form = auth_soup.find("form", action=re.compile(r"authorizeClient"))
        if not auth_form:
            logger.error("Could not find authorisation form")
            logger.debug(f"Response content: {auth_response.text}")
            raise Exception(f"Failed to find authorisation form for {host}")

        auth_data = {
            hidden_field["name"]: hidden_field["value"]
            for hidden_field in auth_form.find_all("input", type="hidden")
        }
        auth_data["submit"] = "Authorize"

        verifier_url = self.__host_config[host]["AUTH_BASE"] + auth_form["action"]
        logger.debug(f"Verifier URL: {verifier_url}")
        final_response = session.post(verifier_url, data=auth_data, allow_redirects=True)

        final_soup = BeautifulSoup(final_response.text, "html.parser")
        verifier_tag = final_soup.find("b", string=re.compile(r"Verification code:"))

        if verifier_tag:
            verifier = verifier_tag.string.split(":")[1].strip()
            logger.debug(f"Extracted verifier: {verifier}")
        else:
            logger.error("Failed to obtain verifier code")
            logger.debug(f"Final URL: {final_response.url}")
            logger.debug(f"Response content: {final_response.text}")
            raise Exception(f"Failed to obtain verifier code for {host}")


        logger.info(f"Getting access token for {host} - {database}...")
        service = create_oauth_service(
            consumer_key, self.__host_config[host]["REST_URL"], database
        )
        try:
            r = service.get_raw_access_token(
                request_key[0], request_key[1], params={"oauth_verifier": verifier}
            )
            if r.status_code == 200:
                token = r.json()["oauth_token"]
                secret = r.json()["oauth_token_secret"]
                logger.debug(f"Access Token: {token}")
                logger.debug(f"Access Token Secret: {secret}")
                return token, secret
            elif r.status_code == 301:
                self.delete_key("request", host)
                return self.fetch_access_key(host, database)
            else:
                logger.error(f"Failed to get access token: {r.json()['message']}")
                raise Exception(f"Failed to get access token for {host}")
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            raise Exception(f"Error getting access token for {host}")

    @staticmethod
    def load_config(host_config_file):
        if not host_config_file or not Path(host_config_file).exists():
            raise FileNotFoundError(
                f"Host configuration file not found: {host_config_file}"
            )
        with open(host_config_file, "r") as f:
            return json.load(f)

    @staticmethod
    def __logged_in(session: requests.session, url: str) -> bool:
        """Check if the current session is logged in."""
        response = session.get(url)
        return "Log out" in response.text

    def __get_bigsdb_session(self, host):
        if host not in self.__logged_in_session or not KeyCache.__logged_in(
            self.__logged_in_session[host], self.__host_config[host]["WEB_URL"]
        ):
            self.__logged_in_session[host] = self.__login_to_bigsdb(host)
        return self.__logged_in_session[host]

    def __login_to_bigsdb(self, host):
        session = requests.Session()
        login_response = session.get(self.__host_config[host]["WEB_URL"])
        login_form = BeautifulSoup(login_response.text, "html.parser").find("form")

        if not login_form:
            logger.debug(f"{BeautifulSoup(login_response.text, 'html.parser')}")
            logger.error("Could not find login form")
            raise Exception(f"Failed to find login form for {host}")

        login_data = {
            hidden_field["name"]: hidden_field["value"]
            for hidden_field in login_form.find_all("input", type="hidden")
        }

        user_credentials = self.get_user_credentials(host)
        hashed_password = hashlib.md5(
            (
                user_credentials[1].strip()
                + user_credentials[0].strip()
            ).encode()
        ).hexdigest()

        login_data.update(
            {
                "user": user_credentials[0].strip(),
                "password": hashed_password,
                "submit": "Log in",
                "page": "user",
            }
            | self.__host_config[host]["LOGIN_DB"]
        )

        login_response = session.post(
            self.__host_config[host]["WEB_URL"], data=login_data, allow_redirects=True
        )

        if "Invalid username or password" in login_response.text:
            logger.error("Login failed: Invalid username/password")
            raise Exception(f"Invalid username/password for {host}")
        login_response.raise_for_status()
        logger.debug("Login successful")
        return session

    def get_rest_url(self, host):
        """Return the REST URL base for the specified host."""
        if host not in self.__host_config:
            raise KeyError(f"Host {host} not found in host configuration")
        return self.__host_config[host]["REST_URL"]


def create_oauth_service(
    consumer_key: tuple[str, str], rest_url: str, database: str
) -> OAuth1Service:
    """Create and return an OAuth1Service instance."""
    return OAuth1Service(
        name="BIGSdb",
        consumer_key=consumer_key[0],
        consumer_secret=consumer_key[1],
        request_token_url=f"{rest_url}/pubmlst_{database}_seqdef/oauth/get_request_token",
        access_token_url=f"{rest_url}/pubmlst_{database}_seqdef/oauth/get_access_token",
        base_url=f"{rest_url}/pubmlst_{database}_seqdef",
    )
