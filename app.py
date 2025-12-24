import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="사내 공지사항", page_icon="📢", layout="centered")

# --- [스타일] 모바일 줄바꿈 방지 및 글자 크기 조정 (추가된 부분) ---
st.markdown("""
<style>
    /* 스마트폰 화면(폭 768px 이하)일 때 적용되는 설정 */
    @media (max-width: 768px) {
        /* 제목(h1) 글자 크기를 줄임 */
        h1 {
            font-size: 1.8rem !important; 
            word-break: keep-all !important; /* 단어 중간에 줄바꿈 금지 */
        }
        /* 부제목(h3) 글자 크기도 조금 줄임 */
        h3 {
            font-size: 1.2rem !important;
            word-break: keep-all !important;
        }
        /* 본문 텍스트도 단어 단위로 줄바꿈 */
        p, div {
            word-break: keep-all !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- [함수] 구글 시트 연결 ---
def get_google_sheet_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Streamlit Cloud의 Secrets 관리 기능을 사용
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 구글 시트 이름 (이 이름과 정확히 일치하는 스프레드시트가 있어야 함)
    try:
        sheet = client.open("사내공지사항DB").sheet1
        return sheet
    except Exception as e:
        st.error(f"구글 시트를 찾을 수 없습니다: {e}")
        st.stop()

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

# 1. 공지 목록 탭
with tab1:
    st.caption("새로고침 하려면 화면을 위에서 아래로 당기세요 (모바일)")
    
    # 로딩 표시
    with st.spinner('데이터를 불러오는 중...'):
        df = load_data()
    
    if df.empty:
        st.info("등록된 공지가 없습니다.")
    else:
        # 최신글이 위로 오도록 정렬 (데이터가 있을 때만)
        df = df.iloc[::-1]

        for index, row in df.iterrows():
            # 중요 공지 강조 UI
            is_imp = str(row.get("중요", "FALSE")).upper() == "TRUE"
            
            # 디자인 설정
            if is_imp:
                icon = "🔥"
                border_style = "red" # 중요 공지는 빨간색 느낌
            else:
                icon = "📌"
                border_style = "grey" # 일반 공지는 회색

            # 공지사항 카드 출력
            with st.container(border=True):
                if is_imp:
                    st.markdown(":red[**[중요]**]")
                
                # 제목과 날짜
                st.subheader(f"{icon} {row['제목']}")
                st.caption(f"작성일: {row['작성일']}")
                
                # 내용
                st.text(row['내용'])

# 2. 관리자 글쓰기 탭
with tab2:
    st.write("관리자만 작성 가능합니다.")
    password = st.text_input("비밀번호", type="password")
    
    # Secrets에 설정된 비밀번호와 비교
    if password == st.secrets["admin_password"]:
        st.success("인증되었습니다.")
        st.divider()
        
        with st.form("notice_form", clear_on_submit=True):
            title = st.text_input("제목")
            content = st.text_area("내용", height=150)
            is_important = st.checkbox("상단 강조 (중요)")
            
            submitted = st.form_submit_button("공지 등록")
            
            if submitted:
                if not title or not content:
                    st.warning("제목과 내용을 모두 입력해주세요.")
                else:
                    with st.spinner('저장 중...'):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_data(now, title, content, is_important)
                    st.success("✅ 등록 완료! '공지 목록' 탭에서 확인하세요.")
                    
    elif password:
        st.error("비밀번호가 틀렸습니다.")