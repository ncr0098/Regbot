
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
    # RAG setup
    from ragas import evaluate
    from ragas.metrics import (
        context_precision,
        answer_relevancy,
        faithfulness,
        context_recall,
    )

    from ragas import SingleTurnSample, EvaluationDataset
    # Sample 1
    sample1 = SingleTurnSample(
        user_input="What is the capital of Germany?",
        retrieved_contexts=["Berlin is the capital and largest city of Germany."],
        response="The capital of Germany is Berlin.",
        reference="Berlin",
    )

    # Sample 2
    sample2 = SingleTurnSample(
        user_input="Who wrote 'Pride and Prejudice'?",
        retrieved_contexts=["'Pride and Prejudice' is a novel by Jane Austen."],
        response="'Pride and Prejudice' was written by Jane Austen.",
        reference="Jane Austen",
    )

    # Sample 3
    sample3 = SingleTurnSample(
        user_input="What's the chemical formula for water?",
        retrieved_contexts=["Water has the chemical formula H2O."],
        response="The chemical formula for water is H2O.",
        reference="H2O",
    )
    dataset = EvaluationDataset(samples=[sample1, sample2, sample3])
    # from datasets import load_dataset

    # amnesty_qa = load_dataset("explodinggradients/amnesty_qa", "english_v2")
    # amnesty_qa

    # list of metrics we're going to use
    metrics = [
        faithfulness,
        answer_relevancy,
        context_recall,
        context_precision,
    ]
    result = evaluate(
        dataset, metrics=metrics, llm=openai_service.llm, embeddings=openai_service.embeddings
    )

    print(result)

main()
        