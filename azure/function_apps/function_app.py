
import azure.functions as func
import logging

from test_blueprint import bp
from create_master_blueprint import create_master_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_blueprint(bp)
app.register_blueprint(create_master_bp)

@app.function_name(name="importFileToAISearch")
@app.route(route="importFileToAISearch") # HTTP Trigger
def importFileToAISearch(req: func.HttpRequest) -> func.HttpResponse:
    from datetime import datetime, timedelta
    import base64

    from services.pdf_reader_service import PDFReaderService
    from services.openai_service import OpenAIService
    from services.text_processing_service import TextProcessingService
    from services.indexer_service import IndexerService
    from services.graph_api_service import GraphAPIService
    from services.dataverse_service import DataverseService
    import os,re
    import urllib.parse
    from dotenv import load_dotenv
    try:
        logging.info('Python HTTP trigger function processed a request.')

        req_body = req.get_json()

        # .envファイルを読み込む
        load_dotenv()

        # AzureOpenAI関連
        azure_openai_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        deployment_name = os.getenv('DEPLOYMENT_NAME')
        azure_openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
        embedding_model_name = os.getenv('EMBEDDING_MODEL_NAME')

        # AI Search関連
        indexer_api_key = os.getenv('INDEXER_API_KEY')
        indexer_endpoint = os.getenv('INDEXER_ENDPOINT')
        indexer_name = os.getenv('INDEXER_NAME')

        # EntraID、GraphAPI関連
        entra_client_id = os.getenv('ENTRA_CLIENT_ID')
        entra_client_secret = os.getenv('ENTRA_CLIENT_SECRET')
        entra_authority_url = os.getenv('ENTRA_AUTHORITY_URL')
        entra_tenant_id = os.getenv('ENTRA_TENANT_ID')
        graph_api_default_scope = os.getenv('GRAPH_API_DEFAULT_SCOPE')
        graph_api_resource = os.getenv('GRAPH_API_RESOURCE')
        power_platform_environment_url = os.getenv('POWER_PLATFORM_ENVIRONMENT_URL')
        dataverse_entity_name = os.getenv('DATAVERSE_ENTITY_NAME')
        site_id = os.getenv("SITE_ID")
        drive_id = os.getenv("DRIVE_ID")

        # 各種サービス初期化
        pdf_reader_service = PDFReaderService()
        openai_service = OpenAIService(
            deployment_name=deployment_name
            , api_version=azure_openai_api_version
            , embedding_model_name=embedding_model_name
            , openai_api_key=azure_openai_api_key
            , openai_endpoint=azure_openai_endpoint
            )
        text_processing_service = TextProcessingService(openai_service=openai_service)
        indexer_service = IndexerService(indexer_api_key=indexer_api_key,
                                         indexer_endpoint=indexer_endpoint,
                                         indexer_name=indexer_name)
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
        
        # レコード取得
        item = req_body["record"]

        records_for_aisearch = []
        records_for_upsert_dataverse = []

        item_dbmodel = dataverse_service.transform_record_dict_to_model_instance(item)
        directory_path = item_dbmodel.cr261_sharepoint_directory
        object_file_name = item_dbmodel.cr261_sharepoint_file_name
        # APIエンドポイント
        file_url = f' https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:{directory_path}/{object_file_name}:/content'

        
        if item_dbmodel.cr261_status == 1:
            logging.info("start delete record from AI Search")
            indexer_service.delete_record({"id": item_dbmodel.cr261_sharepoint_item_id})
            logging.info("done delete record from AI Search")
        else:
            # 本日日付時刻を取得
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 保存するファイル名を作成
            savefile_name= f"{current_time}_{file_url.split('/')[-1]}"

            
            # GraphAPIのアクセストークンは1時間で切れてしまう
            if datetime.now() >= graph_api_service.token_expires_at - timedelta(minutes=5):
                graph_api_service.access_token  = graph_api_service.fetch_access_token([graph_api_default_scope])
                logging.info("graph api token refreshed")
            # ファイルをダウンロードし、ダウンロード先の絶対パス入手
            absolute_path = graph_api_service.download_file_from_sharepoint(file_url=file_url, file_name=savefile_name)
            logging.info(f"pdf downloaded to {absolute_path}")

            # テキスト抽出
            logging.info("start reading pdf")
            md_text = pdf_reader_service.read_pdf(file_path=absolute_path)
            logging.info("done reading pdf")

            # タイトル、要約、キーワード抽出
            logging.info("start generating title, summary, keywords")
            title, summary, keywords = text_processing_service.generate_title_summary_keywords(document_text=md_text)
            logging.info("done generating title, summary, keywords")

            # 想定質問生成
            logging.info("start generating refined question")
            refined_question = text_processing_service.generate_refined_questions(title=title, summary=summary, keywords=keywords)
            logging.info("done generating refined question")
            
            organization = item_dbmodel.cr261_source_name

            # 登録日生成
            registered_date = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")

            LETTERS_PER_FACTOR = 16382 # AI Searchに格納するために分割するbyte数の単位
            text_list = [ md_text [ i:i+ LETTERS_PER_FACTOR] for i in range( 0, len(md_text),LETTERS_PER_FACTOR)]

            id = base64.b64encode(f"{file_url}{registered_date}".encode()).decode()
            # Keys can only contain letters, digits, underscore (_), dash (-), or equal sign (=).
            id = re.sub(r'[^a-zA-Z0-9_\-=]', '', id)
            record = {
                        "id": id,
                        "URL": item_dbmodel.cr261_sharepoint_url,
                        "organization": organization,
                        "sentence": text_list,
                        "refined_question": refined_question,
                        "embedded_sentence": openai_service.generate_embeddings(md_text),
                        "embedded_refined_question": openai_service.generate_embeddings(refined_question),
                        "summary": summary,
                        "keywords": keywords,
                        "title": title,
                        "filename": urllib.parse.unquote(item_dbmodel.cr261_sharepoint_file_name),
                        "registered_date": registered_date,
                        "tokens_of_sentence": str(openai_service.num_tokens(md_text))
                    }
            records_for_aisearch.append(record)
            logging.info("start register record to AI Search")
            indexer_service.register_records(records=records_for_aisearch)
            logging.info("done register record to AI Search")

        # AISearchに対して削除だろうと登録だろうと、Dataverseの該当レコードには更新が発生
        item_dbmodel.cr261_indexed = "1"
        records_for_upsert_dataverse.append(item_dbmodel)

        # Dataverseの該当レコードをアップデート
        logging.info("start update record on Dataverse")
        dataverse_service.update_client_and_entity_with_newest_session(dataverse_entity_name)
        result = dataverse_service.entity.upsert(data=[model.dict(by_alias=True) for model in records_for_upsert_dataverse], mode="batch")
        status_code = result[0].status_code
        if status_code >= 300: # ステータスコードがIntで返ってくることを利用して表現
            logging.error(result[0].text)
            raise Exception
        
        logging.info("done update record on Dataverse")

        return func.HttpResponse(
            "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error occured: {e}")