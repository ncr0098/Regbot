from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI

import tiktoken
import logging

class OpenAIService:
    def __init__(self, deployment_name, api_version, embedding_model_name, openai_api_key, openai_endpoint):
        self.llm = AzureChatOpenAI(
            azure_deployment=deployment_name,
            api_version=api_version,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2
        )
        self.embeddings = AzureOpenAIEmbeddings(
            model=embedding_model_name,
            azure_endpoint=openai_endpoint,
            api_key=openai_api_key
        )

    def call_openai_api(self, message, output_schema=None):
        try:
            if output_schema is not None:
                response = self.llm.with_structured_output(output_schema).invoke(message)
            else:
                response = self.llm.invoke(message)
            return response
        except Exception as e:
            logging.error(f"OpenAI API request error: {e}", stack_info=True)
            raise

    def generate_embeddings(self, text):
        try:
            return self.embeddings.embed_query(text)
        except Exception as e:
            logging.error(f"Embedding generation error: {e}", stack_info=True)
            raise

    def num_tokens(self, target: str):
        try:
            encoding = tiktoken.encoding_for_model("gpt-4o-mini")
            return len(encoding.encode(target))
        except Exception as e:
            logging.error(f"counting tokens error: {e}", stack_info=True)
            raise
