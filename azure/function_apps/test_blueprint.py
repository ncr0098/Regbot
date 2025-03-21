import azure.functions as func
import logging

bp = func.Blueprint()

@bp.function_name('test_blueprint')
@bp.route(route='test_blueprint')
def blueprint_function(req: func.HttpRequest) -> func.HttpResponse:
    from datetime import datetime

    from services.graph_api_service import GraphAPIService
    from services.dataverse_service import DataverseService
    import os
    from dotenv import load_dotenv
    import pandas as pd
    from io import BytesIO, StringIO
    import json
    import time
    import openpyxl
    import requests
    import uuid
    import re

    try:
        # パラメータ取得
        source_name = req.params.get("source_name")
        pdf_url = req.params.get("pdf_url")
        sharepoint_web_url = req.params.get("sharepoint_url")
        status = req.params.get("status")
        manual_flag = req.params.get("manual_flag")
        logging.info(source_name)
        logging.info(pdf_url)
        logging.info(sharepoint_web_url)
        logging.info(status)
        logging.info(manual_flag)

        status = int(status) if not (status is None or status.split() == '') else 999
        manual_flag = int(manual_flag) if not (manual_flag is None or manual_flag.split() == '') else 999
        
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
        
        df_output = pd.DataFrame() # 管理ファイルN+1世代の準備

        ### ここから行ごとの処理 ###
        """
        まずはdataverseにレコードが存在するか
        →無ければファイルをダウンロードし、格納（シェアポイントにファイルが存在しても上書きする）。そしてdataverseのレコードを作成
        
        →あればステータス別に条件分岐
            →→manual格納されたファイルの場合、更新があったか確認する(dataverseの記録 vs sharepointのメタデータ)
            →→場合分け：
            (1)管理ファイルにstatus=9 → 処理continue
            (2)管理ファイルにstatus=1 → sharepointのファイルを削除、dataverseを更新
            (3)管理ファイルにstatus=0 → ファイルとmodified_dateをwebからダウンロード/取得、dataverseのmodified_dateを取得
                (a) dataverse.modified_date vs web.modified_dateに差異なし → 処理continue
                (b) websiteにファイルが無い → df.statusを9に変更（ユーザーに削除確認を依頼）
        
        各行の処理が完了したら、変化をdataverseに反映させる

        注意点：
            websiteの日付はcacheなしで取得する -> ok
            負荷を考慮し、sleepする -> ok
            管理ファイルの出力：sort by status(desc) -> source_name (alphabetical) -> pdf_url (alphabetical) -> ok
        """    
        # for row in df.itertuples(index=True):
        if pdf_url is None or pdf_url.strip() == '' :
            return func.HttpResponse("skip dataverse insertion process due to empty pdf_url")
        
        # source_name validation check
        pattern = re.compile(r'[\uFF00-\uFFEF\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]')
        source_name_invalid =  source_name is None or ' ' in source_name or bool(pattern.search(source_name.strip()))
        status_invalid = not((status == 0) or (status == 1) or (status == 9))
        manual_flag_invalid = manual_flag == 999

        time.sleep(2)
        logging.info(f"\nworking on {pdf_url}")

        status_to_be_inserted = None
        insert_to_be_registered = ''
        
        upload_method = "manual" if manual_flag == 1 else "automatic"
        logging.info(upload_method)
        web_url = pdf_url
        pdf_storage_directory_path = f"/{environment}/{upload_method}/{source_name}"

        # Dataverseからレコードを取得
        records = dataverse_service.entity.read(
            select=["cr261_source_name", "cr261_pdf_url", "cr261_sharepoint_url", 
                    "cr261_sharepoint_directory", "cr261_sharepoint_file_name", "cr261_sharepoint_item_id", 
                    "cr261_pdf_last_modified_datetime", "cr261_status", "cr261_timestamp", 
                    "cr261_manual_flag", "cr261_indexed"], 
            filter=f"cr261_pdf_url eq '{pdf_url}'"
            )
                
        # 管理ファイルにレコードが存在し、dataverseに存在しない場合：　
        # →　lenが0となる。新規のレコードをdataverseに追加する必要あり
        if len(records) == 0: # statusがなんであろうとsharepointに格納し、dataverseに書きこむ
            logging.info("no entry in dataverse...")

            if source_name_invalid or status_invalid or manual_flag_invalid:
            
                pdf_storage_directory_path = ""            
                sharepoint_web_url = ""
                generated_uuid = uuid.uuid4()
                last_modified = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
                status_to_be_inserted = 9 # write 9 in dataverse
                sharepoint_item_id = ""
                pdf_file_name = ""
                time_first_written_to_dataverse = last_modified
                insert_to_be_registered = 1

                record_dict = {
                    "cr261_sharepoint_directory": f"{pdf_storage_directory_path}",
                    "cr261_source_name": f"{source_name}",
                    "cr261_sharepoint_url": f"{sharepoint_web_url}",
                    "cr261_pdf_storageid": f"{generated_uuid}", # this is the guid of this dataverse record
                    "cr261_manual_flag": f"{manual_flag}",
                    "cr261_pdf_url": f"{pdf_url}",
                    "cr261_pdf_last_modified_datetime": f"{last_modified}", # sharepointに格納された時間
                    "cr261_status": f"{status_to_be_inserted}",
                    "cr261_sharepoint_item_id": f"{sharepoint_item_id}", #sharepointに格納されたid
                    "cr261_sharepoint_file_name": f"{pdf_file_name}",
                    "cr261_timestamp": f"{time_first_written_to_dataverse}",
                    "cr261_indexed": f"{insert_to_be_registered}"
                }

                df_dictionary = pd.DataFrame([record_dict])
                result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")
                
                return func.HttpResponse("validation error with source_name or status or manual_flag")
            
            # dataverseに書き込む。ファイル格納方法により変数の取得方法が変わる。
            if "automatic" in upload_method:
                logging.info('its automatic')

                # ファイル名と最終更新日を取得
                web_last_modified_date, pdf_file_name = graph_api_service.get_file_header_from_web(web_url=web_url)
                logging.info(pdf_file_name)
                if web_last_modified_date == 'empty':
                    status_to_be_inserted = 9
                    insert_to_be_registered = '1'
                else:
                    status_to_be_inserted = status
                    insert_to_be_registered = '0'

                time.sleep(50)
                # PDFファイルをwebから取得
                file_content = graph_api_service.download_file_from_web(web_url=web_url)
                if file_content == 'empty':
                    logging.info('empty')
                    status_to_be_inserted = 9
                    insert_to_be_registered = '1'
                else:
                    logging.info('not empty')
                    status_to_be_inserted = status
                    insert_to_be_registered = '0'

                # PDFファイルをsharepointへ格納
                pdf_joined_name = f"{pdf_storage_directory_path}/{pdf_file_name}"
                sharepoint_upload_endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{parent_id}:/{pdf_joined_name}:/content"
                logging.info('start upload file to sharepoint')
                file_upload_graph_data = graph_api_service.upload_file_to_sharepoint(file_content, pdf_file_name, sharepoint_upload_endpoint)
                logging.info("upload file to sharepoint: \n", file_upload_graph_data)

                # dataverse準備
                # 格納方法がautomaticであればwebの最終更新日を、manualであれば格納した日付を設定
                last_modified = web_last_modified_date # if upload_method == "automatic" else file_upload_graph_data["lastModifiedDateTime"]
                sharepoint_item_id = file_upload_graph_data["id"]
                sharepoint_web_url = file_upload_graph_data["webUrl"]
                
                
            
            else: # when upload_method is manual  
                logging.info('its manual')
                # TODO: ファイル名が異なりエラーになっても処理を止めないようにする
                # IMPORTANT: "/dev/manual/PMDA/000206143.pdf" の形式で管理ファイルのsharepoint_urlに書いてもらう必要あり
                joined_directory_and_filename = sharepoint_web_url 
                # ファイルが同じ名称で置き換わっている可能性を考慮し、item_idでなくファイル名で取得
                get_file_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:{joined_directory_and_filename}"
                sharepoint_file_metadata = graph_api_service.graph_api_get(get_file_url).json()
                logging.info(sharepoint_file_metadata)

                if 'error' in sharepoint_file_metadata:
                    logging.info('error occured on fetching valid metadata')
                    status_to_be_inserted = 9
                    insert_to_be_registered = '1'
                    last_modified =  datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
                    sharepoint_item_id = ''
                    sharepoint_web_url = sharepoint_web_url
                    pdf_file_name = sharepoint_web_url.split('/')[-1]
                else:
                    logging.info('got valid metadata')
                    status_to_be_inserted = status
                    insert_to_be_registered = '0'
                    sharepoint_last_modified_date = sharepoint_file_metadata["lastModifiedDateTime"]
                    last_modified = sharepoint_last_modified_date
                    sharepoint_item_id = sharepoint_file_metadata["id"]
                    sharepoint_web_url = sharepoint_file_metadata["webUrl"]
                    pdf_file_name = sharepoint_file_metadata["name"]
                
                # get pdf
                pdf_storage_directory_path = os.path.dirname(f"{joined_directory_and_filename}")
                source_name = pdf_storage_directory_path.split("/")[-1]

                
            generated_uuid = uuid.uuid4() # dataverse tableのレコードのキー
            time_first_written_to_dataverse = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            # # dataverseの書き込み
            record_dict = {
                "cr261_sharepoint_directory": f"{pdf_storage_directory_path}",
                "cr261_source_name": f"{source_name}",
                "cr261_sharepoint_url": f"{sharepoint_web_url}",
                "cr261_pdf_storageid": f"{generated_uuid}", # this is the guid of this dataverse record
                "cr261_manual_flag": f"{manual_flag}",
                "cr261_pdf_url": f"{pdf_url}",
                "cr261_pdf_last_modified_datetime": f"{last_modified}", # sharepointに格納された時間
                "cr261_status": f"{status_to_be_inserted}",
                "cr261_sharepoint_item_id": f"{sharepoint_item_id}", #sharepointに格納されたid
                "cr261_sharepoint_file_name": f"{pdf_file_name}",
                "cr261_timestamp": f"{time_first_written_to_dataverse}",
                "cr261_indexed": f"{insert_to_be_registered}"
            }

            df_dictionary = pd.DataFrame([record_dict])
            result = dataverse_service.entity.create(data=df_dictionary, mode="individual")
            logging.info(result)
            logging.info("upload success")

            return func.HttpResponse("process when no data exists on dataverse")
        
        # dataverseにも管理ファイルに記載されたレコードが存在する場合：
        else:
            logging.info('records not empty')
            record_dict = records[0] # pdf_urlはuniqueなため1件目を取得する
            
            if source_name_invalid or status_invalid or manual_flag_invalid:

                record_dict["cr261_status"] = 9

                df_dictionary = pd.DataFrame([record_dict])
                result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")
                logging.info(result)
                
                return func.HttpResponse("validation error with source_name or status or manual_flag")
            
            if "manual" in upload_method:
                logging.info('its manual')
                # マニュアル格納されたファイルのindex要否チェック
                
                # dataverseとsharepoint file metadataのmodified dateを比較
                dataverse_last_modified_date = record_dict["cr261_pdf_last_modified_datetime"]
                pdf_file_name = record_dict["cr261_sharepoint_file_name"]
                
                # ファイルが同じ名称で置き換わっている可能性を考慮し、item_idでなくファイル名で取得
                get_file_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:{pdf_storage_directory_path}/{pdf_file_name}"
                sharepoint_file_metadata = graph_api_service.graph_api_get(get_file_url).json()
                logging.info(sharepoint_file_metadata)
                if '404error' in sharepoint_file_metadata:
                    logging.info(sharepoint_file_metadata)
                    status_to_be_inserted = 9
                    insert_to_be_registered = '1'
                else:
                    logging.info('not 404')
                    status_to_be_inserted = status
                    insert_to_be_registered = '0'

                # dataverseの更新
                record_dict["cr261_indexed"] = insert_to_be_registered
                record_dict["cr261_status"] = status_to_be_inserted
                
                sharepoint_last_modified_date = sharepoint_file_metadata["lastModifiedDateTime"]
                pdf_storage_id = sharepoint_file_metadata["id"]

                if dataverse_last_modified_date != sharepoint_last_modified_date:
                    logging.info('file must be changed')
                    # 前回手動格納(dataverseの記録)のあとにsharepointのファイルに変更があったということ
                    # 再度indexする必要あり。
                    record_dict["cr261_indexed"] = "0"
                    # ファイルが同じ名称で置き換わっている可能性を考慮し、item_idを上書きする
                    record_dict["cr261_sharepoint_item_id"] = pdf_storage_id
                    record_dict["cr261_pdf_last_modified_datetime"] = sharepoint_last_modified_date

                    # dataverseの書き込み
                    df_dictionary = pd.DataFrame([record_dict])                
                    result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")

                    # sharepointに変更があったが、statusが1の場合は後続の分岐処理で削除処理をおこなう。それ以外は次の行に進む。
                    if status != 1:
                        logging.info("task ended successfully")
                        logging.info("\ntask ended successfully")

                        return func.HttpResponse("record skipped")

            # status値による分岐処理：
            if status == 9:
                # ユーザーが確認する必要あり
                # 管理ファイル世代N+1に追記
                df_output = pd.concat([df_output, pd.DataFrame([record_dict])], axis=0, ignore_index=True)
                logging.info("staus is 9. skipping record")
                return func.HttpResponse("status is 9. skipping")

            elif status == 1:
                # sharepointのファイルを削除、dfのstatusを1に、indexedを0に、その他db整理
                item_id = record_dict["cr261_sharepoint_item_id"]
                logging.info(item_id)
                delete_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{item_id}"
                deletion_graph_data = graph_api_service.delete_file_from_sharepoint(delete_url)
                
                if deletion_graph_data:
                    # dictionary を更新する
                    record_dict["cr261_indexed"] = "0"
                    record_dict["cr261_status"] = 1
                    record_dict["cr261_pdf_last_modified_datetime"] = datetime(1970, 1, 1).strftime('%Y-%m-%dT%H:%M:%SZ')
                    # dataverseの書き込み
                    df_dictionary = pd.DataFrame([record_dict])                
                    result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")
                    # 管理ファイル世代N+1には記入しない　（行がなくなる）
                    
                    logging.info("ファイル削除成功")
                
            elif status == 0:
                
                # ファイルの再ダウンロード要否の確認が必要
                dataverse_last_modified_date = record_dict["cr261_pdf_last_modified_datetime"]

                # PDFファイル情報をwebから取得
                web_last_modified_date, pdf_file_name = graph_api_service.get_file_header_from_web(web_url=web_url)

                if 'empty' in web_last_modified_date:
                    logging.info('404')
                    status_to_be_inserted = 9
                    insert_to_be_registered = '1'
                if "status_302_continue" in web_last_modified_date:
                    return func.HttpResponse("download is skipped because organizaton is in black list")
                else:
                    logging.info('not 404')
                    status_to_be_inserted = status
                    insert_to_be_registered = '0'

                # ファイルがwebに存在しない場合や、ダウンロードに不備（サーバー側のスクレイピング制限等）があった場合statusを9に変更
                if web_last_modified_date is None and pdf_file_name is None:
                    status_to_be_inserted = 9    
                    
                    # dataverseの書き込み
                    df_dictionary = pd.DataFrame([record_dict])
                    result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")
                    
                    logging.info("ファイルダウンロード失敗")
                    

                # 更新がない場合ダウンロードをスキップ
                if web_last_modified_date == dataverse_last_modified_date and record_dict["cr261_status"] == 0:
                    logging.info("ファイル最終更新日が一致")
                    logging.info("ファイル最終更新日が一致")
                    return func.HttpResponse("download is skipped because file modified date is the same as header")
                
                # PDFファイル情報をwebから取得
                file_content = graph_api_service.download_file_from_web(web_url=web_url)

                # PDFファイルをsharepointへ格納
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
                record_dict["cr261_manual_flag"] = manual_flag
                record_dict["cr261_indexed"] = insert_to_be_registered
                record_dict["cr261_status"] = status_to_be_inserted

                # dataverseの書き込み
                df_dictionary = pd.DataFrame([record_dict])                
                result = dataverse_service.entity.upsert(data=df_dictionary, mode="individual")

            else:
                logging.error(f"staus error for {record_dict["cr261_pdf_url"]}")
                return func.HttpResponse("download is skipped because file modified date is the same as header")
            
            ### 行ごとの処理完了 ###
        
        logging.info("task ended successfully")
        logging.info("\ntask ended successfully")

        return func.HttpResponse("import pdf from external website to sharepoint ended")
    except Exception as e:
        logging.error(f"An error occurred in function: {e}", stack_info=True)
        return func.HttpResponse(
            "Internal Server Error",
            status_code=500
        )

# blueprint_function(req="aaa")