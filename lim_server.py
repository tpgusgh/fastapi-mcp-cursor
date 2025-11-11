# 완전한 SSE 기반 LangChain + FastAPI + MCP 서버 예제 (에이전트 포함)

import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

from fastapi import FastAPI, Request  # FastAPI를 사용한 웹 서버 및 HTTP 요청 처리
from langchain_google_genai import ChatGoogleGenerativeAI  # LangChain에서 Google의 LLM(Gemini) 사용
from mcp.server.fastmcp import FastMCP  # MCP 서버를 빠르게 구성하는 헬퍼 클래스
from mcp.server.sse import SseServerTransport  # SSE 통신을 위한 MCP 전송 계층
from starlette.routing import Mount, Route  # FastAPI의 라우팅 설정을 위한 Starlette 모듈
import uvicorn  # FastAPI 앱을 실행하기 위한 서버 라이브러리

llm = ChatGoogleGenerativeAI(model="models/gemini-pro-latest", google_api_key=os.getenv("GEMINI_API_KEY"))

# MCP 서버 초기화 ("chatbot"이라는 이름으로 MCP 서버 생성, LLM을 내부에 주입)
mcp = FastMCP("chatbot")

# 단순 대화용 MCP 툴 정의
@mcp.tool()
async def chat(input: str) -> str:
    """LLM과 일반적인 대화를 수행합니다."""
    result = await llm.ainvoke(input)  # Gemini에게 입력을 비동기로 전달하고 응답을 받음

    # 결과가 LangChain의 AIMessage 객체인 경우 .content 속성에서 실제 응답 추출
    raw_content = str(result.content) if hasattr(result, "content") else str(result)
    # UnicodeEncodeError 방지를 위해 서로게이트 문자를 교체하여 인코딩 후 디코딩
    return raw_content.encode('utf-8', 'replace').decode('utf-8')

# SSE 서버 전송 계층 설정 ("/messages/" 경로로 POST 및 스트리밍 처리)
sse = SseServerTransport("/messages/")

# SSE 연결을 처리하는 엔드포인트 함수 정의
async def handle_sse(request: Request) -> None:
    # 클라이언트와의 SSE 연결을 수립하고, MCP 서버의 메인 처리 루프를 실행
    async with sse.connect_sse(
        request.scope,        # HTTP 요청의 범위 정보
        request.receive,      # 클라이언트로부터 메시지 수신
        request._send,        # 클라이언트로 메시지 전송
    ) as (read_stream, write_stream):  # 읽기/쓰기 스트림 확보
        await mcp._mcp_server.run(  # 내부 MCP 서버 실행 (비공식 내부 API 사용)
            read_stream,             # 입력 스트림
            write_stream,            # 출력 스트림
            mcp._mcp_server.create_initialization_options(),  # 초기화 옵션 설정
        )

# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(
    debug=True,  # 디버그 모드 활성화
    routes=[
        Route("/sse", endpoint=handle_sse),  # 실시간 SSE 연결 핸들러 등록
        Mount("/messages/", app=sse.handle_post_message),  # 메시지 POST 처리용 경로 등록
    ],
)

# Python 스크립트가 직접 실행될 경우, uvicorn으로 FastAPI 서버 실행
if __name__ == "__main__":
    uvicorn.run("llm_server:app", host="127.0.0.1", port=3000, reload=True)
    # "llm_server"는 현재 파일명 (llm_server.py 여야 함)
    # reload=True는 코드 변경 시 자동 재시작 기능 (개발 편의)