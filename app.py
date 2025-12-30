import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time, timedelta
import uuid
import pytz
import holidays
from streamlit_calendar import calendar
import time as tm  # [수정] 이름 충돌 방지를 위해 'tm'으로 변경

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
# [스타일] CSS: 제목 겹침 해결 & 버튼 크기 최적화
# =========================================================
st.markdown("""
<style>
    /* [1] 제목(h1) 모바일 최적화 (글자 겹침/잘림 방지) */
    h1 {
        padding-top: 1rem !important;
        font-size: 2rem !important;
    }
    @media (max-width: 640px) {
        h1 {
            font-size: 1.5rem !important;
            margin-top: 0.5rem !important;
        }
        .block-container {
            padding-top: 2rem !important;
        }
    }

    /* [2] 상단 이상한 아이콘 및 사이드바 버튼 숨김 */
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }

    /* [3] Expander 아이콘 숨김 */
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary svg { display: none !important; }
    div[data-testid="stExpander"] summary { padding-left: 10px !important; }

    /* [4] 버튼 스타일: 기본적으로 내용물 크기에 맞게 */
    div.stButton > button {
        width: auto !important;
        padding: 0.4rem 1rem;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white !important;
    }

    /* [5] 폼 내부 버튼은 꽉 차게 (신청/등록 버튼) */
    div[data-testid="stForm"] div.stButton > button {
        width: 100% !important;
        background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
    }

    /* [6] 로그아웃 버튼 전용 스타일 (작고 빨갛게) */
    div[data-testid="column"] button[kind="secondary"] {
        background: #FF4B4B !important;
        color: white !important;
        font-size: 12px !important;
        padding: 0.2rem 0.5rem !important;
        height: auto !important;
        min-height: 0px !important;
    }

    /* [7] 입력창 디자인 */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px;
    }
    
    /* [8] 달력 높이 */
    iframe[title="streamlit_calendar.calendar"] { height: 750px !important; }
    
    /* [9] 본문 폰트 */
    p { font-size: 16px; word-break: keep-all; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# [설정] 관리자 및 회사 정보
# =========================================================
FOREMEN = ["JK 조장", "JX 메인 조장", "JX 어퍼 조장", "MX5 조장", "피더 조장"]
MIDDLE_MANAGERS = ["반장"]
APPROVER_OPTIONS = FOREMEN + MIDDLE_MANAGERS
ALL_MANAGERS = FOREMEN + MIDDLE_MANAGERS + ["MASTER"]

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
        return {str(row['이름']): str(row['비밀번호']) for row in data}
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
        if '소속' in df.columns:
            df['소속'] = df['소속'].str.strip()
            df = df[df['소속'] == company_name.strip()]
        return df
    except: return pd.DataFrame()

# 저장/삭제 함수들
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
    initial_status = "1차승인대기" if approver in FOREMEN else "2차승인대기"
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
    # 상단 헤더
    st.title(f"🏢 {COMPANY}")

    # 상태변수 초기화
    if 'show_sugg_form' not in st.session_state: st.session_state['show_sugg_form'] = False
    if 'show_attend_form' not in st.session_state: st.session_state['show_attend_form'] = False

    def toggle_sugg(): st.session_state['show_sugg_form'] = not st.session_state['show_sugg_form']
    def toggle_attend(): st.session_state['show_attend_form'] = not st.session_state['show_attend_form']

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 공지", "🗣️ 제안", "📆 근무표", "📅 근태신청", "⚙️ 관리자"])

    # 1. 공지사항
    with tab1:
        if st.button("🔄 새로고침", key="re_1"): st.cache_data.clear(); st.rerun()
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

    # 2. 제안
    with tab2:
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
                        tm.sleep(1) # [수정] time -> tm
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
                            if st.button("🗑️ 삭제", key=f"del_sugg_{idx}"):
                                delete_row_by_index("건의사항", idx)
                                st.success("삭제됨")
                                tm.sleep(1); st.rerun() # [수정] time -> tm

    # 3. 근무표
    with tab3:
        c_btn, c_view = st.columns([0.6, 0.4])
        with c_btn:
            if st.button("🔄 새로고침", key="cal_ref"): 
                st.cache_data.clear(); st.session_state['calendar_key'] = str(uuid.uuid4()); st.rerun()
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
                events.append({"title": f"📢 {r['제목']}", "start": start, "end": end, "color": "#8A2BE2", "extendedProps": {"content": r['내용'], "type": "schedule"}})

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
                .fc-day-sun .fc-daygrid-day-number { color: #FF4B4B !important; }
                .fc-day-sat .fc-daygrid-day-number { color: #1E90FF !important; }
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
            filtered_events = [e for e in events if e.get("extendedProps", {}).get("type") != "holiday"]
            if filtered_events:
                list_df = pd.DataFrame(filtered_events)
                st.dataframe(list_df, column_config={"color": None, "extendedProps": None, "resourceId": None, "title": "내용", "start": "시작", "end": "종료"}, hide_index=True, use_container_width=True)
            else: st.info("등록된 일정이 없습니다.")

    # 4. 근태신청
    with tab4:
        st.write("### 📅 연차/근태 신청")
        if st.button("📝 신청서 작성", on_click=toggle_attend): pass
        
        if st.session_state['show_attend_form']:
            with st.container(border=True):
                date_mode = st.radio("기간 설정", ["하루/반차/외출 (단일)", "기간 (연차/휴가)"], horizontal=True)
                final_date_str = ""
                if date_mode == "하루/반차/외출 (단일)":
                    st.write("**📆 일시 및 시간 선택 (단일)**")
                    dc1, dc2, dc3 = st.columns(3)
                    d_sel = dc1.date_input("날짜 선택", value=datetime.now(KST))
                    t_start = dc2.time_input("시작 시간", value=time(9,0)) # [정상 작동] datetime.time
                    t_end = dc3.time_input("종료 시간", value=time(18,0))
                    final_date_str = f"{d_sel} {t_start.strftime('%H:%M')} ~ {t_end.strftime('%H:%M')}"
                else:
                    st.write("**📆 기간 및 시간 선택 (연차/휴가)**")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        st.caption("시작 일시")
                        d_start = st.date_input("시작일", value=datetime.now(KST))
                        t_start = st.time_input("시작 시간", value=time(9,0))
                    with dc2:
                        st.caption("종료 일시")
                        d_end = st.date_input("종료일", value=datetime.now(KST))
                        t_end = st.time_input("종료 시간", value=time(18,0))
                    if d_start > d_end: st.error("⚠️ 종료일이 시작일보다 빠릅니다.")
                    else: final_date_str = f"{d_start} {t_start.strftime('%H:%M')} ~ {d_end} {t_end.strftime('%H:%M')}"
                
                st.info(f"선택: {final_date_str}")
                
                with st.form("att_form"):
                    c1, c2 = st.columns(2)
                    name = c1.text_input("이름")
                    pw = c2.text_input("비밀번호(본인확인용)", type="password")
                    type_val = st.selectbox("구분", ["연차", "반차(오전)", "반차(오후)", "조퇴", "외출", "결근"])
                    approver = st.selectbox("승인 요청 대상", APPROVER_OPTIONS)
                    reason = st.text_input("사유")
                    if st.form_submit_button("신청하기"):
                        if not name or not pw: st.error("정보를 입력해주세요.")
                        else:
                            save_attendance(COMPANY, name, type_val, final_date_str, reason, pw, approver)
                            st.success(f"✅ 승인 요청 전송 완료")
                            tm.sleep(1.5) # [수정] time -> tm
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
    with tab5:
        st.subheader("⚙️ 관리자 및 조장/반장 전용")
        if 'logged_in_manager' not in st.session_state:
            user_db = load_user_db()
            selected_name = st.selectbox("관리자 선택", ["선택안함"] + ALL_MANAGERS)
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
                                st.success("설정 완료!"); tm.sleep(1); st.rerun() # [수정]
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
            
            # [수정] 로그아웃 버튼: 작고 심플하게
            c_info, c_logout = st.columns([0.8, 0.2])
            with c_info:
                st.success(f"👋 접속중: {manager_name}")
            with c_logout:
                # secondary 타입 + CSS 조합으로 작고 빨간 버튼 구현
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
                                st.success("초기화 완료"); tm.sleep(1); st.rerun() # [수정]

            m_tab1, m_tab2, m_tab3 = st.tabs(["✅ 결재", "📢 공지/일정", "📊 통계"])
            with m_tab1:
                df = load_data("근태신청", COMPANY)
                if not df.empty and '상태' in df.columns:
                    pend = pd.DataFrame()
                    if manager_id == "MASTER":
                        pend = df[df['상태'] == '최종승인대기']
                        st.info("📢 최종 승인 대기")
                    elif manager_id == "반장":
                        pend = df[df['상태'] == '2차승인대기']
                        st.info("📢 반장 승인 대기")
                    else:
                        pend = df[(df['상태'] == '1차승인대기') & (df['승인담당자'] == manager_name)]
                        st.info("📢 조장 승인 대기")

                    if pend.empty: st.info("대기중인 건이 없습니다.")
                    else:
                        for i, r in pend.iterrows():
                            with st.expander(f"[{r['이름']}] {r['구분']} - {r['날짜및시간']}"):
                                st.write(f"사유: {r['사유']}")
                                c_app, c_rej = st.columns(2)
                                if c_app.button("승인", key=f"app_{i}"):
                                    if manager_id == "MASTER": 
                                        update_attendance_step("근태신청", i, "최종승인")
                                    elif manager_id == "반장": 
                                        update_attendance_step("근태신청", i, "최종승인대기", "MASTER")
                                    else: 
                                        update_attendance_step("근태신청", i, "2차승인대기", "반장")
                                    st.success("승인됨"); tm.sleep(1); st.rerun() # [수정]
                                if c_rej.button("반려", key=f"rej_{i}"):
                                    update_attendance_step("근태신청", i, "반려")
                                    st.error("반려됨"); tm.sleep(1); st.rerun() # [수정]
                else: st.info("데이터 없음")

            with m_tab2:
                st.write("공지사항/일정 등록")
                with st.form("n_form", clear_on_submit=True):
                    type_sel = st.selectbox("유형", ["공지사항", "일정"])
                    t = st.text_input("제목")
                    c = st.text_area("내용")
                    is_imp = st.checkbox("중요 공지", value=False)
                    d_s = st.date_input("날짜(일정용)", value=datetime.now(KST))
                    if st.form_submit_button("등록"):
                        if type_sel == "공지사항": save_notice(COMPANY, t, c, is_imp)
                        else: save_schedule(COMPANY, str(d_s), t, c, manager_name)
                        st.success("등록 완료"); tm.sleep(1); st.rerun() # [수정]
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
                        stat_df = pd.DataFrame(final_list)
                        pivot = stat_df.pivot_table(index="이름", columns="월", values="사용일수", aggfunc="sum", fill_value=0)
                        st.dataframe(pivot)
                    else: st.info("집계 데이터 없음")
                else: st.info("데이터 없음")