import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="제이유 사내광장", page_icon="🏢", layout="centered")

# --- [스타일] CSS 수정 (화살표 삭제 & 폰트 겹침 해결) ---
st.markdown("""
<style>
    /* 1. 본문 텍스트 설정 */
    div[data-testid="stMarkdownContainer"] p {
        font-size: 18px !important;
        line-height: 1.6 !important;
        word-break: keep-all !important;
    }
    
    /* 2. 모바일 제목 크기 조정 */
    @media (max-width: 768px) {
        h1 { font-size: 2.0rem !important; word-break: keep-all !important; }
        h3 { font-size: 1.3rem !important; word-break: keep-all !important; }
    }
    
    /* [핵심] 화살표 아이콘(toggle icon)을 아예 삭제해서 안 보이게 함 */
    div[data-testid="stExpanderToggleIcon"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
    }
    
    /* 혹시 모를 잔여 아이콘 숨김 */
    .streamlit-expanderHeader svg { display: none !important; }
    .streamlit-expanderHeader .material-icons { display: none !important; }
    
    /* 아이콘이 사라진 만큼 왼쪽 여백을 없애서 글자를 당김 */
    .streamlit-expanderHeader {
        padding-left: 0 !important;
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

# --- [함수] 저장 로직 ---
def save_notice(date, title, content, is_important):
    sheet = get_worksheet("공지사항")
    sheet.append_row([date, title, content, "TRUE" if is_important else "FALSE"])
    st.cache_data.clear()

def save_suggestion(date, title, content, author, is_private):
    sheet = get_worksheet("건의사항")
    sheet.append_row([date, title, content, author, "TRUE" if is_private else "FALSE"])
    st.cache_data.clear()

# --- [UI] 메인 화면 ---
# [확인용] 제목이 바뀌어야 코드가 적용된 것입니다!
st.title("🏢 제이유 사내광장 (업데이트됨)")

tab1, tab2, tab3 = st.tabs(["📋 공지사항", "🗣️ 제안 및 건의", "⚙️ 관리자 작성"])

# 1. 공지사항 탭
with tab1:
    if st.button("🔄 공지 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    with st.spinner('로딩 중...'):
        df = load_data("공지사항")
    st.markdown("---")
    if df.empty:
        st.info("공지사항이 없습니다.")
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
                st.markdown(f"{row['내용']}")

# 2. 제안 및 건의 탭
with tab2:
    st.write("### 🗣️ 자유 게시판 & 건의함")
    st.caption("자유롭게 의견을 남겨주세요.")
    
    # [수정] 화살표 없이 글자만 클릭하면 열림
    with st.expander("✍️ 제안 및 건의사항 작성하기 (터치)", expanded=False):
        with st.form("suggestion_form", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                author_input = st.text_input("작성자", placeholder="이름 (생략가능)")
            with col2:
                is_private = st.checkbox("🔒 관리자에게만", help="비공개 건의")
            s_title = st.text_input("제목", placeholder="제목 입력")
            s_content = st.text_area("내용", height=100, placeholder="내용 입력")
            if st.form_submit_button("등록", use_container_width=True):
                if not s_content:
                    st.warning("내용을 입력하세요.")
                else:
                    final_author = author_input if author_input.strip() else "익명"
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_suggestion(now, s_title, s_content, final_author, is_private)
                    st.success("등록되었습니다.")
                    st.rerun()

    st.divider()
    if st.button("🔄 게시판 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    df_s = load_data("건의사항")
    if df_s.empty:
        st.info("등록된 글이 없습니다.")
    else:
        df_s = df_s.iloc[::-1]
        for index, row in df_s.iterrows():
            if str(row.get("비공개", "FALSE")).upper() != "TRUE":
                with st.container(border=True):
                    st.markdown(f"**💬 {row['제목']}**")
                    col_info1, col_info2 = st.columns([1, 1])
                    with col_info1:
                        st.caption(f"👤 {row.get('작성자', '익명')}")
                    with col_info2:
                        st.caption(f"📅 {row['작성일']}")
                    st.markdown(f"{row['내용']}")

# 3. 관리자 탭
with tab3:
    st.write("🔒 관리자 전용")
    password = st.text_input("비밀번호", type="password")
    if str(password).strip() == str(st.secrets["admin_password"]).strip():
        st.success("접속 성공")
        st.divider()
        with st.form("notice_form", clear_on_submit=True):
            st.write("📝 공지 작성")
            title = st.text_input("제목")
            content = st.text_area("내용")
            is_important = st.checkbox("상단 강조")
            if st.form_submit_button("등록"):
                save_notice(datetime.now().strftime("%Y-%m-%d %H:%M"), title, content, is_important)
                st.toast("등록됨")
        st.divider()
        if st.button("비공개 건의사항 보기"):
             df_secret = load_data("건의사항")
             if not df_secret.empty:
                 st.dataframe(df_secret[df_secret['비공개'].astype(str).str.upper() == 'TRUE'])
             else:
                 st.info("데이터 없음")