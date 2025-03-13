from services.openai_service import OpenAIService
from models.model import TitleSummaryKeywords, Keywords, RefinedQuestion
import logging

class TextProcessingService:
    def __init__(self, openai_service: OpenAIService):
        self.openai_service = openai_service

    def judge_organization_by_domain(self, url):
        org = ""
        if "www.pmda.go.jp" in url:
            org = "PMDA"
        elif "www.ema.europa.eu" in url:
            org = "EMA"
        elif "www.fda.gov" in url:
            org = "FDA"
        elif "database.ich.org" in url:
            org = "ICH"
        elif "www.mhlw.go.jp" in url:
            org = "JP"
        else:
            org = "no match"
        return org

    
    def generate_title_summary_keywords(self, document_text):
        try:
            message = f"""Execute followings.
            1. Generate a title, summary and extract about less than 20 keywords for the following document.
            ===DOCUMENT TEXT START===
            {document_text}
             ===DOCUMENT TEXT END===

             2. Confirm whether output is written in English. If not, translate it into English.

            NOTE: Output MUST be English.
            """
            title_and_summary = self.openai_service.call_openai_api(message=message, output_schema=TitleSummaryKeywords)

            return title_and_summary.title, title_and_summary.summary, title_and_summary.keywords
        except Exception as e:
            logging.error(f"generating title and summary error: {e}", stack_info=True)
            raise
    
    def generate_keywords(self, document_text):
        try:
            message = f"""Execute followings.
            1. Extract about less than 20 keywords from the following text.
            ===TEXT START===
            {document_text}
             ===TEXT END===
            
            2. Confirm whether output is written in English. If not, translate it into English.

            NOTE: Output MUST be English.
            """
            keywords = self.openai_service.call_openai_api(message=message, output_schema=Keywords)

            return keywords.keywords
        except Exception as e:
            logging.error(f"generating keywords error: {e}", stack_info=True)
            raise
    
    def generate_refined_questions(self, title, summary, keywords):
        try:
            questions_prompt = f"""You are a specialist in summarizing text and creating titles, as well as anticipating the content of a text and related questions based on parts of the original text. 
            This prompt is intended to elaborate and clarify potential questions related to the content of the document.
            Create question according to the instructions. If additional questions or instructions are input by the user, please revise the content accordingly and output it again.

    
    <<document title>>{title}
    <<document summary>>{summary}
    <<keywords in document>>{keywords}
    
    ====

## Instructions :
### 1. Background of the question :
- Estimate from the information in the question.
- Describe specifically in three or more sentences.

### 2. Purpose of the question :
- Estimate from the information in the question.
- Describe specifically in three or more sentences.

### 3. Scope of the answer :
- Estimate from the information in the question.

### 4. Detailed questions :
Organize the information from the question to clarify the requirements
- Divide the questions into units where answers are needed and number them as a, b, c...Ensure that a, b, c can be answered independently with sufficient explanation.
- Each question should be clear in terms of the 5W1H (who, what, when, where, why, how) and answerable by reading the question alone.
- Indicate the elements that should be included in the answer for each question.

### 5. Additional questions :
You need to attach three additional follow-up questions to the user's question. The rules for additional questions are defined as follows.
Do not repeat questions that have already been asked.
Do not include "source" in follow-up questions.
Follow-up questions should serve as ideas to expand the user's curiosity. For example, consider questions about the effects, side effects, and usage of the drug.
Only generate questions, do not generate text such as "next question" before or after the questions.
Example:
Q: What are the effects of this drug? 
A: This drug has pain-relieving effects. It also has anti-inflammatory properties. 
- What are the main side effects of this drug?
- What precautions should be taken when using this drug?
- Are there other drugs with similar effects?

### 6. Usage scenario :
- Estimate from the information in the question.
- Clarify who will use the answer and how it will be used.
    """
            question = self.openai_service.call_openai_api(message=questions_prompt, output_schema=RefinedQuestion)

            return question.question
        except Exception as e:
            logging.error(f"generating refined question error: {e}", stack_info=True)
            raise

    def process_text(self, text):
        try:
            embedding = self.openai_service.generate_embeddings(text)
            keywords = self.generate_keywords(text)
            summary, title = self.generate_title_and_summary(text)
            question = self.generate_refined_questions(title, summary, keywords)

            return {
                "embedding": embedding,
                "keywords": keywords,
                "summary": summary,
                "title": title,
                "question": question
            }
        except Exception as e:
            logging.error(f"Error processing text: {e}", stack_info=True)
            raise