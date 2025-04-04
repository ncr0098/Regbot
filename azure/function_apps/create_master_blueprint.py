import azure.functions as func
import logging

create_master_bp = func.Blueprint()

@create_master_bp.function_name('create_master_blueprint')
@create_master_bp.route(route='create_master_blueprint')
def create_master_blueprint_function(req: func.HttpRequest) -> func.HttpResponse:
    from datetime import datetime

    from services.graph_api_service import GraphAPIService
    from services.dataverse_service import DataverseService
    import os
    from dotenv import load_dotenv
    import pandas as pd
    from io import BytesIO
    
    # .envファイルを読み込む
    load_dotenv()
    
    # EntraID、GraphAPI関連
    entra_client_id = os.getenv('ENTRA_CLIENT_ID')
    entra_client_secret = os.getenv('ENTRA_CLIENT_SECRET')
    entra_authority_url = os.getenv('ENTRA_AUTHORITY_URL')
    entra_tenant_id = os.getenv('ENTRA_TENANT_ID')
    graph_api_default_scope = os.getenv('GRAPH_API_DEFAULT_SCOPE')
    graph_api_resource = os.getenv('GRAPH_API_RESOURCE')
    power_platform_environment_url = os.getenv('POWER_PLATFORM_ENVIRONMENT_URL')
    dataverse_entity_name = os.getenv('DATAVERSE_ENTITY_NAME')

    site_id = os.getenv('SITE_ID')
    parent_id = os.getenv('PARENT_ID')
    environment = os.getenv('ENVIRONMENT')
    
    graph_api_service = GraphAPIService(
            client_id=entra_client_id
            , client_secret=entra_client_secret
            , tenant_id=entra_tenant_id
            , authority=entra_authority_url
            , scope=[graph_api_default_scope]
            , resource=graph_api_resource
            )
    dataverse_service = DataverseService(environment_url=power_platform_environment_url
                                        , entra_client_id=entra_client_id
                                        , entra_client_secret=entra_client_secret
                                        , authority=entra_authority_url
                                        , entity_logical_name=dataverse_entity_name)
    
    # Dataverseからレコード取得
    # 論理削除されてないものすべて取得
    dataverse_records = dataverse_service.entity.read(select=["*"], filter="cr261_status ne 1", order_by="cr261_pdf_last_modified_datetime")
    
    if len(dataverse_records) > 0:
        df_output = pd.DataFrame(dataverse_records) # 管理ファイルN+1世代の準備

        df_selected = df_output[['cr261_source_name', 'cr261_pdf_url', 'cr261_sharepoint_url', 'cr261_status', 'cr261_manual_flag']]
        df_selected = df_selected.rename(columns={
            'cr261_source_name': 'source_name',
            'cr261_pdf_url': 'pdf_url',
            'cr261_sharepoint_url': 'sharepoint_url',
            'cr261_status': 'status',
            'cr261_manual_flag':'manual_flag'
        })
        df_sorted = df_selected.sort_values(by=['status', 'source_name', 'pdf_url'], 
                                ascending=[False, True, True])
        print(df_sorted)
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create the filename with the current time
        retrieval_list_file_name = f"retrieve_list_{current_time}.csv"
        # Convert DataFrame to CSV in memory
        io_buffer = BytesIO()
        # df_sorted.to_excel(io_buffer, index=False)
        df_sorted.to_csv(io_buffer, index=False)  # Use BytesIO here

        io_buffer.seek(0)

        # Convert CSV buffer to bytes
        # io_bytes = io_buffer.getvalue().encode('utf-8')
        # Convert buffer to bytes
        io_bytes = io_buffer.getvalue()

        # PDFファイルをsharepointへ格納
        retrieval_list_storage_directory_path = f"/{environment}/retrieval_list"
        retrieval_list_joined_name = f"{retrieval_list_storage_directory_path}/{retrieval_list_file_name}"
        
        # 上書きアップロードのエンドポイント
        sharepoint_upload_retrieve_list_endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{parent_id}:/{retrieval_list_joined_name}:/content"

        logging.info("start uploading")
        graph_data = graph_api_service.upload_file_to_sharepoint(io_bytes, retrieval_list_file_name, sharepoint_upload_retrieve_list_endpoint)
        logging.info("complete uploading")

        logging.info("retrieval list uploaded")
    else:
        logging.info("no record founded")

    logging.info("task ended successfully")
    print("\ntask ended successfully")

    return func.HttpResponse("retrieval list uploading task ended")