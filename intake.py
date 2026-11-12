"""접수 화면 (웹 배포용). 매장·현장에서 하자를 접수하면 DB의 접수 테이블에 저장한다. 실행: streamlit run intake.py"""
import datetime as dt

import streamlit as st

import db

st.set_page_config(page_title="하자 접수", layout="centered")

한국시간 = dt.timezone(dt.timedelta(hours=9))
오늘 = dt.datetime.now(한국시간).date()

st.title("하자 접수")
st.caption("시설에서 발견한 하자를 적어 주세요. 시설관리팀이 확인 후 처리합니다.")

st.session_state.setdefault("번호", 0)  # 접수 후 입력칸을 비우려고 칸 이름을 바꾼다
n = st.session_state["번호"]

if st.session_state.get("완료"):
    st.success(f"접수되었습니다. (접수 {st.session_state.pop('완료')}번)")

with st.form(f"접수양식_{n}"):
    발견일 = st.date_input("발견일", value=오늘, max_value=오늘, key=f"발견일_{n}")
    접수자 = st.text_input("접수자", max_chars=50, key=f"접수자_{n}")
    부서 = st.text_input("부서 · 매장", max_chars=50, key=f"부서_{n}")
    위치 = st.text_input("위치", placeholder="예: B1 푸드코트, 2F 화장실", max_chars=100, key=f"위치_{n}")
    내용 = st.text_area("하자 내용", placeholder="어디에서 무엇이 어떻게 되었는지 적어 주세요.",
                        height=150, max_chars=1000, key=f"내용_{n}")
    보냄 = st.form_submit_button("접수하기", type="primary")

if 보냄:
    빈칸 = [이름 for 이름, 값 in [("접수자", 접수자), ("부서 · 매장", 부서), ("위치", 위치), ("하자 내용", 내용)] if not 값.strip()]
    if 빈칸:
        st.error("빈칸을 채워 주세요: " + ", ".join(빈칸))
    else:
        try:
            st.session_state["완료"] = db.접수저장(발견일, 접수자, 부서, 위치, 내용)
            st.session_state["번호"] += 1
            st.rerun()
        except RuntimeError as e:
            print(f"[접수 저장 실패] {e}")  # 오류 내용은 화면에 내보내지 않고 서버 로그에만 남긴다.
            st.error("접수를 저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요.")
