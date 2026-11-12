"""담당자 화면 (내 PC). 접수 원문이 하자대장이 되기까지의 과정을 단계별로 보여준다. 실행: streamlit run app.py"""
import pandas as pd
import streamlit as st

import ai
import rules
import run

st.set_page_config(page_title="하자보수 도구", layout="wide")
st.title("하자보수 도구")
st.caption("접수 원문 → AI 정리 → 코드 판정 → 사람 확인 → 하자대장.  :blue[AI] 원문 해석 · :green[코드] 규칙 계산 · :orange[사람] 책임·현장 판단")

공사목록 = rules.공사목록읽기()
위치목록 = sorted({k["위치"] for k in 공사목록})

탭과정, 탭대장, 탭분담 = st.tabs(["처리 과정", "하자대장", "기능 분담"])

# ---------------------------------------------------------------- 처리 과정
with 탭과정:
    파일들 = sorted(run.접수함.glob("*.txt"))
    파일 = st.selectbox("접수 원문 선택", 파일들, format_func=lambda p: p.name)
    원문 = 파일.read_text(encoding="utf-8")
    st.session_state.setdefault("AI결과", {})

    왼, 오 = st.columns([2, 3], gap="large")

    with 왼:
        st.subheader("① 접수 원문  :green[코드]")
        st.caption("접수함 폴더의 파일을 그대로 읽습니다. 원본은 고치지 않습니다.")
        st.code(원문, language=None, wrap_lines=True)

    with 오:
        st.subheader("② AI 정리  :blue[AI]")
        st.caption("접수일·위치·하자내용·공종·긴급도 다섯 가지만 AI가 정합니다. (지침/접수정리.md)")
        if st.button("AI로 정리하기", type="primary"):
            with st.spinner("AI가 원문을 읽는 중..."):
                try:
                    st.session_state["AI결과"][파일.name] = ai.접수정리(원문, 파일.name, 위치목록)
                except Exception as e:
                    st.error(f"AI 호출 실패: {e}")
        결과 = st.session_state["AI결과"].get(파일.name)

        if not 결과:
            st.info("버튼을 누르면 이 원문을 AI가 정리합니다.")
        else:
            st.table(pd.DataFrame([{k: v for k, v in 결과.items() if k != "근거"}]).T.rename(columns={0: "AI가 정한 값"}))
            st.caption(f"근거: {결과.get('근거', '')}")

            st.subheader("③ 코드 판정  :green[코드]")
            st.caption("번호·조치기한·공사 찾기·보증 판정은 AI 없이 업무설명 규칙으로 계산합니다. (rules.py)")
            try:
                행 = run.행만들기(파일.name, 결과, 1, 공사목록)
                찾은 = rules.공사찾기(공사목록, 결과["위치"], 결과["공종"])
                st.write(
                    f"위치 `{결과['위치']}` · 공종 `{결과['공종']}`이 같은 공사: "
                    + (", ".join(f"{k['공사번호']}({k['공종']})" for k in 찾은) if 찾은 else "없음")
                )
                계산칸 = ["접수번호", "조치기한", "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]
                st.table(pd.DataFrame([{k: 행[k] for k in 계산칸}]).T.rename(columns={0: "코드가 계산한 값"}))
                st.caption("접수번호의 순번은 이 화면에서는 01로 둡니다. 실제 순번은 run.py가 접수일별로 다시 매깁니다.")
            except Exception as e:
                행 = None
                st.error(f"코드 판정 실패: {e}")

            st.subheader("④ 사람 확인  :orange[사람]")
            if 행 and 행["상태"] == "확인필요":
                st.warning(
                    "확인필요 건입니다. 담당자가 현장을 보고 공종을 정하면 보증 판정을 다시 돌립니다."
                    + (f"  비고: {행['비고']}" if 행["비고"] else "")
                )
            elif 행:
                st.success("판정완료. 담당자는 AI가 정한 공종·긴급도를 검토합니다.")
            if 행 and "40자 초과" in 행["비고"]:
                st.caption("하자내용이 40자를 넘었습니다. 담당자가 줄입니다.")

# ---------------------------------------------------------------- 하자대장
with 탭대장:
    try:
        대장 = pd.DataFrame(rules.대장읽기(), columns=run.항목).fillna("")
    except RuntimeError as e:
        대장 = None
        st.error(f"하자대장을 읽지 못했습니다: {e}")
    if 대장 is not None and 대장.empty:
        st.info("아직 하자대장이 없습니다. 터미널에서 `python run.py`를 실행하면 DB의 하자대장 테이블에 저장됩니다.")
    elif 대장 is not None:
        a, b, c, d = st.columns(4)
        a.metric("전체", f"{len(대장)}건")
        b.metric("긴급", f"{(대장['긴급도'] == '긴급').sum()}건")
        c.metric("시공업체 요청", f"{(대장['책임구분'] == '시공업체').sum()}건")
        d.metric("확인필요", f"{(대장['상태'] == '확인필요').sum()}건")

        def 강조(행):
            색 = "background-color: rgba(255, 165, 0, 0.25)" if 행["상태"] == "확인필요" else ""
            return [색] * len(행)

        st.dataframe(대장.style.apply(강조, axis=1), hide_index=True, width="stretch")
        st.caption("주황색 줄은 담당자 확인이 필요한 건입니다. 저장 위치: DB 하자대장 테이블")

# ---------------------------------------------------------------- 기능 분담
with 탭분담:
    분담 = pd.DataFrame(
        [
            ("접수함 파일 읽기", "원문파일", "코드"),
            ("접수일 찾기", "접수일", "AI + 코드"),
            ("위치를 `층 구역`으로 정리", "위치", "AI"),
            ("하자내용 40자 요약", "하자내용", "AI"),
            ("공종 판단", "공종", "AI"),
            ("긴급도 판단", "긴급도", "AI"),
            ("조치기한 계산", "조치기한", "코드"),
            ("접수번호 부여", "접수번호", "코드"),
            ("공사정보 찾기", "공사번호, 시공업체, 준공일", "코드"),
            ("보증만료일·판정", "보증만료일, 보증판정, 책임구분", "코드"),
            ("만료임박 표시", "비고", "코드"),
            ("확인필요 건 확정", "공종, 책임구분", "사람"),
            ("AI 결과 검토", "긴급도, 공종 등", "사람"),
            ("대장 저장, 상태 기록", "상태", "코드"),
            ("조치요청 확정", "상태", "사람"),
        ],
        columns=["기능", "대장 칸", "담당"],
    )
    st.dataframe(분담, hide_index=True, width="stretch")
