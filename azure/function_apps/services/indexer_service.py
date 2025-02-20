from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import (
    SimpleField,
    SearchFieldDataType,
    SearchableField,
    SearchField,
    SearchIndex,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SearchField,
    SemanticSearch,
    VectorSearch,
    VectorSearchAlgorithmKind,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchAlgorithmMetric,
    ExhaustiveKnnAlgorithmConfiguration,
    ExhaustiveKnnParameters,
    VectorSearchProfile,
    ScalarQuantizationCompression,
    ScalarQuantizationParameters
)
from models.model import Document
from pydantic import ValidationError
import logging

class IndexerService:
    def __init__(self, indexer_api_key, indexer_endpoint):
        self.indexer_api_key = indexer_api_key
        self.indexer_endpoint = indexer_endpoint
        self.index_name = "external_file_info"
        self.fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True, searchable=False, filterable=False, sortable=False, facetable=False),
                SearchableField(name="URL", type=SearchFieldDataType.String, facetable=True, filterable=True, sortable=True, analyzer_name="standard.lucene"),
                SearchableField(name="organization", type=SearchFieldDataType.String, facetable=True, filterable=True, sortable=True, analyzer_name="standard.lucene"),
                SearchField(name="sentence", type=SearchFieldDataType.Collection(SearchFieldDataType.String), facetable=False, filterable=False, analyzer_name="standard.lucene"),
                SearchableField(name="refined_question", type=SearchFieldDataType.String, facetable=True, filterable=True, sortable=True, analyzer_name="standard.lucene"),
                SearchField(name="embedded_sentence", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), searchable=True, vector_search_dimensions=1536, vector_search_profile_name='vectorConfig'),
                SearchField(name="embedded_refined_question", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), searchable=True, vector_search_dimensions=1536, vector_search_profile_name='vectorConfig'),
                SearchableField(name="summary", type=SearchFieldDataType.String, searchable=False, facetable=True, filterable=True, sortable=True),
                SearchField(name="keywords", type=SearchFieldDataType.Collection(SearchFieldDataType.String), facetable=True, filterable=True, analyzer_name="standard.lucene"),
                SearchableField(name="title", type=SearchFieldDataType.String, facetable=True, filterable=True, sortable=True, analyzer_name="standard.lucene"),
                SearchableField(name="registered_date", type=SearchFieldDataType.String, searchable=False, facetable=True, filterable=True, sortable=True),
                SearchableField(name="tokens_of_sentence", type=SearchFieldDataType.String, facetable=True, filterable=True, sortable=True, analyzer_name="standard.lucene"),
            ]
        self.vector_search_config = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="myHnsw",
                    kind=VectorSearchAlgorithmKind.HNSW,
                    parameters=HnswParameters(
                        m=4,
                        ef_construction=400,
                        ef_search=500,
                        metric=VectorSearchAlgorithmMetric.COSINE,
                    ),
                ),
                ExhaustiveKnnAlgorithmConfiguration(
                    name="myExhaustiveKnn",
                    kind=VectorSearchAlgorithmKind.EXHAUSTIVE_KNN,
                    parameters=ExhaustiveKnnParameters(
                        metric=VectorSearchAlgorithmMetric.COSINE,
                    ),
                ),
            ],
            profiles=[
                VectorSearchProfile(
                    name="vectorConfig",
                    algorithm_configuration_name="myHnsw",
                    compression_name="myCompression"
                ),
                # Add more profiles if needed
                VectorSearchProfile(
                    name="myExhaustiveKnnProfile",
                    algorithm_configuration_name="myExhaustiveKnn",
                ),
                # Add more profiles if needed
            ],
            compressions=[
                ScalarQuantizationCompression(
                    compression_name="myCompression",
                    rerank_with_original_vectors=True,
                    default_oversampling=10,
                    parameters=ScalarQuantizationParameters(
                        quantized_data_type="int8"
                    )
                )
            ],
        )

        semantic_config = SemanticConfiguration(
            name='my-semantic-config',
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name='title'),
                content_fields=[SemanticField(field_name='sentence')],
                keywords_fields=[SemanticField(field_name='keywords')],
            )
        )

        self.semantic_settings = SemanticSearch(configurations=[semantic_config])

    def create_index(self):
        # インデックスの定義
        index = SearchIndex(
            name=self.index_name,
            fields=self.fields,
            vector_search=self.vector_search_config,
            semantic_search=self.semantic_settings
        )

        # インデックスを作成するためのクライアント
        credential = AzureKeyCredential(self.indexer_api_key)

        client = SearchIndexClient(endpoint=self.indexer_endpoint, credential=credential)

        # インデックスを作成
        client.create_index(index)

    def register_records(self, records: list):
        
        try:
            # Pydanticモデルを使用して結果を検証
            [Document(**record) for record in records]

            # インデックスを作成するためのクライアント
            credential = AzureKeyCredential(self.indexer_api_key)

            # インデックスにデータを追加するためのクライアント
            search_client = SearchClient(endpoint=self.indexer_endpoint, index_name=self.index_name, credential=credential)

            # データをAzure Cognitive Searchに登録
            result = search_client.upload_documents(documents=records)

            status = getattr(result, "status_code")
            
            if status != 200 and status != 201:
                logging.error(getattr(result, "error_message"))
                raise Exception
            logging.info("Document uploaded successfully.")

        except ValidationError as e:
            logging.error(f"Validation error: {e.json()}")
            raise

    def delete_record(self, query: list):
         # インデックスを作成するためのクライアント
        credential = AzureKeyCredential(self.indexer_api_key)

        # インデックスにデータを追加するためのクライアント
        search_client = SearchClient(endpoint=self.indexer_endpoint, index_name=self.index_name, credential=credential)
        result = search_client.delete_documents(documents=query)

        print("Delete new document succeeded: {}".format(result[0].succeeded))