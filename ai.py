"""AI 호출은 이 파일에서만 한다. 키와 모델은 .env에서 읽는다."""
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")


def _client():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key or "여기에" in key:
        raise RuntimeError(".env의 ANTHROPIC_API_KEY가 비어 있습니다.")
    return anthropic.Anthropic(api_key=key)


def _model():
    model = os.getenv("MODEL", "").strip()
    if not model:
        raise RuntimeError(".env의 MODEL이 비어 있습니다.")
    return model


def 지침읽기(이름):
    """지침/ 폴더의 지침 파일을 읽어 시스템 프롬프트로 쓴다."""
    return (BASE / "지침" / f"{이름}.md").read_text(encoding="utf-8")


def _json로_읽기(글):
    """AI 답에서 JSON 객체 하나를 꺼낸다."""
    글 = 글.strip()
    try:
        return json.loads(글)
    except json.JSONDecodeError:
        시작, 끝 = 글.find("{"), 글.rfind("}")
        if 시작 == -1 or 끝 <= 시작:
            raise ValueError(f"JSON을 찾지 못했습니다: {글[:200]}")
        return json.loads(글[시작:끝 + 1])


def 접수정리(원문, 파일명, 위치목록=None):
    """접수 원문 1건을 정리해 dict로 돌려준다."""
    사용자글 = f"파일명: {파일명}\n\n[접수 원문]\n{원문}"
    if 위치목록:
        사용자글 += "\n\n[위치 목록]\n" + "\n".join(위치목록)

    응답 = _client().messages.create(
        model=_model(),
        max_tokens=2000,
        system=지침읽기("접수정리"),
        messages=[{"role": "user", "content": 사용자글}],
    )
    if 응답.stop_reason != "end_turn":
        raise RuntimeError(f"AI 응답이 정상 종료되지 않았습니다: {응답.stop_reason}")
    글 = "".join(b.text for b in 응답.content if b.type == "text")
    return _json로_읽기(글)
