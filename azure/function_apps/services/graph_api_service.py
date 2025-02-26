import msal
import requests
import tempfile
import os
import logging

class GraphAPIService:
    def __init__(self, client_id, client_secret, tenant_id, authority, scope, resource):
        self.app = msal.ConfidentialClientApplication(
            client_id, authority=authority,
            client_credential=client_secret
        )
        self.tenant_id = tenant_id
        self.resource = resource
        self.access_token = self.fetch_access_token(scope)

    def fetch_access_token(self, scope):
        result = self.app.acquire_token_silent(scope, account=None)
        if not result:
            logging.info("No suitable token exists in cache. Let's get a new one from AAD.")
            result = self.app.acquire_token_for_client(scopes=scope)
        access_token = result["access_token"]
        return access_token
    
    def download_file_from_sharepoint(self, file_url, file_name):
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        try:  
            response = requests.get(file_url, headers=headers, stream=False)

            # ステータスコードをチェック
            if response.status_code == 200:
                # カレントディレクトリにファイルを保存
                local_path = tempfile.gettempdir()
                filepath = os.path.join(local_path, file_name)
                with open(filepath, "wb") as file:
                    file.write(response.content)
                absolute_path = os.path.abspath(filepath)
                logging.info(f"ファイルが {absolute_path} として保存されました。")
                return absolute_path
            else:
                logging.error(f"ファイルのダウンロードに失敗しました。ステータスコード: {response.status_code}")
                raise Exception
        except Exception as e:
            logging.error(f"GraphAPI request error: {e}", stack_info=True)
            raise
