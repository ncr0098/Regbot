
import azure.functions as func
import logging
from datetime import datetime
import base64

from services.pdf_reader_service import PDFReaderService
from services.openai_service import OpenAIService
from services.text_processing_service import TextProcessingService
from services.indexer_service import IndexerService
from services.graph_api_service import GraphAPIService
from services.dataverse_service import DataverseService
import os
from dotenv import load_dotenv

app = func.FunctionApp(http_auth_level=func.AuthLevel.ADMIN)

@app.route(route="importFileToAISearch")
def importFileToAISearch(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    req_body = req.get_json()
    file_url = req_body.get('fileUrl')
    doc_dir = req_body.get('docDir')
    if file_url and doc_dir:
        logging.info(f"File URL: {file_url}")

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

        # EntraID、GraphAPI関連
        entra_client_id = os.getenv('ENTRA_CLIENT_ID')
        entra_client_secret = os.getenv('ENTRA_CLIENT_SECRET')
        entra_authority_url = os.getenv('ENTRA_AUTHORITY_URL')
        entra_tenant_id = os.getenv('ENTRA_TENANT_ID')
        graph_api_default_scope = os.getenv('GRAPH_API_DEFAULT_SCOPE')
        graph_api_resource = os.getenv('GRAPH_API_RESOURCE')
        power_platform_environment_url = os.getenv('POWER_PLATFORM_ENVIRONMENT_URL')
        dataverse_entity_name = os.getenv('DATAVERSE_ENTITY_NAME')

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
        indexer_service = IndexerService(indexer_api_key=indexer_api_key, indexer_endpoint=indexer_endpoint)
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
                                             , authority=entra_authority_url)

        # 本日日付時刻を取得
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存するファイル名を作成
        savefile_name= f"{current_time}_{file_url.split('/')[-1]}"

        # ファイルをダウンロードし、ダウンロード先の絶対パス入手
        absolute_path = graph_api_service.download_file_from_sharepoint(file_url=file_url, file_name=savefile_name)

        # テキスト抽出
        md_text = pdf_reader_service.read_pdf(file_path=absolute_path)

        # タイトル、要約抽出
        title, summary = text_processing_service.generate_title_and_summary(document_text=md_text)

        # キーワード抽出
        keywords = text_processing_service.generate_keywords(document_text=md_text)

        # 想定質問生成
        elaborated_question = text_processing_service.generate_elaborated_questions(title=title, summary=summary, keywords=keywords)

        # 組織の判別
        organization = text_processing_service.judge_organization_by_domain(url=file_url)

        # 登録日生成
        registered_date = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")

        id = base64.b64encode(f"{file_url}{registered_date}".encode()).decode()
        record = {
                    "id": id,
                    "URL": file_url,
                    "organization": organization,
                    "sentence": md_text,
                    "elaborated_question": elaborated_question,
                    "embedded_sentence": openai_service.generate_embeddings(md_text),
                    "embedded_elaborated_question": openai_service.generate_embeddings(elaborated_question),
                    "summary": summary,
                    "keywords": keywords,
                    "title": title,
                    "registered_date": registered_date,
                    "tokens_of_sentence": str(openai_service.num_tokens(md_text))
                }

        # AI Searchに登録
        indexer_service.register_record(record=record)
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
        