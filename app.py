import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time, timedelta
import uuid
import pytz
import holidays
from streamlit_calendar import calendar
import json
import os

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="제이유 사내광장", page_icon="🏢", layout="centered")

# --- [설정] 한국 시간 타임존 정의 ---
KST = pytz.timezone('Asia/Seoul')

# --- [설정] 관리자 및 회사 정보 ---
FOREMEN = [
    "JK 조장", "JX 메인 조장", "JX 어퍼 조장",
    "MX5 조장", "피더 조장"
]

MIDDLE_MANAGERS = ["반장"]
ALL_MANAGERS = FOREMEN + MIDDLE_MANAGERS

COMPANIES = {
    "9424": "장안 제이유",
    "0645": "울산 제이유"
}

USER_DB_FILE = 'user_db.json'

# --- [스타일] CSS ---
st.markdown("""
<style>
    div[data-testid="stMarkdownContainer"] p { font-size: 18px !important; line-height: 1.6; }
    div[data-testid="stMetricValue"] { font-size: 24px !important; color: #FF4B4B !important; }
    iframe[title="streamlit_calendar.calendar"] { height: 750px !important; min-height: 750px !important; }
</style>
""", unsafe_allow_html=True)

# --- [함수] 로컬 사용자 DB 관리 ---
def load_user_db():
    if not os.path.exists(USER_DB_FILE):
        return {}
    with open(USER_DB_FILE, 'r') as f:
        return json.load(f)

def save_user_db(db):
    with open(USER_DB_FILE, 'w') as f:
        json.dump(db, f)

# --- [함수] 유틸리티 ---
def get_korea_time():
    return datetime.now(KST).strftime("%Y-%m-%d")

def get_worksheet(sheet_name):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("사내공지사항DB").worksheet(sheet_name)

# --- [데이터 로드] ---
@st.cache_data(ttl=300)
def load_data(sheet_name, company_name):
    try:
        sheet = get_worksheet(sheet_name)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # [수정 완료] 기존 버그 수정
        # '상태' 컬럼 유무를 검사하던 코드를 삭제했습니다.
        # 이제 데이터가 아예 비어있을 때만 컬럼을 새로 만듭니다.
        if df.empty:
            if sheet_name == "근태신청":
                df = pd.DataFrame(columns=['소속', '작성일', '이름', '구분', '날짜및시간', '사유', '상태', '비밀번호', '승인자'])
            elif sheet_name == "공지사항":
                # 공지사항은 원래 '상태' 컬럼이 없으므로 이 부분이 정상적으로 실행됩니다.
                df = pd.DataFrame(columns=['소속', '작성일', '제목', '내용', '중요'])
            elif sheet_name == "건의사항":
                df = pd.DataFrame(columns=['소속', '작성일', '제목', '내용', '작성자', '비공개', '비밀번호'])
            elif sheet_name == "일정관리":
                 df = pd.DataFrame(columns=['소속', '날짜', '제목', '내용', '작성자'])

        # 문자열 변환
        df = df.astype(str)
        
        # 소속 필터링 (공백 제거 포함)
        if '소속' in df.columns:
            df['소속'] = df['소속'].str.strip()
            target_company = company_name.strip()
            df = df[df['소속'] == target_company]
            
        return df
    except Exception as e:
        return pd.DataFrame()

# --- [함수] 저장 로직 ---
def save_notice(company, title, content, is_important):
    sheet = get_worksheet("공지사항")
    imp_str = "TRUE" if is_important else "FALSE"
    sheet.append_row([company, get_korea_time(), title, content, imp_str])
    st.cache_data.clear()

def save_suggestion(company, title, content, author, is_private, password):
    sheet = get_worksheet("건의사항")
    sheet.append_row([company, get_korea_time(), title, content, author, "TRUE" if is_private else "FALSE", str(password)])
    st.cache_data.clear()

def save_attendance(company, name, type_val, date_range_str, reason, password, approver):
    sheet = get_worksheet("근태신청")
    sheet.append_row([company, get_korea_time(), name, type_val, date_range_str, reason, "대기중", str(password), approver])
    st.cache_data.clear()

def save_schedule(company, date_str, title, content, author):
    sheet = get_worksheet("일정관리")
    sheet.append_row([company, date_str, title, content, author])
    st.cache_data.clear()

def update_attendance_status(sheet_name, row_idx, new_status):
    sheet = get_worksheet(sheet_name)
    sheet.update_cell(row_idx + 2, 7, new_status)
    st.cache_data.clear()


