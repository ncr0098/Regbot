from dataverse_api import DataverseClient
from msal import ConfidentialClientApplication
from msal_requests_auth.auth import ClientCredentialAuth
from requests import Session
from models.model import DataversePdfStatus

class DataverseService:
    def __init__(self, environment_url, entra_client_id, entra_client_secret, authority, entity_logical_name):
        self.environment_url = environment_url

        self.app_reg = ConfidentialClientApplication(
            client_id=entra_client_id,
            client_credential=entra_client_secret,
            authority=authority,
        )

        auth = ClientCredentialAuth(
            client=self.app_reg,
            scopes=[environment_url + "/.default"]
        )
        # Prepare Session
        session = Session()
        session.auth = auth

        # Instantiate DataverseClient
        self.client = DataverseClient(session=session, environment_url=environment_url)

        self.entity = self.client.entity(logical_name=entity_logical_name)

    def transform_record_dict_to_model_instance(self, record_dict):
        return DataversePdfStatus(**record_dict)
    
    def update_client_and_entity_with_newest_session(self, entity_logical_name):
        auth = ClientCredentialAuth(
            client=self.app_reg,
            scopes=[self.environment_url + "/.default"]
        )
        # Prepare Session
        session = Session()
        session.auth = auth

        # Instantiate DataverseClient
        self.client = DataverseClient(session=session, environment_url=self.environment_url)

        self.entity = self.client.entity(logical_name=entity_logical_name)
    
