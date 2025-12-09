import os
from fastmcp import FastMCP
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)
from langchain_community.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

mcp = FastMCP("pdf-rag")

vectorstore = None
embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

PROMPT = ChatPromptTemplate.from_template("""
PDF 기반 응답

질문: {question}

문맥:
{context}
""")


async def rag(question: str):
    retriever = vectorstore.as_retriever()
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

    chain = (
        {"context": retriever, "question": lambda x: x["question"]}
        | PROMPT
        | llm
        | StrOutputParser()
    )
    return chain.invoke({"question": question})


@mcp.tool
def upload_pdf(file_path: str) -> str:
    """PDF를 임베딩합니다."""
    global vectorstore
    if not os.path.exists(file_path):
        return "⚠️ 파일을 찾을 수 없습니다."

    docs = PyPDFLoader(file_path).load()
    vectorstore = FAISS.from_documents(docs, embeddings)
    return f"📚 PDF 색인 완료 ({len(docs)} 페이지)"


@mcp.tool
async def summarize() -> str:
    """문서 전체 요약"""
    if vectorstore is None:
        return "📂 먼저 upload_pdf 호출해주세요!"

    summary = await rag("문서를 핵심만 요약")
    return "📌 Summary:\n" + summary


@mcp.tool
async def ask(question: str) -> str:
    """문서 기반 질문 응답"""
    if vectorstore is None:
        return "📂 먼저 upload_pdf 호출해주세요!"

    answer = await rag(question)
    return "💬 Answer:\n" + answer


if __name__ == "__main__":
    mcp.run()
