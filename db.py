"""저장은 이 파일에서만 한다. 연결 정보는 .env의 DATABASE_URL에서 읽고, 화면·오류에는 내보내지 않는다."""
import functools
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (CheckConstraint, Column, Date, DateTime, Integer, MetaData, Table, Text,
                        create_engine, func, select, text)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

load_dotenv(Path(__file__).parent / ".env")

# data/하자대장.csv와 같은 열(같은 순서)
대장열 = ["접수번호", "접수일", "원문파일", "위치", "공종", "하자내용", "긴급도", "조치기한",
        "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]

meta = MetaData()

접수 = Table(
    "접수", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("접수일시", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("발견일", Date),
    Column("접수자", Text),
    Column("부서", Text),
    Column("위치", Text),
    Column("내용", Text),
    Column("처리상태", Text, nullable=False, server_default="미처리"),
    Column("접수번호", Text),
    CheckConstraint("\"처리상태\" IN ('미처리', '처리완료')", name="접수_처리상태_check"),
)

하자대장 = Table(
    "하자대장", meta,
    *[Column(c, Text, primary_key=(c == "접수번호"), nullable=(c != "접수번호")) for c in 대장열],
)


def _url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(".env의 DATABASE_URL이 비어 있습니다.")
    # SQLAlchemy가 psycopg(3)를 쓰도록 접속 방식을 맞춘다.
    for 앞 in ("postgresql://", "postgres://"):
        if url.startswith(앞):
            return "postgresql+psycopg://" + url[len(앞):]
    return url


def _가리기(글):
    """오류 글에서 접속 주소와 비밀번호를 지운다."""
    for 비밀 in (os.getenv("DATABASE_URL", "").strip(), make_url(_url()).password):
        if 비밀:
            글 = 글.replace(비밀, "***")
    return 글


def _오류가림(함수):
    @functools.wraps(함수)
    def 감싼(*a, **k):
        try:
            return 함수(*a, **k)
        except SQLAlchemyError as e:
            raise RuntimeError(f"DB 오류({type(e).__name__}): {_가리기(str(e).splitlines()[0])}") from None
    return 감싼


@lru_cache
def _엔진():
    return create_engine(_url(), pool_pre_ping=True)


@lru_cache
@_오류가림
def 초기화():
    """테이블 2개가 없으면 만들고, 두 테이블 모두 RLS(행 수준 보안)를 켠다. 여러 번 불러도 안전하다."""
    with _엔진().begin() as c:
        meta.create_all(c)
        for 표 in (접수, 하자대장):
            c.execute(text(f'ALTER TABLE "{표.name}" ENABLE ROW LEVEL SECURITY'))


@_오류가림
def 대장읽기():
    """하자대장 전체를 접수번호 순으로 dict 목록으로 돌려준다."""
    초기화()
    with _엔진().connect() as c:
        return [dict(r) for r in c.execute(select(하자대장).order_by(하자대장.c.접수번호)).mappings()]


@_오류가림
def 대장저장(행들):
    """접수번호를 기준으로 넣고, 이미 있으면 덮어쓴다. (저장한 건수, 접수번호가 없어 건너뛴 건수)를 돌려준다."""
    초기화()
    저장 = [{k: (r.get(k) or "") for k in 대장열} for r in 행들 if (r.get("접수번호") or "").strip()]
    if 저장:
        문 = pg_insert(하자대장).values(저장)
        문 = 문.on_conflict_do_update(
            index_elements=["접수번호"],
            set_={k: 문.excluded[k] for k in 대장열 if k != "접수번호"},
        )
        with _엔진().begin() as c:
            c.execute(문)
    return len(저장), len(행들) - len(저장)


@_오류가림
def 접수저장(발견일, 접수자, 부서, 위치, 내용):
    """접수 화면에서 받은 한 건을 접수 테이블에 넣고 id를 돌려준다. 처리상태는 미처리로 시작한다."""
    초기화()
    값 = {"발견일": 발견일, "접수자": 접수자.strip(), "부서": 부서.strip(), "위치": 위치.strip(), "내용": 내용.strip()}
    with _엔진().begin() as c:
        return c.execute(접수.insert().values(**값).returning(접수.c.id)).scalar_one()


@_오류가림
def 미처리접수():
    """처리상태가 미처리인 접수를 id 순으로 돌려준다."""
    초기화()
    with _엔진().connect() as c:
        문 = select(접수).where(접수.c.처리상태 == "미처리").order_by(접수.c.id)
        return [dict(r) for r in c.execute(문).mappings()]


@_오류가림
def 접수처리완료(쌍들):
    """(id, 접수번호) 목록의 접수를 처리완료로 바꾸고 접수번호를 적는다."""
    초기화()
    with _엔진().begin() as c:
        for id_, 번호 in 쌍들:
            c.execute(접수.update().where(접수.c.id == id_).values(처리상태="처리완료", 접수번호=번호))


@_오류가림
def 건수():
    """테이블별 건수."""
    초기화()
    with _엔진().connect() as c:
        return {표.name: c.execute(select(func.count()).select_from(표)).scalar_one() for 표 in (접수, 하자대장)}
