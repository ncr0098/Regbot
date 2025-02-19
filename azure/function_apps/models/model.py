from pydantic import BaseModel, Field

class TitleAndSummary(BaseModel):
    title: str = Field(..., title="文書のタイトル")
    summary: str = Field(..., title="文書の要約")
    
class Keywords(BaseModel):
    keywords: list[str] = Field(..., title="文書のキーワード")
    
class RefinedQuestion(BaseModel):
    question: str = Field(..., title="想定質問")
    
class RefinedQuestionWithFactor(BaseModel):
    question_background: str = Field(..., title="問いの背景")
    question_purpose: str = Field(..., title="問いの目的")
    answer_scope: str = Field(..., title="回答のスコープ")
    detailed_questions: list[str] = Field(..., title="詳細化した質問")
    additional_questions: list[str] = Field(..., title="追加質問")

class Document(BaseModel):
    id: str
    URL: str
    organization: str
    sentence: list
    refined_question: str
    embedded_sentence: list[float]
    embedded_refined_question: list[float]
    summary: str
    keywords: list[str]
    title: str
    registered_date: str
    tokens_of_sentence: str