# ==========================================
# [0] 로그인 화면
# ==========================================
if 'company_name' not in st.session_state:
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

COMPANY = st.session_state['company_name']
st.sidebar.title(f"📍 {COMPANY}")
if st.sidebar.button("로그아웃"):
    del st.session_state['company_name']
    if 'logged_in_manager' in st.session_state:
        del st.session_state['logged_in_manager']
    st.rerun()

st.title(f"🏢 {COMPANY} 사내광장")

# ==========================================
# [메인 로직]
# ==========================================
if 'show_sugg_form' not in st.session_state: st.session_state['show_sugg_form'] = False
if 'show_attend_form' not in st.session_state: st.session_state['show_attend_form'] = False

def toggle_sugg(): st.session_state['show_sugg_form'] = not st.session_state['show_sugg_form']
def toggle_attend(): st.session_state['show_attend_form'] = not st.session_state['show_attend_form']

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 공지", "🗣️ 건의", "📆 근무표", "📅 근태신청", "⚙️ 관리자"])

# 1. 공지사항
with tab1:
    if st.button("🔄 새로고침", key="re_1"): st.cache_data.clear(); st.rerun()
    df = load_data("공지사항", COMPANY)
    
    if df.empty:
        st.info("등록된 공지사항이 없습니다.")
    else:
        for idx, row in df.iloc[::-1].iterrows():
            is_imp = False
            if '중요' in row:
                is_imp = str(row['중요']).upper() == "TRUE"
                
            with st.container(border=True):
                if is_imp: st.markdown(f":red[**[중요] 🔥 {row['제목']}**]")
                else: st.subheader(f"📌 {row['제목']}")
                
                st.caption(f"📅 {row['작성일']}")
                st.markdown(f"{row['내용']}")

# 2. 건의사항
with tab2:
    if st.button("✍️ 작성하기", on_click=toggle_sugg): pass
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
                    st.success("등록됨"); st.session_state['show_sugg_form']=False; st.rerun()
    st.divider()
    df_s = load_data("건의사항", COMPANY)
    if not df_s.empty:
        for idx, row in df_s.iloc[::-1].iterrows():
            if str(row.get("비공개","FALSE")) != "TRUE":
                with st.container(border=True):
                    st.write(f"**{row['제목']}**")
                    st.caption(f"작성자: {row['작성자']}")

