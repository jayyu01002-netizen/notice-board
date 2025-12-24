import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="제이유 공지사항", page_icon="📢", layout="centered")

# --- [스타일] 글자 크기 확대 및 모바일 줄바꿈 방지 ---
st.markdown("""
<style>
    /* 1. 전체 기본 글자 크기 키우기 */
    html, body, [class*="css"] {
        font-size: 18px; /* 기본 폰트 사이즈 업 */
    }

    /* 2. 스마트폰 화면(폭 768px 이하)일 때 설정 */
    @media (max-width: 768px) {
        /* 메인 제목 크기 */
        h1 {
            font-size: 2.2rem !important; 
            word-break: keep-all !important; /* 단어 끊김 방지 */
        }
        /* 소제목(공지 제목) 크기 */
        h3 {
            font-size: 1.4rem !important;
            word-break: keep-all !important;
            line-height: 1.4 !important;
        }
        /* 본문 내용 크기 */
        p, div, span {
            font-size: 16px !important;
            word-break: keep-all !important;
        }
        /* 버튼 크기 키우기 */
        button {
            height: 3rem !important;
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
        st.error(f"구글 시트를 찾을 수 없습니다. 이름이 '사내공지사항DB'가 맞는지 확인해주세요.\n에러: {e}")
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
    # 새 행 추가 (작성일, 제목, 내용, 중요여부)
    sheet.append_row([date, title, content, "TRUE" if is_important else "FALSE"])

# --- [UI] 메인 화면 구성 ---
st.title("📢 제이유 공지사항")

# 탭으로 UI 분리 (조회용 / 관리자용)
tab1, tab2 = st.tabs(["📋 공지 목록", "⚙️ 관리자 글쓰기"])

# ==========================================
# 1. 공지 목록 탭 (직원용)
# ==========================================
with tab1:
    # [수정] 모바일에서도 확실하게 작동하는 새로고침 버튼
    if st.button("🔄 최신 목록 불러오기", use_container_width=True):
        st.rerun()
    
    # 로딩 표시
    with st.spinner('제이유 서버와 통신 중...'):
        df = load_data()
    
    st.markdown("---") # 구분선

    if df.empty:
        st.info("현재 등록된 공지가 없습니다.")
    else:
        # 최신글이 위로 오도록 순서 뒤집기
        df = df.iloc[::-1]

        for index, row in df.iterrows():
            # 중요 공지인지 확인
            is_imp = str(row.get("중요", "FALSE")).upper() == "TRUE"
            
            # 카드 디자인 시작
            with st.container(border=True):
                # 1) 제목 영역
                if is_imp:
                    # 중요 공지는 빨간색 강조 + 아이콘
                    st.markdown(f":red[**[중요] 🔥 {row['제목']}**]")
                else:
                    # 일반 공지는 조금 더 크게 표시
                    st.subheader(f"📌 {row['제목']}")

                # 2) 날짜 영역 (회색 작은 글씨)
                st.caption(f"📅 작성일: {row['작성일']}")
                
                # 3) 본문 영역 (글씨 크기 확보)
                st.markdown(f"**{row['내용']}**") 

# ==========================================
# 2. 관리자 글쓰기 탭 (관리자용)
# ==========================================
with tab2:
    st.write("🔒 관리자만 작성할 수 있습니다.")
    password = st.text_input("관리자 비밀번호", type="password")
    
    # Secrets에 설정된 비밀번호와 비교
    if password == st.secrets["admin_password"]:
        st.success("로그인 되었습니다.")
        st.divider()
        
        with st.form("notice_form", clear_on_submit=True):
            st.write("### 📝 새 공지 작성")
            title = st.text_input("제목을 입력하세요")
            content = st.text_area("내용을 입력하세요", height=200) # 입력창 높이 키움
            is_important = st.checkbox("📢 상단 강조 (중요 공지)")
            
            submitted = st.form_submit_button("등록하기", use_container_width=True)
            
            if submitted:
                if not title or not content:
                    st.warning("제목과 내용을 모두 입력해주세요.")
                else:
                    with st.spinner('저장 중...'):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_data(now, title, content, is_important)
                    st.toast("✅ 공지사항이 등록되었습니다!")
                    
    elif password: # 비밀번호가 틀렸을 때
        st.error("비밀번호가 일치하지 않습니다.")