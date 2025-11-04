#explorer-server/main.py
import os
import logging
from datetime import datetime
from mcp.server.fastmcp import FastMCP
import subprocess
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)

# MCP 서버 인스턴스
mcp = FastMCP("File-Search")

# ---- macOS용 기본 설정 ----
# 기본 루트: 사용자 홈 디렉터리. 필요 시 환경변수 FILE_SEARCH_ROOT 로 재정의 가능.
ROOT_DIR = os.path.expanduser(os.environ.get("FILE_SEARCH_ROOT", "~"))

# 숨김 디렉터리/시스템 경로 등 제외하고 싶으면 여기에 패턴 추가
EXCLUDE_DIR_NAMES = {".git", ".Trash", ".Spotlight-V100", ".fseventsd", ".DS_Store", "node_modules"}
EXCLUDE_PATH_PREFIXES = [
    os.path.expanduser("~/Library/Caches"),
    os.path.expanduser("~/Library/Containers/com.apple.Safari/Data"),
]

def _is_excluded(dirpath: str) -> bool:
    # 경로 접두어 기반 제외
    for p in EXCLUDE_PATH_PREFIXES:
        if dirpath.startswith(p):
            return True
    # 폴더명 기반 제외
    base = os.path.basename(dirpath)
    if base in EXCLUDE_DIR_NAMES:
        return True
    return False

def _fmt_datetime_from_stat(stat) -> str:
    # macOS: st_birthtime 이 있으면 '생성일', 없으면 수정시간으로 대체
    ts = getattr(stat, "st_birthtime", None)
    if ts is None:
        ts = stat.st_mtime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

# 파일 검색
def search_files(keyword: str, base_path: str = ROOT_DIR, max_results: int = 20) -> List[Dict]:
    results: List[Dict] = []
    base_path = os.path.expanduser(base_path)

    for dirpath, dirnames, filenames in os.walk(base_path, followlinks=False):
        # 제외 디렉터리 필터링
        if _is_excluded(dirpath):
            # 하위 순회를 막기 위해 dirnames를 비워버림
            dirnames[:] = []
            continue

        # 숨김 폴더 대량 순회 방지: 필요 시 아래 주석 해제
        # dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for fname in filenames:
            try:
                if keyword.lower() in fname.lower():
                    fpath = os.path.join(dirpath, fname)
                    stat = os.stat(fpath)
                    results.append({
                        "파일명": fname,
                        "경로": fpath,
                        "크기(Bytes)": stat.st_size,
                        "생성일": _fmt_datetime_from_stat(stat),
                    })
                    if len(results) >= max_results:
                        return results
            except Exception as e:
                logging.warning(f"파일 접근 오류: {os.path.join(dirpath, fname)} - {e}")
                continue

    return results

@mcp.tool()
def find_file(keyword: str, base_path: Optional[str] = None, max_results: int = 20) -> str:
    """
    macOS에서 파일명을 기준으로 키워드에 해당하는 파일을 검색합니다.
    - keyword: 포함 검색(대소문자 무시)
    - base_path: 검색 시작 경로(기본값: 사용자 홈). 환경변수 FILE_SEARCH_ROOT로도 설정 가능
    - max_results: 최대 결과 개수
    """
    root = base_path or ROOT_DIR
    logging.info(f"🔍 '{keyword}' 키워드로 파일 검색 시작 (root={root}, max={max_results})")

    found = search_files(keyword, base_path=root, max_results=max_results)
    if not found:
        return f"'{keyword}'에 해당하는 파일을 찾을 수 없습니다. (검색 루트: {os.path.expanduser(root)})"

    lines = [
        f"📄 {f['파일명']} ({f['크기(Bytes)']} Bytes) - {f['경로']} - 생성일 {f['생성일']}"
        for f in found
    ]
    return "\\n".join(lines)

@mcp.tool()
def reveal_in_finder(path: str) -> str:
    """
    지정한 파일/폴더를 Finder에서 표시합니다.
    - 파일이면 해당 파일을 선택 상태로 열고, 폴더면 폴더를 엽니다.
    """
    try:
        target = os.path.expanduser(path)
        if not os.path.exists(target):
            return f"경로가 존재하지 않습니다: {target}"

        # 파일이면 -R(=reveal) 옵션으로 표시, 폴더면 그냥 open
        if os.path.isfile(target):
            subprocess.run(["open", "-R", target], check=True)
        else:
            subprocess.run(["open", target], check=True)
        return f"Finder에서 표시했습니다: {target}"
    except subprocess.CalledProcessError as e:
        return f"Finder 열기 실패: {e}"
    except Exception as e:
        return f"오류 발생: {e}"

if __name__ == "__main__":
    # stdio 기반으로 MCP 서버 실행 (Cursor/Claude Desktop/Smithery 등과 연동)
    mcp.run(transport="stdio")
