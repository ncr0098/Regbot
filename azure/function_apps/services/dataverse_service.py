from dataverse_api import DataverseClient
from msal import ConfidentialClientApplication
from msal_requests_auth.auth import ClientCredentialAuth
from requests import Session

class DataverseService:
    def __init__(self, environment_url, entra_client_id, entra_client_secret, authority):
        self.envieonment_url = environment_url

        app_reg = ConfidentialClientApplication(
            client_id=entra_client_id,
            client_credential=entra_client_secret,
            authority=authority,
        )

        auth = ClientCredentialAuth(
            client=app_reg,
            scopes=[environment_url + "/.default"]
        )
        # Prepare Session
        session = Session()
        session.auth = auth

        # Instantiate DataverseClient
        self.client = DataverseClient(session=session, environment_url=environment_url)