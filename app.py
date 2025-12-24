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

# --- [함수] 구글 시트 연결 ---
def get_worksheet(sheet_name):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("사내공지사항DB").worksheet(sheet_name)

# --- [함수] 데이터 로드 (캐시 적용) ---
@st.cache_data(ttl=600)
def load_data(sheet_name):
    try:
        sheet = get_worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# --- [함수] 공지사항 저장 ---
def save_notice(date, title, content, is_important):
    sheet = get_worksheet("공지사항")
    sheet.append_row([date, title, content, "TRUE" if is_important else "FALSE"])
    st.cache_data.clear()

# --- [함수] 제안 및 건의 저장 (수정됨) ---
def save_suggestion(date, title, content, author, is_private):
    sheet = get_worksheet("건의사항")
    # 작성자, 비공개 여부 컬럼 추가
    sheet.append_row([date, title, content, author, "TRUE" if is_private else "FALSE"])
    st.cache_data.clear()

# --- [UI] 메인 화면 ---
st.title("🏢 제이유 사내광장")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📋 공지사항", "🗣️ 제안 및 건의", "⚙️ 관리자 작성"])

# ==========================================
# 1. 공지 목록 탭
# ==========================================
with tab1:
    if st.button("🔄 공지 새로고침", key="refresh_notice", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    with st.spinner('불러오는 중...'):
        df = load_data("공지사항")
    
    st.markdown("---")

    if df.empty:
        st.info("등록된 공지가 없습니다.")
    else:
        df = df.iloc[::-1]
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
# 2. 제안 및 건의 탭 (공개 게시판 형태)
# ==========================================
with tab2:
    st.write("### 🗣️ 자유 게시판 & 건의함")
    st.caption("회사를 위한 좋은 아이디어 혹은 건의사항을 자유롭게 남겨주세요.")
    
    # 2-1. 글쓰기 접이식 메뉴 (Expander)
    with st.expander("✍️ 새 글 작성하기 (터치)", expanded=False):
        with st.form("suggestion_form", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                author_input = st.text_input("작성자 (비워두면 익명)", placeholder="이름")
            with col2:
                is_private = st.checkbox("🔒 관리자에게만 전송", help="체크하면 게시판에 공개되지 않고 관리자만 볼 수 있습니다.")
            
            s_title = st.text_input("제목", placeholder="제안 내용을 한 줄로 요약해 주세요")
            s_content = st.text_area("내용", height=100, placeholder="상세 내용을 적어주세요")
            
            s_submitted = st.form_submit_button("등록하기", use_container_width=True)
            
            if s_submitted:
                if not s_content:
                    st.warning("내용을 입력해주세요.")
                else:
                    final_author = author_input if author_input.strip() else "익명"
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_suggestion(now, s_title, s_content, final_author, is_private)
                    
                    if is_private:
                        st.success("🔒 관리자에게만 비밀리에 전달되었습니다.")
                    else:
                        st.success("✅ 게시판에 등록되었습니다.")
                    st.rerun()

    # 2-2. 제안 목록 표시
    st.divider()
    if st.button("🔄 게시판 새로고침", key="refresh_suggestion", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.spinner('의견을 불러오는 중...'):
        df_s = load_data("건의사항")

    if df_s.empty:
        st.info("아직 등록된 제안이 없습니다. 첫 번째 의견을 남겨보세요!")
    else:
        # 최신순 정렬
        df_s = df_s.iloc[::-1]
        
        for index, row in df_s.iterrows():
            # 비공개 글 필터링 (TRUE면 건너뜀)
            is_secret = str(row.get("비공개", "FALSE")).upper() == "TRUE"
            
            if not is_secret:
                with st.container(border=True):
                    # 제목 + 작성자(오른쪽 정렬 느낌)
                    st.markdown(f"**💬 {row['제목']}**")
                    
                    col_info1, col_info2 = st.columns([1, 1])
                    with col_info1:
                        st.caption(f"👤 {row.get('작성자', '익명')}")
                    with col_info2:
                        st.caption(f"📅 {row['작성일']}")
                    
                    st.text(row['내용'])

# ==========================================
# 3. 관리자 탭
# ==========================================
with tab3:
    st.write("🔒 관리자 전용")
    password = st.text_input("관리자 비밀번호", type="password")
    
    if password == st.secrets["admin_password"]:
        st.success("관리자 모드 접속")
        st.divider()
        
        # 관리자용 - 공지 작성
        st.write("#### 📝 공지사항 작성")
        with st.form("notice_form", clear_on_submit=True):
            title = st.text_input("제목")
            content = st.text_area("내용", height=150)
            is_important = st.checkbox("📢 상단 강조")
            
            if st.form_submit_button("공지 등록", use_container_width=True):
                if title and content:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_notice(now, title, content, is_important)
                    st.toast("등록 완료")
        
        st.divider()
        
        # 관리자용 - 비공개 건의사항 확인하기 기능 추가
        st.write("#### 🔒 비공개 건의함 (관리자만 보임)")
        if st.button("비공개 건의사항 열기"):
             df_secret = load_data("건의사항")
             if not df_secret.empty:
                 # 비공개인 것만 필터링
                 secret_msgs = df_secret[df_secret['비공개'].astype(str).str.upper() == 'TRUE']
                 if secret_msgs.empty:
                     st.info("비공개 건의사항이 없습니다.")
                 else:
                     st.dataframe(secret_msgs)
             else:
                 st.info("데이터가 없습니다.")

    elif password:
        st.error("비밀번호 불일치")