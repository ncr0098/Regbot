import msal
import requests
import tempfile
import os
import logging
from io import BytesIO
from datetime import datetime, timedelta
import re

class GraphAPIService:
    def __init__(self, client_id, client_secret, tenant_id, authority, scope, resource):
        self.app = msal.ConfidentialClientApplication(
            client_id, authority=authority,
            client_credential=client_secret
        )
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.authority = authority
        self.scope = scope
        self.resource = resource
        self.access_token = self.fetch_access_token(scope)

    def fetch_access_token(self, scope):
        result = self.app.acquire_token_silent(scope, account=None)
        if not result:
            logging.info("No suitable token exists in cache. Let's get a new one from AAD.")
            result = self.app.acquire_token_for_client(scopes=scope)
        access_token = result["access_token"]
        expires_in = result["expires_in"]
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

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
            logging.error(f"GraphAPI request error: {e}")
            raise

    
    def delete_file_from_sharepoint(self, file_url):
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }

        try:
            response = requests.delete(file_url, headers=headers)

            if response.status_code == 204:
                logging.info(f"File at {file_url} deleted successfully.")
                return True
            else:
                logging.error(f"Failed to delete file. Status code: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"GraphAPI request error: {e}")
            raise
    
    def convert_time_format(self, time_str):
         # Define the input format (format A)
        input_format = '%a, %d %b %Y %H:%M:%S %Z'
        
        # Parse the input date string into a datetime object
        date_obj = datetime.strptime(time_str, input_format)
        
        # Define the output format (format B)
        output_format = '%Y-%m-%dT%H:%M:%SZ'
        
        # Format the datetime object into the desired output format
        formatted_date_str = date_obj.strftime(output_format)
        
        return formatted_date_str
    
    def get_file_header_from_web(self, web_url):
        # cacheを無効化
        headers = {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        try:  
            # Send a GET request to the URL
            response = requests.head(web_url, headers=headers)

            # ステータスコードをチェック
            if response.status_code == 200 \
                    and response.headers.get('Content-Type') == "application/pdf":
                # TODO: Content-Lengthにサイズ制限を設ける？

                # file_nameを取得
                # print("\nheader info:", response.headers)
                if web_url.endswith(".pdf") or ".pdf" in web_url: # EMAに".pdf-0"で終わるファイルがあったため
                    file_name = web_url.split("/")[-1]
                else:
                    file_name = response.headers.get('Content-Disposition').split("filename=")[-1]

                #最終更新日を取得
                last_modified = response.headers.get('Last-Modified', 'None Found')
                last_modified_converted = self.convert_time_format(last_modified)
                logging.info(f"ファイルmetadataをwebから取得しました。")
                
                return last_modified_converted, file_name
            
            elif response.status_code == 302:
                logging.error(f"ファイルのヘッダー情報取得に失敗しました。ステータスコード: {response.status_code}")
                return "status_302_continue", "status_302_continue"
            else:
                # failed_header = response.headers.json()
                # print(failed_header)

                logging.error(f"ファイルのヘッダー情報取得に失敗しました。ステータスコード: {response.status_code}")
                return 'empty', 'empty'
        
        except Exception as e:
            logging.error(f"file download error: {e}")
            return None, None

    def download_file_from_web(self, web_url):
        
        # cacheを無効化
        headers = {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        try:  
            # Send a GET request to the URL
            # response = requests.get(web_url, headers=headers, allow_redirects=True)
            response = requests.get(web_url, headers=headers)
            # print(response.headers)
            # ステータスコードをチェック
            if response.status_code == 200 \
                    and response.headers.get('Content-Type') == "application/pdf":                
                
                return response.content
            # elif response.status_code == 302:
            #     new_url = response.headers["Location"]
            #     print(new_url)
            #     response = requests.get(new_url)
            #     return response.content
            
            else:
                logging.error(f"ファイルのダウンロードに失敗しました。ステータスコード: {response.status_code}")
                return 'empty'
        
        except Exception as e:
            logging.error(f"file download error: {e}")
            return None

    def upload_file_to_sharepoint(self, pdf_file, pdf_file_name, sharepoint_upload_endpoint):

        try:
            # write to local file
            local_path = tempfile.gettempdir()            
            filepath = os.path.join(local_path, pdf_file_name)
            with open(filepath, "wb") as file:
                file.write(pdf_file)                
            absolute_path = os.path.abspath(filepath)
            
            # upload written local file
            with open(absolute_path, 'rb') as file:
                graph_data = self.graph_api_put(sharepoint_upload_endpoint, file)
            
            return graph_data
            
        except Exception as e:
            logging.error(f"GraphAPI request error: {e}")
            raise


        # https://graph.microsoft.com/v1.0/sites/0e4def03-c3e0-48d3-9792-37d278ad883d/drive/items/01PMNHK5F6Y2GOVW7725BZO354PWSELRRZ:/cheng_test/pdf_files/test_FDA/aaa.pdf:/content
    
    # Graph APIを使用してデータを送信する汎用PUTメソッド
    def graph_api_put(self, endpoint: str, data) -> requests.models.Response | None:
        """
        Post data to Graph API using the endpoint
        """
        if self.access_token is not None:
            graph_data = requests.put(
                url=endpoint,
                headers={'Authorization': 'Bearer ' + self.access_token},
                data=data).json()
            return graph_data
        else:
            raise Exception("No access token available")
    
    def graph_api_get(self, endpoint: str) -> requests.models.Response | None:
        """
        Get data from Graph API using the endpoint
        """
        if self.access_token is not None:
            graph_data = requests.get(
                endpoint,
                headers={'Authorization': 'Bearer ' + self.access_token})
            return graph_data
    
    def get_latest_retrieval_list_csv(self, retrieval_list_directory_path):
        response = self.graph_api_get(retrieval_list_directory_path).json()
        retrieval_lists = response.get('value', [])

        retrieve_list_files = []

        # Regex pattern to match retrieve_list_YYYYMMDD_hhmmss.xlsx
        pattern = re.compile(r'retrieve_list_(\d{8}_\d{6})\.xlsx')

        for file in retrieval_lists:
            match = pattern.match(file['name'])
            if match:
                retrieve_list_files.append((file['name'], datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')))

        if not retrieve_list_files:
            logging.error("No retrieve_list files found in the directory.")
            return None

        # Find the latest file based on the timestamp
        latest_file_name, _ = max(retrieve_list_files, key=lambda x: x[1])
        return latest_file_name
