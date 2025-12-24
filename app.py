import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="제이유 사내광장", page_icon="🏢", layout="centered")

# --- [스타일] CSS (모바일 최적화) ---
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
        
        /* 버튼 크기 넉넉하게 */
        div.stButton > button {
            width: 100%;
            height: 3.5rem;
            font-size: 18px;
        }
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

# --- [함수] 데이터 로드 ---
@st.cache_data(ttl=600)
def load_data(sheet_name):
    try:
        sheet = get_worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# --- [함수] 데이터 추가 (Create) ---
def save_notice(date, title, content, is_important):
    sheet = get_worksheet("공지사항")
    sheet.append_row([date, title, content, "TRUE" if is_important else "FALSE"])
    st.cache_data.clear()

def save_suggestion(date, title, content, author, is_private):
    sheet = get_worksheet("건의사항")
    sheet.append_row([date, title, content, author, "TRUE" if is_private else "FALSE"])
    st.cache_data.clear()

# --- [함수] 데이터 삭제 (Delete) ---
def delete_row(sheet_name, row_idx):
    # 구글 시트는 1부터 시작, 헤더가 1행이므로 데이터는 2행부터 시작
    # pandas index는 0부터 시작하므로, 실제 행 번호 = index + 2
    sheet = get_worksheet(sheet_name)
    sheet.delete_rows(row_idx + 2)
    st.cache_data.clear()

# --- [함수] 데이터 수정 (Update) ---
def update_notice(row_idx, date, title, content, is_important):
    sheet = get_worksheet("공지사항")
    # A열~D열 업데이트
    target_row = row_idx + 2
    sheet.update(range_name=f"A{target_row}:D{target_row}", 
                 values=[[date, title, content, "TRUE" if is_important else "FALSE"]])
    st.cache_data.clear()

def update_suggestion(row_idx, date, title, content, author, is_private):
    sheet = get_worksheet("건의사항")
    # A열~E열 업데이트
    target_row = row_idx + 2
    sheet.update(range_name=f"A{target_row}:E{target_row}", 
                 values=[[date, title, content, author, "TRUE" if is_private else "FALSE"]])
    st.cache_data.clear()


# --- [UI] 메인 화면 ---
st.title("🏢 제이유 사내광장")

# 상태 관리용
if 'show_write_form' not in st.session_state:
    st.session_state['show_write_form'] = False

def toggle_write_form():
    st.session_state['show_write_form'] = not st.session_state['show_write_form']

tab1, tab2, tab3 = st.tabs(["📋 공지사항", "🗣️ 제안 및 건의", "⚙️ 관리자"])

# ==========================================
# 1. 공지사항 탭
# ==========================================
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
        # 최신순 정렬
        df_rev = df.iloc[::-1]
        for index, row in df_rev.iterrows():
            is_imp = str(row.get("중요", "FALSE")).upper() == "TRUE"
            with st.container(border=True):
                if is_imp:
                    st.markdown(f":red[**[중요] 🔥 {row['제목']}**]")
                else:
                    st.subheader(f"📌 {row['제목']}")
                st.caption(f"📅 {row['작성일']}")
                st.markdown(f"{row['내용']}")

