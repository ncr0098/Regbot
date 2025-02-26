import azure.functions as func
import logging
import pandas as pd
from io import BytesIO, StringIO
import json
import time
bp = func.Blueprint()

@bp.function_name('test_blueprint')
@bp.route(route='test_blueprint')
def blueprint_function(req: func.HttpRequest) -> func.HttpResponse:
    from datetime import datetime

    from services.graph_api_service import GraphAPIService
    from services.dataverse_service import DataverseService
    import os
    from dotenv import load_dotenv
    
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
    drive_id = os.getenv('DRIVE_ID')
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
    
    # 管理ファイル取得
    retrieval_list_storage_directory_path = f"/{environment}/retrieval_list"
    get_retrieval_list_endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:{retrieval_list_storage_directory_path}:/children"
    retrieval_list_file_name = graph_api_service.get_latest_retrieval_list_csv(get_retrieval_list_endpoint)


    # 管理ファイルの読み込みAPIエンドポイント
    file_url = f' https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:{retrieval_list_storage_directory_path}/{retrieval_list_file_name}:/content'
    excel_file = BytesIO(graph_api_service.graph_api_get(file_url).content)
    df = pd.read_excel(excel_file)

    df_output = pd.DataFrame()

    ### ここから行ごとの処理 ###
    # statusの確認、0,1,9ごとに分岐処理
    # dataverseの情報と比較
    # indexed情報をdataverseに付加

    """
    場合分け：
    (1)管理ファイルにstatus=9 → 処理continue
    (2)管理ファイルにstatus=1 → sharepointのファイルを削除、dfから行を削除
    (3)管理ファイルにstatus=0 → ファイルとmodified_dateをwebからダウンロード/取得、dataverseのmodified_dateを取得
        (a) df.modified_date vs dataverse.modified_dateに差異なし & sharepointにも格納済み → 処理continue
        (b) sharepointにない → sharepointに格納、indexedを0に設定する
        (c) websiteにファイルが無い → df.statusを9に変更（ユーザーに削除確認を依頼）
    
    各行の処理が完了したら、変化をdataverseに反映させる


    注意点：websiteの日付はcacheなしで取得する -> ok
    負荷を考慮し、sleepする -> ok
    #管理ファイルの出力：sort by status(desc) -> source_name (alphabetical) -> pdf_url (alphabetical) -> ok
    """    
    for row in df.itertuples(index=True):
        # print(f"\nworking on {row.pdf_url}")
        
        time.sleep(5)

        # Dataverseからレコード取得
        records = dataverse_service.entity.read(
        select=["cr261_source_name", "cr261_pdf_url", "cr261_sharepoint_url", "cr261_sharepoint_directory", "cr261_sharepoint_file_name", "cr261_sharepoint_item_id", "cr261_pdf_last_modified_datetime", "cr261_status", "cr261_timestamp"], 
        filter=f"cr261_pdf_url eq '{row.pdf_url}'", 
        order_by="cr261_pdf_last_modified_datetime")
        
        if len(records) == 0:
            # 管理ファイルにあるが、dataverseにないとrecordsの取得が失敗するため、lenが0となる
            continue #管理ファイルの次の行へ
        
        record_dict = records[0] # pdf_urlはuniqueなため
        status = row.status
        source_name = record_dict["cr261_source_name"]
        
        # check manual files
        if f"/{environment}/manual/" in record_dict["cr261_sharepoint_directory"]:
            # TODO:マニュアル格納されたファイルのindex要否チェック
            
            continue

        # automatic filesの処理：

        # status値による分岐処理：
        if status == 9:
            # ユーザーが確認する必要あり
            # 管理ファイル世代N+1に追記
            df_output = pd.concat([df_output, pd.DataFrame([record_dict])], axis=0, ignore_index=True)
            continue #管理ファイルの次の行へ

        elif status == 1:
            # sharepointのファイルを削除、dfのstatusを1に、indexedを0に、その他db整理
            item_id = record_dict["cr261_sharepoint_item_id"]
            delete_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{item_id}"
            deletion_graph_data = graph_api_service.delete_file_from_sharepoint(delete_url)
            
            if deletion_graph_data:
                # dictionary を更新する
                record_dict["cr261_indexed"] = 0
                record_dict["cr261_sharepoint_url"] = ""
                record_dict["cr261_sharepoint_item_id"] = ""
                record_dict["cr261_sharepoint_directory"] = ""

                # dataverseの書き込み
                df_dictionary = pd.DataFrame([record_dict])                
                result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")

                # 管理ファイル世代N+1には記入しない　（行がなくなる）
                
                logging.info("ファイル削除成功")
            
        elif status == 0:
            # ファイルのダウンロード要否の確認が必要
            web_url = record_dict["cr261_pdf_url"]
            dataverse_last_modified_date = record_dict["cr261_pdf_last_modified_datetime"]

            # PDFファイル情報をwebから取得
            web_last_modified_date, pdf_file_name = graph_api_service.get_file_header_from_web(web_url=web_url)

            # ファイルがwebに存在しない場合や、ダウンロードに不備（サーバー側のスクレイピング制限等）があった場合statusを9に変更
            if web_last_modified_date is None and pdf_file_name is None:    
                record_dict["cr261_status"] = 9
                
                # dataverseの書き込み
                df_dictionary = pd.DataFrame([record_dict])
                result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")
                
                # 管理ファイル世代N+1に追記
                df_output = pd.concat([df_output, pd.DataFrame([record_dict])], axis=0, ignore_index=True)
                
                logging.info("ファイルダウンロード失敗")
                continue #管理ファイルの次の行へ

            # 更新がない場合ダウンロードをスキップ
            if web_last_modified_date == dataverse_last_modified_date:
                logging.info("ファイル最終更新日が一致")
                # 管理ファイル世代N+1に追記
                df_output = pd.concat([df_output, pd.DataFrame([record_dict])], axis=0, ignore_index=True)
                continue #管理ファイルの次の行へ
            
            # PDFファイル情報をwebから取得
            file_content = graph_api_service.download_file_from_web(web_url=web_url)

            # PDFファイルをsharepointへ格納
            pdf_storage_directory_path = f"/{environment}/automatic/{source_name}"
            pdf_joined_name = f"{pdf_storage_directory_path}/{pdf_file_name}"
            # 上書きアップロードのエンドポイント
            sharepoint_upload_endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{parent_id}:/{pdf_joined_name}:/content"
            file_upload_graph_data = graph_api_service.upload_file_to_sharepoint(file_content, pdf_file_name, sharepoint_upload_endpoint)

            # dataverseの更新
            record_dict["cr261_sharepoint_url"] = file_upload_graph_data["webUrl"]
            record_dict["cr261_sharepoint_item_id"] = file_upload_graph_data["id"]
            record_dict["cr261_sharepoint_file_name"] = pdf_file_name
            record_dict["cr261_sharepoint_directory"] = pdf_storage_directory_path
            record_dict["cr261_pdf_last_modified_datetime"] = web_last_modified_date

            # dataverseの書き込み
            df_dictionary = pd.DataFrame([record_dict])                
            result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")

            # 管理ファイル世代N+1に追記
            df_output = pd.concat([df_output, pd.DataFrame([record_dict])], axis=0, ignore_index=True)
            print("upload success")

        else:
            logging.error(f"staus error for {record_dict["cr261_pdf_url"]}")
    
        ### 行ごとの処理完了 ###

    # 管理ファイルN+1世代の出力
    print(df_output)
    df_selected = df_output[['cr261_source_name', 'cr261_pdf_url', 'cr261_sharepoint_url', 'cr261_status']]
    df_selected = df_selected.rename(columns={
        'cr261_source_name': 'source_name',
        'cr261_pdf_url': 'pdf_url',
        'cr261_sharepoint_url': 'sharepoint_url',
        'cr261_status': 'status'
    })
    df_sorted = df_selected.sort_values(by=['status', 'source_name', 'pdf_url'], 
                            ascending=[False, True, True])
                
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create the filename with the current time
    retrieval_list_file_name = f"retrieve_list_{current_time}.xlsx"
    # Convert DataFrame to CSV in memory
    io_buffer = StringIO()
    df_sorted.to_excel(io_buffer, index=False)
    io_buffer.seek(0)

    # Convert CSV buffer to bytes
    io_bytes = io_buffer.getvalue().encode('utf-8')

    # PDFファイルをsharepointへ格納
    retrieval_list_storage_directory_path = f"/{environment}/retrieval_list"
    retrieval_list_joined_name = f"{retrieval_list_storage_directory_path}/{retrieval_list_file_name}"
    # 上書きアップロードのエンドポイント
    sharepoint_upload_retrieve_list_endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{parent_id}:/{retrieval_list_joined_name}:/content"

    graph_data = graph_api_service.upload_file_to_sharepoint(io_bytes, retrieval_list_file_name, sharepoint_upload_retrieve_list_endpoint)
    
    logging.info("retrieval list uploaded")
    
    logging.info("task ended successfully")

    return func.HttpResponse("Blueprintで定義された関数だよ")