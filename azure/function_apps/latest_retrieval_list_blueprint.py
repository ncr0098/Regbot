import azure.functions as func
import logging, re, json, os
from datetime import datetime
import pandas as pd
from io import StringIO

get_latest_retrieval_list_csv_bp = func.Blueprint()

@get_latest_retrieval_list_csv_bp.function_name('get_latest_retrieval_list_csv')
@get_latest_retrieval_list_csv_bp.route(route='get_latest_retrieval_list_csv')
def get_latest_retrieval_list_csv_blueprint_function(req: func.HttpRequest) -> func.HttpResponse:
    from services.graph_api_service import GraphAPIService
    from dotenv import load_dotenv

    try:
        retrieval_list_directory_path = req.params.get("retrieval_list_directory_path")
        # retrieval_list_directory_path = "/prod/retrieval_list"
        logging.info(f"Retrieval list directory path: {retrieval_list_directory_path}")

        # .envファイルを読み込む
        load_dotenv()
        logging.info("env variables loaded.")

        # EntraID、GraphAPI関連
        entra_client_id = os.getenv('ENTRA_CLIENT_ID')
        entra_client_secret = os.getenv('ENTRA_CLIENT_SECRET')
        entra_authority_url = os.getenv('ENTRA_AUTHORITY_URL')
        entra_tenant_id = os.getenv('ENTRA_TENANT_ID')
        graph_api_default_scope = os.getenv('GRAPH_API_DEFAULT_SCOPE')
        graph_api_resource = os.getenv('GRAPH_API_RESOURCE')
        site_id = os.getenv("SITE_ID")
        drive_id = os.getenv("DRIVE_ID")

        logging.info("Environment variables loaded successfully.")

        graph_api_service = GraphAPIService(
            client_id=entra_client_id
            , client_secret=entra_client_secret
            , tenant_id=entra_tenant_id
            , authority=entra_authority_url
            , scope=[graph_api_default_scope]
            , resource=graph_api_resource
            )
        
        endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:{retrieval_list_directory_path}:/children"
        logging.info(f"Graph API endpoint: {endpoint}")

        response = graph_api_service.graph_api_get(endpoint).json()
        logging.info("Graph API response received.")

        retrieval_lists = response.get('value', [])
        if not retrieval_lists:
            logging.error("No files found in the specified directory.")
            return func.HttpResponse(
                "No files found in the specified directory.",
                status_code=404
            )

        retrieve_list_files = []

        # Regex pattern to match retrieve_list_YYYYMMDD_hhmmss.csv
        pattern = re.compile(r'retrieve_list_(\d{8}_\d{6})\.csv')

        for file in retrieval_lists:
            match = pattern.match(file['name'])
            if match:
                retrieve_list_files.append((file['name'], datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')))

        if not retrieve_list_files:
            logging.error("No retrieve_list files found in the directory.")
            return func.HttpResponse(
                "No retrieve_list files found in the directory.",
                status_code=404
            )

        # Find the latest file based on the timestamp
        latest_file_name, _ = max(retrieve_list_files, key=lambda x: x[1])
        file_url = f' https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:{retrieval_list_directory_path}/{latest_file_name}:/content'
        logging.info(f"Latest file URL: {file_url}")
        # 本日日付時刻を取得
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存するファイル名を作成
        savefile_name= f"{current_time}_{file_url.split('/')[-1]}"
        logging.info(f"Save file name: {savefile_name}")

        absolute_path = graph_api_service.download_file_from_sharepoint(file_url=file_url, file_name=savefile_name)
        logging.info(f"File downloaded and saved as {absolute_path}")
        
        with open(absolute_path, 'r', encoding='utf-8') as file:
            csv_content = file.read()
        logging.info("CSV content read from file.")
        
        # CSVをDataFrameに読み込み
        df = pd.read_csv(StringIO(csv_content))
        logging.info("CSV content loaded into DataFrame.")

        # DataFrameを辞書形式に変換
        csv_dict = df.to_dict(orient='records')
        logging.info("DataFrame converted to dictionary. Returning JSON response.")

        # JSON形式で返却
        return func.HttpResponse(
            json.dumps(csv_dict, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error occured: {e}")