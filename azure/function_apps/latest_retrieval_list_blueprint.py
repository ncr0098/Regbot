import azure.functions as func
import logging, re, json, os
from datetime import datetime

get_latest_retrieval_list_csv_bp = func.Blueprint()

@get_latest_retrieval_list_csv_bp.function_name('get_latest_retrieval_list_csv')
@get_latest_retrieval_list_csv_bp.route(route='get_latest_retrieval_list_csv')
def get_latest_retrieval_list_csv_blueprint_function(req: func.HttpRequest) -> func.HttpResponse:
    from services.graph_api_service import GraphAPIService
    from dotenv import load_dotenv

    try:
        retrieval_list_directory_path = req.params.get("retrieval_list_directory_path")
        # retrieval_list_directory_path = "/prod/retrieval_list"

        # .envファイルを読み込む
        load_dotenv()

        # EntraID、GraphAPI関連
        entra_client_id = os.getenv('ENTRA_CLIENT_ID')
        entra_client_secret = os.getenv('ENTRA_CLIENT_SECRET')
        entra_authority_url = os.getenv('ENTRA_AUTHORITY_URL')
        entra_tenant_id = os.getenv('ENTRA_TENANT_ID')
        graph_api_default_scope = os.getenv('GRAPH_API_DEFAULT_SCOPE')
        graph_api_resource = os.getenv('GRAPH_API_RESOURCE')
        site_id = os.getenv("SITE_ID")

        graph_api_service = GraphAPIService(
            client_id=entra_client_id
            , client_secret=entra_client_secret
            , tenant_id=entra_tenant_id
            , authority=entra_authority_url
            , scope=[graph_api_default_scope]
            , resource=graph_api_resource
            )
        
        endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:{retrieval_list_directory_path}:/children"

        response = graph_api_service.graph_api_get(endpoint).json()
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
        return func.HttpResponse(
                json.dumps({
                    "retrieval_list_filename": latest_file_name,
                }),
                mimetype="application/json",
                status_code=200
            )
    except Exception as e:
        logging.error(f"Error occured: {e}")