# ==========================================
# 2. 제안 및 건의 탭
# ==========================================
with tab2:
    st.write("### 🗣️ 자유 게시판 & 건의함")
    st.caption("자유롭게 의견을 남겨주세요.")
    
    # 글쓰기 버튼
    if st.button("✍️ 제안 및 건의사항 작성하기 (터치)", on_click=toggle_write_form, use_container_width=True):
        pass

    if st.session_state['show_write_form']:
        with st.container(border=True):
            st.info("작성 후 '등록'을 누르면 닫힙니다. (수정/삭제는 관리자에게 문의)")
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
                        st.session_state['show_write_form'] = False
                        st.rerun()

    st.divider()
    if st.button("🔄 게시판 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    df_s = load_data("건의사항")
    if df_s.empty:
        st.info("등록된 글이 없습니다.")
    else:
        df_s_rev = df_s.iloc[::-1]
        for index, row in df_s_rev.iterrows():
            if str(row.get("비공개", "FALSE")).upper() != "TRUE":
                with st.container(border=True):
                    st.markdown(f"**💬 {row['제목']}**")
                    col1, col2 = st.columns([1, 1])
                    with col_info1:
                        st.caption(f"👤 {row.get('작성자', '익명')}")
                    with col_info2:
                        st.caption(f"📅 {row['작성일']}")
                    st.markdown(f"{row['내용']}")

# ==========================================
# 3. 관리자 탭 (수정/삭제 기능 통합)
# ==========================================
with tab3:
    st.write("🔒 관리자 전용")
    password = st.text_input("비밀번호", type="password")
    
    if str(password).strip() == str(st.secrets["admin_password"]).strip():
        st.success("관리자 모드 접속")
        st.divider()
        
        # 관리 작업 선택
        mode = st.radio("작업 선택", ["📝 새 공지 작성", "🔧 공지사항 관리(수정/삭제)", "🔧 건의사항 관리(수정/삭제/보기)"])
        
        # 3-1. 새 공지 작성
        if mode == "📝 새 공지 작성":
            with st.form("notice_form", clear_on_submit=True):
                st.write("### 새 공지 쓰기")
                title = st.text_input("제목")
                content = st.text_area("내용")
                is_important = st.checkbox("상단 강조")
                if st.form_submit_button("등록", use_container_width=True):
                    save_notice(datetime.now().strftime("%Y-%m-%d %H:%M"), title, content, is_important)
                    st.toast("등록됨")

        # 3-2. 공지사항 관리
        elif mode == "🔧 공지사항 관리(수정/삭제)":
            st.write("### 공지사항 수정 및 삭제")
            df = load_data("공지사항")
            if df.empty:
                st.info("데이터가 없습니다.")
            else:
                # 선택 박스 (제목으로 선택)
                # 데이터프레임의 인덱스를 사용하여 고유 키 생성
                options = [f"[{i}] {row['제목']} ({row['작성일']})" for i, row in df.iterrows()]
                selected_option = st.selectbox("관리할 공지를 선택하세요", options)
                
                if selected_option:
                    # 선택된 인덱스 추출
                    selected_idx = int(selected_option.split(']')[0].replace('[', ''))
                    row = df.loc[selected_idx]
                    
                    with st.form("edit_notice_form"):
                        new_date = st.text_input("작성일", value=row['작성일'])
                        new_title = st.text_input("제목", value=row['제목'])
                        new_content = st.text_area("내용", value=row['내용'])
                        new_important = st.checkbox("상단 강조", value=(str(row['중요']).upper() == 'TRUE'))
                        
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            if st.form_submit_button("수정 저장", use_container_width=True):
                                update_notice(selected_idx, new_date, new_title, new_content, new_important)
                                st.success("수정되었습니다.")
                                st.rerun()
                        with col_del:
                            if st.form_submit_button("🗑️ 삭제하기", type="primary", use_container_width=True):
                                delete_row("공지사항", selected_idx)
                                st.success("삭제되었습니다.")
                                st.rerun()

        # 3-3. 건의사항 관리
        elif mode == "🔧 건의사항 관리(수정/삭제/보기)":
            st.write("### 건의사항 전체 보기 및 관리")
            df_s = load_data("건의사항")
            if df_s.empty:
                st.info("데이터가 없습니다.")
            else:
                options_s = [f"[{i}] {row['제목']} - {row.get('작성자','익명')}" for i, row in df_s.iterrows()]
                selected_option_s = st.selectbox("관리할 건의를 선택하세요", options_s)
                
                if selected_option_s:
                    selected_idx_s = int(selected_option_s.split(']')[0].replace('[', ''))
                    row_s = df_s.loc[selected_idx_s]
                    
                    st.info(f"작성자: {row_s.get('작성자', '익명')} | 비공개여부: {row_s.get('비공개')}")
                    
                    with st.form("edit_suggestion_form"):
                        new_date_s = st.text_input("작성일", value=row_s['작성일'])
                        new_title_s = st.text_input("제목", value=row_s['제목'])
                        new_content_s = st.text_area("내용", value=row_s['내용'])
                        new_author_s = st.text_input("작성자", value=row_s.get('작성자', '익명'))
                        new_private_s = st.checkbox("비공개 설정", value=(str(row_s.get('비공개')).upper() == 'TRUE'))
                        
                        col_edit_s, col_del_s = st.columns(2)
                        with col_edit_s:
                            if st.form_submit_button("수정 저장", use_container_width=True):
                                update_suggestion(selected_idx_s, new_date_s, new_title_s, new_content_s, new_author_s, new_private_s)
                                st.success("수정되었습니다.")
                                st.rerun()
                        with col_del_s:
                            if st.form_submit_button("🗑️ 삭제하기", type="primary", use_container_width=True):
                                delete_row("건의사항", selected_idx_s)
                                st.success("삭제되었습니다.")
                                st.rerun()

    elif password: # 비밀번호 틀렸을 때
        st.error("비밀번호가 일치하지 않습니다.")