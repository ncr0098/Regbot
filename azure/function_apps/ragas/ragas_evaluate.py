
import azure.functions as func
import logging
from datetime import datetime
import base64

import os, sys

from os.path import dirname, join
from dotenv import load_dotenv
dotenv_path = join(dirname(__file__), ".env.local")
load_dotenv(dotenv_path=dotenv_path)
sys.path.append(os.getenv("LOCAL_PROJECT_ROOT"))

from services.pdf_reader_service import PDFReaderService
from services.openai_service import OpenAIService
from services.text_processing_service import TextProcessingService
from services.indexer_service import IndexerService
from services.graph_api_service import GraphAPIService
from services.dataverse_service import DataverseService


def main():

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

    logging.info(f"client_id: {entra_client_id}, client_secret: {entra_client_secret}, authority: {entra_authority_url}, tennant_id: {entra_tenant_id}")

    # 各種サービス初期化
    pdf_reader_service = PDFReaderService()
    openai_service = OpenAIService(
        deployment_name=deployment_name
        , api_version=azure_openai_api_version
        , embedding_model_name=embedding_model_name
        , openai_api_key=azure_openai_api_key
        , openai_endpoint=azure_openai_endpoint
        )
    # text_processing_service = TextProcessingService(openai_service=openai_service)
    # indexer_service = IndexerService(indexer_api_key=indexer_api_key,
    #                                      indexer_endpoint=indexer_endpoint,
    #                                      indexer_name=indexer_name)
    # graph_api_service = GraphAPIService(
    #     client_id=entra_client_id
    #     , client_secret=entra_client_secret
    #     , tenant_id=entra_tenant_id
    #     , authority=entra_authority_url
    #     , scope=[graph_api_default_scope]
    #     , resource=graph_api_resource
    #     )
    # dataverse_service = DataverseService(environment_url=power_platform_environment_url
    #                                         , entra_client_id=entra_client_id
    #                                         , entra_client_secret=entra_client_secret
    #                                         , authority=entra_authority_url
    #                                         , entity_logical_name=dataverse_entity_name)
    # RAG setup
    from ragas import evaluate, SingleTurnSample, EvaluationDataset
    from ragas.metrics import (
        context_precision, # コンテキストを正確に取得できているか
        answer_relevancy, # 質問に対して簡潔かつ適切に回答しているか
        faithfulness, # コンテキストに基づいて回答しているか
        context_recall, # 教師データからコンテキストをどの程度再現できるか
        answer_similarity, # 回答が教師データとどの程度類似しているか
        answer_correctness # 回答がどの程度正確か
    )

    # 読み込み対象ドキュメントの絶対パス
    # 現時点ではドキュメントの全文をコンテキストに組み込むうえ、
    # 参照ページや引用文がハルシネーションを起こすため、全文を読み込む
    # 
    # context_absolute_paths = [
    #    "C:\\Users\\ncr0098\\project\\regbot\\Regbot\\azure\\function_apps\\ragas\\docs\\1713bp1.pdf" 
    #    ,"C:\\Users\\ncr0098\\project\\regbot\\Regbot\\azure\\function_apps\\ragas\\docs\\guideline-quality-oral-modified-release-products_en.pdf"
    #    ,"C:\\Users\\ncr0098\\project\\regbot\\Regbot\\azure\\function_apps\\ragas\\docs\\note-guidance-development-pharmaceutics_en.pdf"
    #    ,"C:\\Users\\ncr0098\\project\\regbot\\Regbot\\azure\\function_apps\\ragas\\docs\\reflection-paper-dissolution-specification-generic-solid-oral-immediate-release-products-systemic-action-first-version_en.pdf"
    #    ,"C:\\Users\\ncr0098\\project\\regbot\\Regbot\\azure\\function_apps\\ragas\\docs\\SUPAC-IR--Immediate-Release-Solid-Oral-Dosage-Forms--Scale-Up-and-Post-Approval-Changes--Chemistry--Manufacturing-and-Controls--In-Vitro-Dissolution-Testing--and-In-Vivo.pdf"
    # ]
    # contexts = []
    # for ab in context_absolute_paths:
    #     contexts.append(pdf_reader_service.read_pdf(ab))

    # ユーザーが最初に入力した質問
    user_input = """
    Are there any recommendations that specify information regarding the in-use shelf life of sterile drug product?

    """

    # retrieved_contexts = contexts

    # コンテキスト
    # LLMの最終回答に記載されている引用文を利用場合はこちらを使用
    retrieved_contexts = [
         "The applicant should justify the values of z and t on a case by case basis; z should not normally be greater than 28 days."
        , "The purpose of in-use stability testing is to establish - where applicable - a period of time during which a multidose product can be used whilst retaining quality within an accepted specification once the container is opened."
        , "The registration dossier for a multi-dose product should include either the in-use stability data on which the in-use shelf life is based or a justification why no in-use shelf life is established."
        , "Testing the efficacy of the preservative system should be conducted according to the test method of the European Pharmacopoeia."
        , "...testing programme should allow the assignment of an 'in-use shelf life' for the product which will subsequently appear on the product literature."
    ]

    # LLMの最終回答
    response = """
    Recommendations regarding the in-use shelf life of sterile drug products are provided in various guidance documents. Specifically, the guidance states that for sterile products, the in-use stability should be demonstrated based on appropriate studies. For instance, the guidance on maximum shelf-life for sterile products for human use after first opening or following reconstitution indicates that chemical and physical in-use stability has to be demonstrated for specific hours or days at certain temperatures. Specifically, for aqueous preserved sterile products, the in-use time may not exceed a maximum of z days at t °C, typically not greater than 28 days. Additionally, the in-use stability testing of human medicinal products outlines that the purpose is to establish a period during which a multidose product can be safely used while retaining quality. Therefore, testing for physical, chemical, and microbial properties should be conducted under normal conditions of use. The relevant data should be included in the registration dossier, and if no in-use shelf life is established, a justification must be provided.

    """

    # 模範解答
    reference = """
    ・For Single-use formulations, it is stated that In-use storage is possible without Micro Study up to 4 hours at room temperature and 24 hours refrigeration.
    ・If not used immediately, in-use storage times and conditions are the responsibility of the user. Form a microbiological point of view, the product would normally not be longer than 24 hours at 2-8°C.
    ・provides guidance on the test items for in-use studies. Additionally, Section 5 presents the related Q&A.

    """

    sample = SingleTurnSample(
        user_input=user_input,
        retrieved_contexts=retrieved_contexts,
        response=response,
        reference=reference,
    )

    dataset = EvaluationDataset(samples=[sample])

    # list of metrics we're going to use
    metrics = [
        faithfulness,
        answer_relevancy,
        context_recall,
        context_precision,
        answer_correctness,
        answer_similarity
    ]
    result = evaluate(
        dataset, metrics=metrics, llm=openai_service.llm, embeddings=openai_service.embeddings
    )

    print(result)

main()
        