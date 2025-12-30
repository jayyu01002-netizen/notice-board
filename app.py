import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time, timedelta
import uuid
import pytz
import holidays
from streamlit_calendar import calendar
import time as tm

# =========================================================
# [설정] 페이지 기본 설정
# =========================================================
st.set_page_config(
    page_title="제이유 사내광장",
    page_icon="🏢",
    layout="centered",
    initial_sidebar_state="collapsed"
)

main_container = st.empty()
KST = pytz.timezone('Asia/Seoul')

# =========================================================
# [스타일] CSS: 디자인 유지 + 모바일/달력 최적화
# =========================================================
st.markdown("""
<style>
    /* [1] 제목(h1) 및 상단 여백 설정 (모바일 최적화) */
    h1 { padding-top: 1rem !important; font-size: 2rem !important; }
    
    @media (max-width: 640px) {
        h1 { font-size: 1.5rem !important; margin-top: 0.5rem !important; }
        .block-container { padding-top: 7rem !important; } 
    }

    /* [2] 상단 불필요 요소 숨김 */
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }
    
    /* [3] 커스텀 네비게이션 (라디오 버튼) */
    div.row-widget.stRadio > div {
        flex-direction: row;
        justify-content: center;
        gap: 5px;
        background: #f0f2f6;
        padding: 5px;
        border-radius: 10px;
        overflow-x: auto;
        flex-wrap: nowrap;
    }
    div.row-widget.stRadio > div > label {
        background: transparent;
        border-radius: 8px;
        padding: 8px 12px;
        margin: 0 !important;
        width: auto !important;
        border: none;
        cursor: pointer;
        font-weight: bold;
        transition: all 0.2s;
        text-align: center;
        white-space: nowrap;
    }
    div.row-widget.stRadio > div > label[data-checked="true"] {
        background: white !important;
        color: #4b6cb7 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div.row-widget.stRadio div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    /* [4] 일반 버튼 */
    div.stButton > button {
        width: 100% !important;        
        padding: 0.3rem 0.5rem !important;
        font-size: 13px !important;
        border-radius: 6px !important;
        background: #2b2b2b !important;
        color: #eeeeee !important;
        border: 1px solid #444444 !important;
        box-shadow: none !important;
        margin-top: 5px !important;
        white-space: nowrap !important;
    }
    div.stButton > button:hover {
        background: #000000 !important;
        color: #ffffff !important;
    }

    /* [5] 폼 내부 버튼 */
    div[data-testid="stForm"] div.stButton > button {
        width: 100% !important;
        padding: 0.5rem 1rem !important;
        font-size: 16px !important;
        background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%) !important;
        color: white !important;
        border: none !important;
    }

    /* [6] 로그아웃/삭제 버튼 (빨간색) */
    div[data-testid="column"] button[kind="secondary"] {
        background: #FF4B4B !important;
        color: white !important;
        border: none !important;
        white-space: nowrap !important;
    }

    /* [7] 입력창 디자인 */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px;
    }
    iframe[title="streamlit_calendar.calendar"] { height: 750px !important; }
    p { font-size: 16px; word-break: keep-all; }

    /* [8] 달력 헤더(월/년) 글씨색 검정색으로 강제 지정 */
    .fc-toolbar-title { 
        color: #333333 !important; 
        font-weight: 800 !important;
    }
    .fc-button { color: #333333 !important; border: 1px solid #ddd !important; }
    .fc-daygrid-day-number { color: #333333 !important; text-decoration: none !important; }
    .fc-col-header-cell-cushion { color: #333333 !important; text-decoration: none !important; font-weight: bold !important; }
    .fc-day-sun .fc-daygrid-day-number { color: #FF4B4B !important; }
    .fc-day-sun .fc-col-header-cell-cushion { color: #FF4B4B !important; }
    .fc-day-sat .fc-daygrid-day-number { color: #1E90FF !important; }
    .fc-day-sat .fc-col-header-cell-cushion { color: #1E90FF !important; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# [설정] 관리자 및 회사 정보
# =========================================================
JANGAN_FOREMEN = ["JK 조장", "JX 메인 조장", "JX 어퍼 조장", "MX5 조장", "피더 조장"]
JANGAN_MID = ["반장"]
ULSAN_APPROVERS = ["김대환", "김범진", "홍성곤"]
ALL_MANAGERS = JANGAN_FOREMEN + JANGAN_MID + ULSAN_APPROVERS + ["MASTER"]

COMPANIES = {
    "9424": "장안 제이유",
    "0645": "울산 제이유"
}

# =========================================================
# [함수] 데이터 처리
# =========================================================
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def get_worksheet(sheet_name):
    client = get_client()
    return client.open("사내공지사항DB").worksheet(sheet_name)

def get_today():
    return datetime.now(KST).strftime("%Y-%m-%d")

def load_user_db():
    try:
        sheet = get_worksheet("관리자DB")
        data = sheet.get_all_records()
        return {str(row['이름']).strip(): str(row['비밀번호']).strip() for row in data}
    except: return {}

def save_user_db(db):
    try:
        sheet = get_worksheet("관리자DB")
        sheet.clear()
        sheet.append_row(["이름", "비밀번호"])
        for name, pw in db.items():
            sheet.append_row([name, str(pw)])
    except Exception as e: st.error(f"저장 오류: {e}")

@st.cache_data(ttl=300)
def load_data(sheet_name, company_name):
    try:
        sheet = get_worksheet(sheet_name)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        required_cols = {
            "근태신청": ['소속', '신청일', '이름', '구분', '날짜및시간', '사유', '상태', '비밀번호', '승인담당자'],
            "공지사항": ['소속', '작성일', '제목', '내용', '중요'],
            "건의사항": ['소속', '작성일', '제목', '내용', '작성자', '비공개', '비밀번호'],
            "일정관리": ['소속', '날짜', '제목', '내용', '작성자']
        }
        if df.empty and sheet_name in required_cols: 
            df = pd.DataFrame(columns=required_cols[sheet_name])
            
        if sheet_name in required_cols:
            for col in required_cols[sheet_name]:
                if col not in df.columns: df[col] = ""
                
        df = df.astype(str)
        for col in df.columns:
            if df[col].dtype == object: df[col] = df[col].str.strip()

        if '소속' in df.columns:
            df = df[df['소속'] == company_name.strip()]
        return df
    except: return pd.DataFrame()

def save_notice(company, title, content, is_important):
    sheet = get_worksheet("공지사항")
    sheet.append_row([company, get_today(), title, content, "TRUE" if is_important else "FALSE"])
    st.cache_data.clear()

def save_suggestion(company, title, content, author, is_private, password):
    sheet = get_worksheet("건의사항")
    sheet.append_row([company, get_today(), title, content, author, "TRUE" if is_private else "FALSE", str(password)])
    st.cache_data.clear()

def save_attendance(company, name, type_val, date_range_str, reason, password, approver):
    sheet = get_worksheet("근태신청")
    if company == "장안 제이유":
        initial_status = "1차승인대기" if approver in JANGAN_FOREMEN else "2차승인대기"
    else:
        initial_status = "승인대기" 
    sheet.append_row([company, get_today(), name, type_val, date_range_str, reason, initial_status, str(password), approver])
    st.cache_data.clear()

def save_schedule(company, date_str, title, content, author):
    sheet = get_worksheet("일정관리")
    sheet.append_row([company, date_str, title, content, author])
    st.cache_data.clear()

def update_attendance_step(sheet_name, row_idx, new_status, next_approver=None):
    sheet = get_worksheet(sheet_name)
    sheet.update_cell(row_idx + 2, 7, new_status)
    if next_approver: sheet.update_cell(row_idx + 2, 9, next_approver)
    st.cache_data.clear()

def delete_row_by_index(sheet_name, row_idx):
    sheet = get_worksheet(sheet_name)
    sheet.delete_rows(row_idx + 2)
    st.cache_data.clear()

def update_data_cell(sheet_name, row_idx, col_idx, new_value):
    sheet = get_worksheet(sheet_name)
    sheet.update_cell(row_idx + 2, col_idx, new_value)
    st.cache_data.clear()

def calculate_leave_usage(date_str, leave_type):
    usage = {}
    if "반차" in leave_type:
        try: usage[date_str[:7]] = 0.5
        except: pass
        return usage
    try:
        parts = date_str.split('~')
        s = datetime.strptime(parts[0].strip()[:10], "%Y-%m-%d").date()
        e = datetime.strptime(parts[1].strip()[:10], "%Y-%m-%d").date()
        kr_holidays = holidays.KR(years=[s.year, e.year])
        curr = s
        while curr <= e:
            if curr.weekday() < 5 and curr not in kr_holidays:
                m = curr.strftime("%Y-%m")
                usage[m] = usage.get(m, 0) + 1.0
            curr += timedelta(days=1)
    except: pass
    return usage

# ==========================================
# [0] 로그인 화면
# ==========================================
if 'company_name' not in st.session_state:
    with main_container.container():
        st.title("🏢 제이유 그룹 인트라넷")
        st.write("접속하려는 회사의 코드를 입력해주세요.")
        with st.form("login_form"):
            pw_input = st.text_input("회사 접속 코드", type="password")
            if st.form_submit_button("로그인"):
                if pw_input in COMPANIES:
                    st.session_state['company_name'] = COMPANIES[pw_input]
                    st.session_state['calendar_key'] = str(uuid.uuid4())
                    st.rerun()
                else:
                    st.error("잘못된 접속 코드입니다.")
    st.stop()

# ==========================================
# [메인 로직]
# ==========================================
COMPANY = st.session_state['company_name']

with main_container.container():
    st.title(f"🏢 {COMPANY}")

    if 'show_sugg_form' not in st.session_state: st.session_state['show_sugg_form'] = False
    if 'show_attend_form' not in st.session_state: st.session_state['show_attend_form'] = False

    def toggle_sugg(): st.session_state['show_sugg_form'] = not st.session_state['show_sugg_form']
    def toggle_attend(): st.session_state['show_attend_form'] = not st.session_state['show_attend_form']

    tabs = ["📋 공지", "🗣️ 제안", "📆 근무표", "📅 근태신청", "⚙️ 관리자"]
    selected_tab = st.radio("메뉴 선택", tabs, horizontal=True, label_visibility="collapsed")
    
    st.write("")

    # 1. 공지사항
    if selected_tab == "📋 공지":
        c_space, c_btn = st.columns([0.75, 0.25])
        with c_btn:
            if st.button("🔄 새로고침", key="re_1"): 
                st.cache_data.clear()
                st.rerun()
        
        df = load_data("공지사항", COMPANY)
        if df.empty: st.info("등록된 공지사항이 없습니다.")
        else:
            for idx, row in df.iloc[::-1].iterrows():
                is_imp = str(row.get("중요", "FALSE")).upper() == "TRUE"
                with st.container(border=True):
                    if is_imp: st.markdown(f":red[**[중요] 🔥 {row['제목']}**]")
                    else: st.subheader(f"📌 {row['제목']}")
                    st.caption(f"📅 {row['작성일']}")
                    st.markdown(f"{row['내용']}")
                    
                    if st.session_state.get('logged_in_manager') == "MASTER":
                        with st.expander("🛠️ 관리자 메뉴 (수정/삭제)"):
                            u_title = st.text_input("제목 수정", value=row['제목'], key=f"edit_t_{idx}")
                            u_content = st.text_area("내용 수정", value=row['내용'], key=f"edit_c_{idx}")
                            c1, c2 = st.columns(2)
                            if c1.button("💾 수정 저장", key=f"save_{idx}"):
                                update_data_cell("공지사항", idx, 3, u_title)
                                update_data_cell("공지사항", idx, 4, u_content)
                                st.success("수정 완료"); tm.sleep(1); st.rerun()
                            if c2.button("🗑️ 삭제", key=f"del_{idx}", type="secondary"):
                                delete_row_by_index("공지사항", idx)
                                st.success("삭제 완료"); tm.sleep(1); st.rerun()

    # 2. 제안
    elif selected_tab == "🗣️ 제안":
        if st.button("✍️ 제안 작성하기", on_click=toggle_sugg): pass
        
        if st.session_state['show_sugg_form']:
            with st.container(border=True):
                with st.form("sugg_form", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    author = c1.text_input("작성자")
                    pw = c2.text_input("비밀번호(4자리)", type="password")
                    title = st.text_input("제목")
                    content = st.text_area("내용")
                    private = st.checkbox("🔒 비공개")
                    if st.form_submit_button("등록"):
                        save_suggestion(COMPANY, title, content, author, private, pw)
                        st.success("✅ 등록되었습니다.")
                        tm.sleep(1)
                        st.session_state['show_sugg_form'] = False; st.rerun()
        
        st.divider()
        df_s = load_data("건의사항", COMPANY)
        if not df_s.empty:
            for idx, row in df_s.iloc[::-1].iterrows():
                show_content = True
                if str(row.get("비공개","FALSE")) == "TRUE": show_content = False 
                if show_content or st.session_state.get('logged_in_manager') == "MASTER":
                    with st.container(border=True):
                        if str(row.get("비공개","FALSE")) == "TRUE": st.write(f"🔒 **{row['제목']}** (비공개)")
                        else: st.write(f"**{row['제목']}**")
                        
                        st.caption(f"작성자: {row['작성자']}")
                        if show_content: st.write(row['내용'])
                        
                        if st.session_state.get('logged_in_manager') == "MASTER":
                            with st.expander("🛠️ 관리자 메뉴 (수정/삭제)"):
                                u_s_title = st.text_input("제목 수정", value=row['제목'], key=f"edit_st_{idx}")
                                u_s_content = st.text_area("내용 수정", value=row['내용'], key=f"edit_sc_{idx}")
                                c1, c2 = st.columns(2)
                                if c1.button("💾 수정 저장", key=f"save_s_{idx}"):
                                    update_data_cell("건의사항", idx, 3, u_s_title)
                                    update_data_cell("건의사항", idx, 4, u_s_content)
                                    st.success("수정 완료"); tm.sleep(1); st.rerun()
                                if c2.button("🗑️ 삭제", key=f"del_sugg_{idx}", type="secondary"):
                                    delete_row_by_index("건의사항", idx)
                                    st.success("삭제 완료"); tm.sleep(1); st.rerun()

    # 3. 근무표
    elif selected_tab == "📆 근무표":
        c_space, c_btn, c_view = st.columns([0.55, 0.20, 0.25])
        with c_space: st.write("")
        with c_btn:
            if st.button("🔄 새로고침", key="cal_ref"): 
                st.cache_data.clear()
                st.session_state['calendar_key'] = str(uuid.uuid4())
                st.rerun()
        with c_view:
            view_type = st.radio("보기", ["달력", "목록"], horizontal=True, label_visibility="collapsed")

        events = []
        now_kst = datetime.now(KST)
        kr_holidays = holidays.KR(years=[now_kst.year, now_kst.year+1])
        for d, n in kr_holidays.items():
            events.append({"title": n, "start": str(d), "color": "#FF4B4B", "extendedProps": {"type": "holiday"}})

        df_sch = load_data("일정관리", COMPANY)
        if not df_sch.empty and '날짜' in df_sch.columns:
            for i, r in df_sch.iterrows():
                start, end = r['날짜'], r['날짜']
                if "~" in r['날짜']:
                    try:
                        s, e = r['날짜'].split("~")
                        start = s.strip()
                        end = (datetime.strptime(e.strip(), "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    except: pass
                
                evt_color = "#8A2BE2" 
                title_text = str(r['제목'])
                
                if title_text.startswith("[RED]"):
                    evt_color = "#FF4B4B" 
                    title_text = title_text.replace("[RED]", "")
                elif title_text.startswith("[휴무]"): 
                    evt_color = "#FF4B4B"

                events.append({"title": f"📢 {title_text}", "start": start, "end": end, "color": evt_color, "extendedProps": {"content": r['내용'], "type": "schedule"}})

        df_cal = load_data("근태신청", COMPANY)
        approved_df = pd.DataFrame()
        if not df_cal.empty and '상태' in df_cal.columns:
            approved_df = df_cal[df_cal['상태'] == '최종승인']
            for i, r in approved_df.iterrows():
                try:
                    raw_dt = r.get('날짜및시간', '')
                    start_d, end_d = raw_dt[:10], raw_dt[:10]
                    if "~" in raw_dt:
                        parts = raw_dt.split("~")
                        start_d = parts[0].strip()[:10]
                        end_part = parts[1].strip()
                        if len(end_part) > 5:
                            end_obj = datetime.strptime(end_part[:10], "%Y-%m-%d") + timedelta(days=1)
                            end_d = end_obj.strftime("%Y-%m-%d")
                        else: end_d = start_d
                    l_type = r['구분']
                    col = "#D9534F" if "연차" in l_type else "#0275D8"
                    events.append({
                        "title": f"[{r['이름']}] {l_type}", 
                        "start": start_d, "end": end_d, "color": col,
                        "extendedProps": {"name": r['이름'], "type": "leave", "content": r['사유'], "raw_date": raw_dt}
                    })
                except: pass

        if view_type == "달력":
            calendar_css = """
                .fc { background: white !important; }
                .fc-toolbar-title { color: #333333 !important; font-weight: bold !important; font-size: 1.5rem !important; }
                .fc-button { color: #333333 !important; border: 1px solid #ddd !important; }
                .fc-daygrid-day-number { color: #333333 !important; text-decoration: none !important; }
                .fc-col-header-cell-cushion { color: #333333 !important; text-decoration: none !important; font-weight: bold !important; }
                .fc-day-sun .fc-daygrid-day-number { color: #FF4B4B !important; }
                .fc-day-sun .fc-col-header-cell-cushion { color: #FF4B4B !important; }
                .fc-day-sat .fc-daygrid-day-number { color: #1E90FF !important; }
                .fc-day-sat .fc-col-header-cell-cushion { color: #1E90FF !important; }
            """
            cal = calendar(events=events, options={"initialView": "dayGridMonth", "height": 750}, key=st.session_state['calendar_key'], custom_css=calendar_css)
            
            if cal.get("callback") == "eventClick":
                evt = cal["eventClick"]["event"]
                props = evt.get("extendedProps", {})
                st.info(f"📌 {evt['title']}")
                if props.get("type") == "leave":
                    name = props.get("name")
                    user_df = approved_df[approved_df['이름'] == name]
                    total_usage = {}
                    for _, u_row in user_df.iterrows():
                        usage = calculate_leave_usage(u_row['날짜및시간'], u_row['구분'])
                        for m, val in usage.items():
                            total_usage[m] = total_usage.get(m, 0) + val
                    st.write(f"📊 **{name}님의 월별 실사용 현황**")
                    if total_usage:
                        st.dataframe(pd.DataFrame(list(total_usage.items()), columns=["월", "사용일수"]).sort_values("월"), hide_index=True)
                    else:
                        st.info("집계된 사용 내역이 없습니다.")
        else:
            filtered_events = [e for e in events if e.get("extendedProps", {}).get("type") != "holiday"]
            if filtered_events:
                list_df = pd.DataFrame(filtered_events)
                st.dataframe(list_df, column_config={"color": None, "extendedProps": None, "resourceId": None, "title": "내용", "start": "시작", "end": "종료"}, hide_index=True, use_container_width=True)
            else: st.info("등록된 일정이 없습니다.")

    # 4. 근태신청
    elif selected_tab == "📅 근태신청":
        st.write("### 📅 연차/근태 신청")
        if st.button("📝 신청서 작성", on_click=toggle_attend): pass
        
        if st.session_state['show_attend_form']:
            with st.container(border=True):
                date_mode = st.radio("기간 설정", ["반차/외출/병가 (단일)", "기간 (연차/휴가)"], horizontal=True)
                final_date_str = ""
                if date_mode == "반차/외출/병가 (단일)":
                    st.write("**📆 일시 및 시간 선택 (단일)**")
                    dc1, dc2, dc3 = st.columns(3)
                    d_sel = dc1.date_input("날짜 선택", value=datetime.now(KST))
                    
                    t_start = dc2.time_input("시작 시간", value=time(8,0))
                    t_end = dc3.time_input("종료 시간", value=time(17,0)) 
                    final_date_str = f"{d_sel} {t_start.strftime('%H:%M')} ~ {t_end.strftime('%H:%M')}"
                else:
                    st.write("**📆 기간 및 시간 선택 (연차/휴가)**")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        st.caption("시작 일시")
                        d_start = st.date_input("시작일", value=datetime.now(KST))
                        t_start = st.time_input("시작 시간", value=time(8,0))
                    with dc2:
                        st.caption("종료 일시")
                        d_end = st.date_input("종료일", value=datetime.now(KST))
                        t_end = st.time_input("종료 시간", value=time(17,0))
                    if d_start > d_end: st.error("⚠️ 종료일이 시작일보다 빠릅니다.")
                    else: final_date_str = f"{d_start} {t_start.strftime('%H:%M')} ~ {d_end} {t_end.strftime('%H:%M')}"
                
                st.info(f"선택: {final_date_str}")
                
                with st.form("att_form"):
                    c1, c2 = st.columns(2)
                    name = c1.text_input("이름")
                    pw = c2.text_input("비밀번호(본인확인용)", type="password")
                    type_val = st.selectbox("구분", ["연차", "반차(오전)", "반차(오후)", "조퇴", "외출", "결근"])
                    
                    if COMPANY == "장안 제이유":
                        approver_options = JANGAN_FOREMEN + JANGAN_MID
                    else:
                        approver_options = ULSAN_APPROVERS
                    
                    approver = st.selectbox("승인 요청 대상", approver_options)
                    reason = st.text_input("사유")
                    if st.form_submit_button("신청하기"):
                        if not name or not pw: st.error("정보를 입력해주세요.")
                        else:
                            save_attendance(COMPANY, name, type_val, final_date_str, reason, pw, approver)
                            st.success(f"✅ 승인 요청 전송 완료")
                            tm.sleep(1.5)
                            st.session_state['show_attend_form']=False; st.rerun()
        st.divider()
        with st.form("search"):
            sc1, sc2 = st.columns(2)
            s_name = sc1.text_input("이름")
            s_pw = sc2.text_input("비밀번호", type="password")
            if st.form_submit_button("조회"):
                df = load_data("근태신청", COMPANY)
                if not df.empty and '이름' in df.columns:
                    my_df = df[(df['이름']==s_name) & (df['비밀번호']==s_pw)]
                    if my_df.empty: st.error("내역 없음")
                    else:
                        for _, r in my_df.iterrows(): st.info(f"{r['날짜및시간']} | {r['구분']} | {r['상태']}")
                else: st.error("데이터가 없습니다.")

    # 5. 관리자
    elif selected_tab == "⚙️ 관리자":
        st.subheader("⚙️ 관리자 전용")
        if 'logged_in_manager' not in st.session_state:
            user_db = load_user_db()
            
            if COMPANY == "장안 제이유":
                manager_options = ["선택안함"] + JANGAN_FOREMEN + JANGAN_MID + ["MASTER"]
            else:
                manager_options = ["선택안함"] + ULSAN_APPROVERS + ["MASTER"]

            selected_name = st.selectbox("관리자 선택", manager_options)
            
            if selected_name != "선택안함":
                if selected_name not in user_db:
                    st.warning(f"🔒 '{selected_name}' 초기 비밀번호 설정")
                    with st.form("init_pw"):
                        new_pw = st.text_input("새 비밀번호", type="password")
                        chk_pw = st.text_input("확인", type="password")
                        if st.form_submit_button("설정"):
                            if new_pw == chk_pw and new_pw:
                                user_db[selected_name] = new_pw
                                save_user_db(user_db)
                                st.success("설정 완료!"); tm.sleep(1); st.rerun()
                            else: st.error("비밀번호 불일치")
                else:
                    with st.form("manager_login_form"):
                        input_pw = st.text_input("비밀번호", type="password")
                        if st.form_submit_button("로그인"):
                            if str(input_pw) == str(user_db[selected_name]):
                                st.session_state['logged_in_manager'] = selected_name; st.rerun()
                            else: st.error("비밀번호 오류")
            
            st.write("")
            if st.toggle("🔐 시스템 최고 관리자 (Master) 로그인"):
                with st.form("master_login_form"):
                    master_pw = st.text_input("Master PW", type="password")
                    if st.form_submit_button("Master Login"):
                        if master_pw == st.secrets["admin_password"]:
                            st.session_state['logged_in_manager'] = "MASTER"; st.rerun()
                        else: st.error("비밀번호 오류")
        else:
            manager_id = st.session_state['logged_in_manager']
            manager_name = manager_id
            
            # 로그아웃 버튼 공간 확보
            c_info, c_logout = st.columns([0.75, 0.25])
            with c_info:
                st.success(f"👋 접속중: {manager_name}")
            with c_logout:
                if st.button("로그아웃", type="secondary"):
                    del st.session_state['logged_in_manager']; st.rerun()
            
            if manager_id == "MASTER":
                if st.toggle("🔐 관리자 비밀번호 초기화 (마스터 기능)"):
                    user_db = load_user_db()
                    registered_users = [u for u in user_db.keys() if u != "MASTER"]
                    if not registered_users: st.info("대상 없음")
                    else:
                        target = st.selectbox("대상 선택", ["선택안함"] + registered_users)
                        if target != "선택안함":
                            if st.button(f"'{target}' 초기화"):
                                del user_db[target]; save_user_db(user_db)
                                st.success("초기화 완료"); tm.sleep(1); st.rerun()

            m_tab1, m_tab2, m_tab3 = st.tabs(["✅ 결재", "📢 공지/일정", "📊 통계"])
            with m_tab1:
                df = load_data("근태신청", COMPANY)
                if not df.empty and '상태' in df.columns:
                    pend = pd.DataFrame()
                    if COMPANY == "장안 제이유":
                        if manager_id == "MASTER":
                            pend = df[df['상태'] == '최종승인대기']
                            st.info("📢 최종 승인 대기")
                        elif manager_id == "반장":
                            pend = df[df['상태'] == '2차승인대기']
                            st.info("📢 반장 승인 대기")
                        else:
                            pend = df[(df['상태'] == '1차승인대기') & (df['승인담당자'] == manager_name)]
                            st.info("📢 조장 승인 대기")
                    else:
                        if manager_id == "MASTER":
                            pend = df[df['상태'] == '승인대기']
                            st.info("📢 전체 승인 대기 (Master 권한)")
                        elif manager_id in ULSAN_APPROVERS:
                            pend = df[(df['상태'] == '승인대기') & (df['승인담당자'].str.strip() == manager_name.strip())]
                            st.info(f"📢 {manager_name}님 승인 대기")

                    if pend.empty: st.info("대기중인 건이 없습니다.")
                    else:
                        for i, r in pend.iterrows():
                            with st.expander(f"[{r['이름']}] {r['구분']} - {r['날짜및시간']}"):
                                st.write(f"사유: {r['사유']}")
                                c_app, c_rej = st.columns(2)
                                if c_app.button("승인", key=f"app_{i}"):
                                    if COMPANY == "장안 제이유":
                                        if manager_id == "MASTER": 
                                            update_attendance_step("근태신청", i, "최종승인")
                                        elif manager_id == "반장": 
                                            update_attendance_step("근태신청", i, "최종승인대기", "MASTER")
                                        else: 
                                            update_attendance_step("근태신청", i, "2차승인대기", "반장")
                                    else:
                                        update_attendance_step("근태신청", i, "최종승인")
                                    st.success("승인됨"); tm.sleep(1); st.rerun()
                                    
                                if c_rej.button("반려", key=f"rej_{i}"):
                                    update_attendance_step("근태신청", i, "반려")
                                    st.error("반려됨"); tm.sleep(1); st.rerun()
                else: st.info("데이터 없음")

            with m_tab2:
                st.write("공지사항/일정 등록")
                with st.form("n_form", clear_on_submit=True):
                    type_sel = st.selectbox("유형", ["공지사항", "일정"])
                    t = st.text_input("제목")
                    c = st.text_area("내용")
                    is_imp = st.checkbox("중요 공지", value=False)
                    
                    # [추가] 기간 선택 가능
                    d_range = st.date_input("날짜 (기간 선택 가능)", value=[datetime.now(KST).date()], help="기간을 선택하려면 시작일과 종료일을 클릭하세요.")
                    
                    is_holiday = False
                    if manager_id == "MASTER" and type_sel == "일정":
                        is_holiday = st.checkbox("🚩 전사 휴무/특별 일정 (캘린더에 빨간색 표시)")

                    if st.form_submit_button("등록"):
                        if type_sel == "공지사항": 
                            save_notice(COMPANY, t, c, is_imp)
                        else: 
                            final_date_str = ""
                            if len(d_range) == 2:
                                final_date_str = f"{d_range[0]} ~ {d_range[1]}"
                            elif len(d_range) == 1:
                                final_date_str = str(d_range[0])
                            else:
                                st.error("날짜를 선택해주세요.")
                                st.stop()

                            final_title = t
                            if is_holiday: final_title = f"[RED]{t}"
                            
                            save_schedule(COMPANY, final_date_str, final_title, c, manager_name)
                        st.success("등록 완료"); tm.sleep(1); st.rerun()
                
                # [추가] 등록된 일정 관리 (수정/삭제)
                st.divider()
                st.write("### 📋 등록된 일정 관리 (수정/삭제)")
                df_sch = load_data("일정관리", COMPANY)
                if not df_sch.empty:
                    for i, r in df_sch.iterrows():
                        # 자신이 작성했거나 MASTER인 경우에만 관리 가능
                        if manager_id == "MASTER" or r['작성자'] == manager_name:
                            with st.expander(f"{r['날짜']} : {r['제목']}"):
                                
                                # 날짜 파싱 (단일 or 기간)
                                existing_title = str(r['제목'])
                                is_red = False
                                clean_title = existing_title
                                if existing_title.startswith("[RED]"):
                                    is_red = True
                                    clean_title = existing_title.replace("[RED]", "")
                                
                                new_date_str = st.text_input("날짜 (YYYY-MM-DD 또는 ~ 범위)", value=r['날짜'], key=f"edit_sd_{i}")
                                new_title = st.text_input("제목", value=clean_title, key=f"edit_st_{i}")
                                new_content = st.text_area("내용", value=r['내용'], key=f"edit_sc_{i}")
                                
                                new_is_red = is_red
                                if manager_id == "MASTER":
                                    new_is_red = st.checkbox("🚩 휴무(빨간색) 태그 적용", value=is_red, key=f"chk_red_{i}")
                                
                                c1, c2 = st.columns(2)
                                if c1.button("수정", key=f"upd_s_{i}"):
                                    final_t = new_title
                                    if new_is_red: final_t = f"[RED]{new_title}"
                                    
                                    # 날짜(2열), 제목(3열), 내용(4열)
                                    update_data_cell("일정관리", i, 2, new_date_str)
                                    update_data_cell("일정관리", i, 3, final_t)
                                    update_data_cell("일정관리", i, 4, new_content)
                                    st.success("수정됨"); tm.sleep(1); st.rerun()
                                    
                                if c2.button("삭제", key=f"del_s_{i}"):
                                    delete_row_by_index("일정관리", i)
                                    st.success("삭제됨"); tm.sleep(1); st.rerun()

            with m_tab3:
                st.write("### 📊 월별 연차 사용 현황")
                df = load_data("근태신청", COMPANY)
                if not df.empty and '상태' in df.columns:
                    df = df[df['상태'] == '최종승인']
                    stats_data = {} 
                    for _, row in df.iterrows():
                        usage = calculate_leave_usage(row['날짜및시간'], row['구분'])
                        name = row['이름']
                        if name not in stats_data: stats_data[name] = {}
                        for mon, val in usage.items():
                            stats_data[name][mon] = stats_data[name].get(mon, 0) + val
                    
                    if stats_data:
                        final_list = []
                        for name, mon_data in stats_data.items():
                            for mon, val in mon_data.items():
                                final_list.append({"이름": name, "월": mon, "사용일수": val})
                        
                        try:
                            stat_df = pd.DataFrame(final_list, columns=["이름", "월", "사용일수"])
                            if not stat_df.empty:
                                pivot = stat_df.pivot_table(index="이름", columns="월", values="사용일수", aggfunc="sum", fill_value=0)
                                st.dataframe(pivot)
                            else:
                                st.info("집계할 데이터가 부족합니다.")
                        except Exception as e:
                            st.warning("⚠️ 통계 집계 중 오류가 발생했습니다.")
                            if final_list: st.dataframe(pd.DataFrame(final_list))

                    else: st.info("집계 데이터 없음")
                else: st.info("데이터 없음")