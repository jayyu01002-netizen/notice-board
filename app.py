import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="제이유 사내광장", page_icon="🏢", layout="centered")

# --- [스타일] CSS (모바일 최적화 & 글자 크기) ---
st.markdown("""
<style>
    /* 전체 폰트 크기 증대 */
    html, body, [class*="css"] { font-size: 18px; }
    
    /* 모바일(폭 768px 이하) 전용 설정 */
    @media (max-width: 768px) {
        h1 { font-size: 2.2rem !important; word-break: keep-all !important; }
        h3 { font-size: 1.4rem !important; word-break: keep-all !important; }
        p, div, span, textarea, input { font-size: 16px !important; word-break: keep-all !important; }
        button { height: 3rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- [함수] 구글 시트 연결 (캐시 적용 안 함 - 연결은 항상 생생하게) ---
def get_worksheet(sheet_name):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # 스프레드시트 이름은 '사내공지사항DB'로 고정, 시트(탭) 이름은 변수로 받음
    return client.open("사내공지사항DB").worksheet(sheet_name)

# --- [함수] 데이터 로드 (캐시 적용! - 10분간 메모리에 저장) ---
# ttl=600 : 600초(10분) 동안은 구글 시트를 안 읽고 기억된 데이터를 보여줌 (트래픽 절약)
@st.cache_data(ttl=600)
def load_data():
    try:
        sheet = get_worksheet("공지사항") # '공지사항' 탭에서 읽기
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# --- [함수] 데이터 저장 (공지사항) ---
def save_notice(date, title, content, is_important):
    sheet = get_worksheet("공지사항")
    sheet.append_row([date, title, content, "TRUE" if is_important else "FALSE"])
    st.cache_data.clear() # 새 글을 썼으니 캐시를 삭제해야 바로 보임!

# --- [함수] 데이터 저장 (익명 건의사항) ---
def save_suggestion(date, title, content):
    sheet = get_worksheet("건의사항") # '건의사항' 탭에 저장
    sheet.append_row([date, title, content])
    # 건의사항은 관리자만 엑셀로 볼 것이므로 캐시 삭제 불필요

# --- [UI] 메인 화면 ---
st.title("🏢 제이유 사내광장")

# 탭 3개로 확장
tab1, tab2, tab3 = st.tabs(["📋 공지사항", "🗣️ 익명 건의함", "⚙️ 관리자 작성"])

# ==========================================
# 1. 공지 목록 탭 (직원용 - 캐시 적용)
# ==========================================
with tab1:
    # 이 버튼을 누르면 캐시를 강제로 지우고 새로고침함
    if st.button("🔄 최신 목록 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    with st.spinner('데이터 불러오는 중...'):
        df = load_data() # 캐시된 데이터 혹은 새 데이터 가져오기
    
    st.markdown("---")

    if df.empty:
        st.info("등록된 공지가 없습니다.")
    else:
        df = df.iloc[::-1] # 최신순 정렬
        for index, row in df.iterrows():
            is_imp = str(row.get("중요", "FALSE")).upper() == "TRUE"
            
            with st.container(border=True):
                if is_imp:
                    st.markdown(f":red[**[중요] 🔥 {row['제목']}**]")
                else:
                    st.subheader(f"📌 {row['제목']}")

                st.caption(f"📅 {row['작성일']}")
                st.markdown(f"**{row['내용']}**")

# ==========================================
# 2. 익명 건의함 탭 (직원용 - 쓰기 전용)
# ==========================================
with tab2:
    st.write("### 🗣️ 소중한 의견을 듣습니다")
    st.info("이곳에 작성된 내용은 **익명**으로 저장되며 관리자만 확인할 수 있습니다. \n 자유롭게 건의 및 제안해 주세요.")
    
    with st.form("suggestion_form", clear_on_submit=True):
        s_title = st.text_input("제안 제목 (선택)", placeholder="예: 휴게실 비품 관련 건의")
        s_content = st.text_area("건의 내용 (필수)", height=150, placeholder="내용을 입력해 주세요.")
        
        s_submitted = st.form_submit_button("📩 익명으로 보내기", use_container_width=True)
        
        if s_submitted:
            if not s_content:
                st.warning("내용을 입력해주세요.")
            else:
                with st.spinner('전송 중...'):
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_suggestion(now, s_title, s_content)
                st.success("✅ 소중한 의견이 안전하게 전달되었습니다!")

# ==========================================
# 3. 관리자 글쓰기 탭 (관리자용)
# ==========================================
with tab3:
    st.write("🔒 관리자 전용")
    password = st.text_input("관리자 비밀번호", type="password")
    
    if password == st.secrets["admin_password"]:
        st.success("인증됨")
        st.divider()
        
        with st.form("notice_form", clear_on_submit=True):
            st.write("### 📝 공지 작성")
            title = st.text_input("제목")
            content = st.text_area("내용", height=200)
            is_important = st.checkbox("📢 상단 강조")
            
            submitted = st.form_submit_button("공지 등록", use_container_width=True)
            
            if submitted:
                if not title or not content:
                    st.warning("제목과 내용을 입력하세요.")
                else:
                    with st.spinner('저장 및 알림 전송 중...'):
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_notice(now, title, content, is_important)
                    st.toast("✅ 등록 완료! 목록이 갱신되었습니다.")
                    
    elif password:
        st.error("비밀번호 불일치")