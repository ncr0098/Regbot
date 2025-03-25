from pydantic import BaseModel, Field
from typing import Optional

class TitleSummaryKeywords(BaseModel):
    title: str = Field(..., title="文書のタイトル")
    summary: str = Field(..., title="文書の要約")
    keywords: list[str] = Field(..., title="文書のキーワード")
    
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

class DataversePdfStatus(BaseModel):
    odata_etag: Optional[str] = Field(None, alias='@odata.etag')
    _createdby_value: Optional[str] = None
    cr261_pdf_storageid: Optional[str] = None
    statuscode: Optional[int] = None
    cr261_pdf_url: Optional[str] = None
    _modifiedonbehalfby_value: Optional[str] = None
    importsequencenumber: Optional[int] = None
    _owningbusinessunit_value: Optional[str] = None
    overriddencreatedon: Optional[str] = None
    cr261_source_name: Optional[str] = None
    _owninguser_value: Optional[str] = None
    cr261_sharepoint_url: Optional[str] = None
    utcconversiontimezonecode: Optional[int] = None
    _owningteam_value: Optional[str] = None
    _createdonbehalfby_value: Optional[str] = None
    cr261_indexed: Optional[str] = None
    modifiedon: Optional[str] = None
    _modifiedby_value: Optional[str] = None
    versionnumber: Optional[int] = None
    statecode: Optional[int] = None
    _ownerid_value: Optional[str] = None
    timezoneruleversionnumber: Optional[int] = None
    cr261_pdf_last_modified_datetime: Optional[str] = None
    cr261_status: Optional[int] = None
    createdon: Optional[str] = None
    cr261_timestamp: Optional[str] = None
    cr261_sharepoint_item_id: Optional[str] = None
    cr261_sharepoint_directory: Optional[str] = None
    cr261_sharepoint_file_name: Optional[str] = None
    cr261_manual_flag: Optional[int] = None
