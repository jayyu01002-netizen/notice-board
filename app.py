import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="사내 공지사항", page_icon="📢", layout="centered")

# --- [함수] 구글 시트 연결 (비밀번호 등은 Streamlit Secrets에서 가져옴) ---
def get_google_sheet_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Streamlit Cloud의 Secrets 관리 기능을 사용
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # 구글 시트 이름 (정확해야 함)
    sheet = client.open("사내공지사항DB").sheet1
    return sheet

# --- [함수] 데이터 로드 및 저장 ---
def load_data():
    try:
        sheet = get_google_sheet_data()
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame() # 에러시 빈 데이터 반환

def save_data(date, title, content, is_important):
    sheet = get_google_sheet_data()
    # 새 행 추가
    sheet.append_row([date, title, content, "TRUE" if is_important else "FALSE"])

# --- [UI] 메인 화면 구성 ---
st.title("📢 우리회사 공지사항")

# 탭으로 UI 분리 (조회용 / 관리자용)
tab1, tab2 = st.tabs(["📋 공지 목록", "⚙️ 관리자 글쓰기"])

with tab1:
    st.info("새로고침 하려면 화면을 위에서 아래로 당기세요 (모바일)")
    df = load_data()
    
    if df.empty:
        st.write("등록된 공지가 없습니다.")
    else:
        # 최신글이 위로 오도록 정렬 (데이터가 있을 때만)
        if not df.empty:
            df = df.iloc[::-1]

        for index, row in df.iterrows():
            # 중요 공지 강조 UI
            is_imp = str(row.get("중요", "FALSE")).upper() == "TRUE"
            icon = "🔥" if is_imp else "📌"
            border_color = "red" if is_imp else "grey"
            
            with st.container(border=True):
                if is_imp:
                    st.markdown(":red[**[중요]**]")
                st.subheader(f"{icon} {row['제목']}")
                st.caption(f"작성일: {row['작성일']}")
                st.text(row['내용'])

with tab2:
    st.write("관리자만 작성 가능합니다.")
    password = st.text_input("비밀번호", type="password")
    
    # st.secrets에 설정된 비밀번호와 비교
    if password == st.secrets["admin_password"]:
        st.success("인증되었습니다.")
        with st.form("notice_form", clear_on_submit=True):
            title = st.text_input("제목")
            content = st.text_area("내용", height=150)
            is_important = st.checkbox("상단 강조 (중요)")
            submitted = st.form_submit_button("공지 등록")
            
            if submitted and title:
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                save_data(now, title, content, is_important)
                st.toast("✅ 등록 완료! '공지 목록' 탭에서 확인하세요.")
    elif password:
        st.error("비밀번호가 틀렸습니다.")