# 3. 근무표 (달력)
with tab3:
    c_btn, c_view = st.columns([0.6, 0.4])
    if c_btn.button("🔄 새로고침", key="cal_ref"): 
        st.cache_data.clear(); st.session_state['calendar_key'] = str(uuid.uuid4()); st.rerun()
    view_type = c_view.radio("보기", ["달력", "목록"], horizontal=True, label_visibility="collapsed")

    events = []
    
    # 공휴일
    now_kst = datetime.now(KST)
    kr_holidays = holidays.KR(years=[now_kst.year, now_kst.year+1])
    for d, n in kr_holidays.items():
        events.append({
            "title": n, 
            "start": str(d), 
            "color": "#FF4B4B",
            "extendedProps": {"type": "holiday"}
        })

    # 일정
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

    # 근태 (승인된 것만)
    df_cal = load_data("근태신청", COMPANY)
    approved_df = pd.DataFrame()
    if not df_cal.empty and '상태' in df_cal.columns:
        approved_df = df_cal[df_cal['상태'].isin(['최종승인', '승인'])]
        for i, r in approved_df.iterrows():
            raw_dt = r.get('날짜및시간', '')
            start_d, end_d = raw_dt.split(' ')[0], raw_dt.split(' ')[0]
            if "~" in raw_dt:
                try:
                    clean = raw_dt.split('(')[0].strip() if '(' in raw_dt else raw_dt
                    s_part, e_part = clean.split("~")
                    start_d = s_part.strip()
                    end_obj = datetime.strptime(e_part.strip(), "%Y-%m-%d") + timedelta(days=1)
                    end_d = end_obj.strftime("%Y-%m-%d")
                except: pass
            l_type = r['구분']
            col = "#D9534F" if "연차" in l_type else "#0275D8"
            events.append({
                "title": f"[{r['이름']}] {l_type}", 
                "start": start_d, "end": end_d, "color": col,
                "extendedProps": {"name": r['이름'], "type": "leave", "content": r['사유']}
            })

    if view_type == "달력":
        calendar_css = """
            .fc { background: white !important; }
            .fc-daygrid-day-number { color: #000000 !important; font-weight: bold !important; text-decoration: none !important; }
            .fc-col-header-cell-cushion { color: #000000 !important; font-weight: bold !important; text-decoration: none !important; }
            .fc-event { cursor: pointer; }
        """
        
        cal = calendar(
            events=events, 
            options={"initialView": "dayGridMonth", "height": 750}, 
            key=st.session_state['calendar_key'], 
            custom_css=calendar_css
        )
        
        if cal.get("callback") == "eventClick":
            evt = cal["eventClick"]["event"]
            props = evt.get("extendedProps", {})
            st.info(f"📌 {evt['title']}")
            if props.get("type") == "leave":
                name = props.get("name")
                user_df = approved_df[approved_df['이름'] == name]
                month_stats = {}
                for _, u_row in user_df.iterrows():
                    d_str = u_row['날짜및시간'].split(' ')[0]
                    try:
                        mon = d_str[:7]
                        val = 0.5 if "반차" in u_row['구분'] else 1.0
                        month_stats[mon] = month_stats.get(mon, 0) + val
                    except: pass
                st.write(f"📊 **{name}님의 월별 사용 현황**")
                if month_stats:
                    st.dataframe(pd.DataFrame(list(month_stats.items()), columns=["월", "사용일수"]).sort_values("월"), hide_index=True)
    else:
        filtered_events = [e for e in events if e.get("extendedProps", {}).get("type") != "holiday"]
        if filtered_events:
            list_df = pd.DataFrame(filtered_events)
            st.dataframe(
                list_df,
                column_config={
                    "color": None, 
                    "extendedProps": None, 
                    "resourceId": None,
                    "title": "내용",
                    "start": "시작",
                    "end": "종료"
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("등록된 일정이 없습니다.")

# 4. 근태신청
with tab4:
    st.write("### 📅 연차/근태 신청")
    if st.button("📝 신청서 작성", on_click=toggle_attend): pass
    
    if st.session_state['show_attend_form']:
        with st.container(border=True):
            with st.form("att_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("이름")
                pw = c2.text_input("비밀번호(본인확인용)", type="password")
                
                type_val = st.selectbox("구분", ["연차", "반차(오전)", "반차(오후)", "조퇴", "외출", "결근"])
                approver = st.selectbox("승인 담당자", ALL_MANAGERS)
                
                st.markdown("---")
                
                date_mode = st.radio("기간 설정", ["하루/반차/외출 (단일)", "기간 (연차/휴가)"], horizontal=True)
                final_date_str = ""
                
                if date_mode == "하루/반차/외출 (단일)":
                    st.write("**📆 일시 및 시간 선택 (단일)**")
                    dc1, dc2, dc3 = st.columns(3)
                    d_sel = dc1.date_input("날짜 선택", value=datetime.now(KST))
                    t_start = dc2.time_input("시작 시간", value=time(9,0))
                    t_end = dc3.time_input("종료 시간", value=time(18,0))
                    
                    final_date_str = f"{d_sel} {t_start.strftime('%H:%M')} ~ {t_end.strftime('%H:%M')}"
                
                else:
                    st.write("**📆 기간 선택 (연차/휴가)**")
                    dc1, dc2 = st.columns(2)
                    d_start = dc1.date_input("시작일", value=datetime.now(KST))
                    d_end = dc2.date_input("종료일", value=datetime.now(KST))
                    
                    if d_start > d_end:
                        st.error("⚠️ 종료일이 시작일보다 빠릅니다.")
                    else:
                        final_date_str = f"{d_start} ~ {d_end}"

                st.info(f"선택된 일시: {final_date_str}")
                reason = st.text_input("사유")
                
                if st.form_submit_button("신청하기"):
                    if not name or not pw:
                        st.error("이름과 비밀번호를 입력해주세요.")
                    else:
                        save_attendance(COMPANY, name, type_val, final_date_str, reason, pw, approver)
                        st.success("신청이 완료되었습니다.")
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
                    for _, r in my_df.iterrows():
                        st.info(f"{r['날짜및시간']} | {r['구분']} | {r['상태']}")
            else:
                st.error("데이터가 없습니다.")

# 5. 관리자
with tab5:
    st.subheader("⚙️ 관리자 및 조장/반장 전용")
    if 'logged_in_manager' not in st.session_state:
        user_db = load_user_db()
        selected_name = st.selectbox("관리자(조장/반장) 선택", ["선택안함"] + ALL_MANAGERS)
        if selected_name != "선택안함":
            if selected_name not in user_db:
                st.warning(f"🔒 '{selected_name}'님은 최초 접속입니다. 비밀번호를 설정해주세요.")
                with st.form("init_pw"):
                    new_pw = st.text_input("새 비밀번호", type="password")
                    chk_pw = st.text_input("비밀번호 확인", type="password")
                    if st.form_submit_button("비밀번호 등록"):
                        if new_pw == chk_pw and new_pw:
                            user_db[selected_name] = new_pw
                            save_user_db(user_db)
                            st.success("설정 완료! 다시 로그인해주세요.")
                            st.rerun()
                        else:
                            st.error("비밀번호가 일치하지 않습니다.")
            else:
                with st.form("manager_login_form"):
                    input_pw = st.text_input("비밀번호 입력", type="password")
                    if st.form_submit_button("로그인"):
                        if input_pw == user_db[selected_name]:
                            st.session_state['logged_in_manager'] = selected_name
                            st.rerun()
                        else:
                            st.error("비밀번호가 틀렸습니다.")
        
        with st.expander("시스템 최고 관리자"):
            with st.form("master_login_form"):
                master_pw = st.text_input("Master PW", type="password")
                if st.form_submit_button("Master Login"):
                    if master_pw == st.secrets["admin_password"]:
                        st.session_state['logged_in_manager'] = "MASTER"
                        st.rerun()
                    else:
                        st.error("비밀번호가 틀렸습니다.")
    else:
        manager_id = st.session_state['logged_in_manager']
        manager_name = manager_id
        c_logout, _ = st.columns([0.2, 0.8])
        if c_logout.button("로그아웃"):
            del st.session_state['logged_in_manager']
            st.rerun()
        st.success(f"👋 안녕하세요, {manager_name}님")
        m_tab1, m_tab2, m_tab3 = st.tabs(["✅ 결재 관리", "📢 공지/일정", "📊 통계"])
        with m_tab1:
            df = load_data("근태신청", COMPANY)
            if not df.empty and '상태' in df.columns:
                pend = df[df['상태'].isin(['대기중'])]
                if manager_id != "MASTER":
                    pend = pend[pend['승인자'] == manager_name]
                if pend.empty: 
                    st.info("대기중인 결재 건이 없습니다.")
                else:
                    st.write(f"총 {len(pend)}건의 대기 문서가 있습니다.")
                    for i, r in pend.iterrows():
                        with st.expander(f"[{r['이름']}] {r['구분']} - {r['날짜및시간']}"):
                            st.write(f"사유: {r['사유']}")
                            c_app, c_rej = st.columns(2)
                            if c_app.button("승인", key=f"app_{i}"):
                                update_attendance_status("근태신청", i, "최종승인")
                                st.success("승인되었습니다.")
                                st.rerun()
                            if c_rej.button("반려", key=f"rej_{i}"):
                                update_attendance_status("근태신청", i, "반려")
                                st.error("반려되었습니다.")
                                st.rerun()
            else:
                st.info("데이터가 없거나 시트 형식이 잘못되었습니다.")

        with m_tab2:
            st.write("공지사항 및 일정 등록")
            with st.form("n_form", clear_on_submit=True):
                type_sel = st.selectbox("유형", ["공지사항", "일정"])
                t = st.text_input("제목")
                c = st.text_area("내용")
                is_imp = st.checkbox("중요 공지 (상단 고정)", value=False)
                d_s = st.date_input("날짜(일정용)", value=datetime.now(KST))
                
                if st.form_submit_button("등록"):
                    if type_sel == "공지사항":
                        save_notice(COMPANY, t, c, is_imp)
                    else:
                        save_schedule(COMPANY, str(d_s), t, c, manager_name)
                    st.toast("등록되었습니다.")
        with m_tab3:
            st.write("### 📊 전사원 월별 연차 사용 현황")
            df = load_data("근태신청", COMPANY)
            if not df.empty and '상태' in df.columns:
                df = df[df['상태'].isin(['최종승인', '승인'])]
                stats_data = []
                for _, row in df.iterrows():
                    if "연차" in row['구분'] or "반차" in row['구분']:
                        use_val = 0.5 if "반차" in row['구분'] else 1.0
                        try:
                            d_str = row['날짜및시간'].split(' ')[0].split('~')[0].strip()
                            month = d_str[:7]
                            stats_data.append({"이름": row['이름'], "월": month, "사용일수": use_val})
                        except: pass
                if stats_data:
                    stat_df = pd.DataFrame(stats_data)
                    pivot = stat_df.pivot_table(index="이름", columns="월", values="사용일수", aggfunc="sum", fill_value=0)
                    st.dataframe(pivot)
                else:
                    st.info("집계할 데이터 없음")
            else:
                st.info("데이터 없음")