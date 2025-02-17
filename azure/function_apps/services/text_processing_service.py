from services.openai_service import OpenAIService
from models.model import TitleAndSummary, Keywords, ElaboratedQuestion

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

    
    def generate_title_and_summary(self, document_text):
        message = f"Generate a title and summary for the following document.{document_text}"
        title_and_summary = self.openai_service.call_openai_api(message=message, output_schema=TitleAndSummary)

        return title_and_summary.title, title_and_summary.summary
    
    def generate_keywords(self, document_text):
        message = f"Extract about less than 20 keywords from the following text.{document_text}"
        keywords = self.openai_service.call_openai_api(message=message, output_schema=Keywords)

        return keywords.keywords
    
    def generate_elaborated_questions(self, title, summary, keywords):
        questions_prompt = f"""あなたは、文章の要約やタイトルなど、元の文章の内容の一部から想定される文章の内容やそれに関する質問の想定に長けています。このプロンプトは文書の内容に対して想定される質問を詳細化し明確化するためのものです。

 
<<文書のタイトル>>{title}
<<文書の要約>>{summary}
<<文書のキーワード>>{keywords}
ｘｘｘｘｘｘ
 
====
 
上記の問いについて①～⑥を明確にして、整理された質問に変換してください。
 
<<アウトプットフォーマット>>を参照して最終的に出力する際には””内はそのまま一切変更せず出力してください。
 
 
①問いの背景、②問いの目的、③回答のスコープ、④詳細化した質問、⑤追加質問、⑥利用イメージ
 
①問いの背景
 
・問いの情報から推定してください。
 
・具体的に、３文以上で記載してください。
 
 
②問いの目的
 
・問いの情報から推定してください。
 
・具体的に、３文以上で記載してください。
 
 
③回答のスコープ
 
・問いの情報から推定してください。
 
 
④詳細化した質問・問いの情報を整理して要件を明確にした質問
 
・質問は答えが欲しい単位に区切ってa,b,c・・・と番号をつけて箇条書きにしてください。
 
　　・a,b,cはそれぞれ単独で読んで回答できるように説明を充実させる
 
　　・それぞれの質問は5W1Hが明確である（質問文だけ読んで回答できる）
 
・それぞれの問いについて回答に含めるべき要素を提示してください。
 
⑤追加質問：
 
回答には、ユーザの質問に対する追加の3つの追加質問を添付する必要があります。追加質問のルールは以下に定義されています。
 
質問を参照する際は二重山括弧を使用してください。例：<<この薬の主な効果は何ですか？>>。
 
既に尋ねられた質問を繰り返さないようにしてください。
 
フォローアップの質問に「出典」を追加しないでください。
 
箇条書きのフォローアップ質問は使用せず、常に二重山括弧で囲んでください。
 
フォローアップの質問は、ユーザの好奇心を広げるアイデアとなるようにしてください。例えば、薬の効果、副作用、使用方法などについての質問を考えてみてください。
 
質問の生成のみ行い、質問の前後に「次の質問」などのテキストは生成しないでください。
 
 
EXAMPLE:###
 
Q:この薬はどのような効果がありますか？
 
A:この薬は、痛みを和らげる効果があります。また、炎症を抑える作用もあります。
 
<<この薬の主な副作用は何ですか？>>
 
<<この薬を使用する際の注意点は何ですか？>>
 
<<他にも同じような効果を持つ薬はありますか？>>
 
 
⑥利用イメージ
 
・問いの情報から推定してください。
 
・「誰がどのように回答を利用」するか明確にしてください。

<<アウトプットフォーマット>>
 
①背景：XXX
 
②目的：XXX
 
③スコープ：XXX
 
④質問
 
　・a. XXX
 
　・b. XXX
 
　・c. ・・・
 
⑤追加質問
 
　・XXX
 
　・XXX
 
　・・・
 
 
⑥利用イメージ
 
・XXX。
"""
        question = self.openai_service.call_openai_api(message=questions_prompt, output_schema=ElaboratedQuestion)

        return question.question

    def process_text(self, text):
        try:
            embedding = self.openai_service.generate_embeddings(text)
            keywords = self.generate_keywords(text)
            summary, title = self.generate_title_and_summary(text)
            question = self.generate_elaborated_questions(title, summary, keywords)

            return {
                "embedding": embedding,
                "keywords": keywords,
                "summary": summary,
                "title": title,
                "question": question
            }
        except Exception as e:
            print(f"Error processing text: {e}")
            raise