import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time, timedelta
import uuid
import pytz
import holidays
from streamlit_calendar import calendar
import time

# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="제이유 사내광장",
    page_icon="🏢",
    layout="centered"
)

main_container = st.empty()
KST = pytz.timezone("Asia/Seoul")

# =========================================================
# 🔒 모바일 아이콘 깨짐 완전 해결 CSS
# =========================================================
st.markdown("""
<style>
/* ===== Material Icons 복구 (모바일 핵심) ===== */
.material-icons,
span.material-icons,
[data-testid="stIcon"] {
    font-family: 'Material Icons' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 24px;
    display: inline-block;
    line-height: 1;
    text-transform: none;
    letter-spacing: normal;
    white-space: nowrap;
    direction: ltr;
}

/* ===== Markdown 텍스트만 스타일 적용 (아이콘 보호) ===== */
div[data-testid="stMarkdownContainer"] > p {
    font-size: 18px;
    line-height: 1.6;
}

/* ===== 버튼 ===== */
div.stButton > button {
    width: 100%;
    background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
    color: white !important;
    border: none;
    border-radius: 12px;
    padding: 0.55rem 1rem;
    font-weight: bold;
    transition: all 0.25s ease;
    box-shadow: 0 4px 6px rgba(0,0,0,0.15);
}

div.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 14px rgba(0,0,0,0.25);
}

/* ===== 입력창 ===== */
.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] {
    border-radius: 10px;
}

/* ===== 캘린더 ===== */
iframe[title="streamlit_calendar.calendar"] {
    height: 750px !important;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# 회사 / 관리자 설정
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
# 구글 시트 연결
# =========================================================
def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

def get_worksheet(name):
    return get_client().open("사내공지사항DB").worksheet(name)

# =========================================================
# 유틸
# =========================================================
def get_today():
    return datetime.now(KST).strftime("%Y-%m-%d")

@st.cache_data(ttl=300)
def load_data(sheet, company):
    try:
        ws = get_worksheet(sheet)
        df = pd.DataFrame(ws.get_all_records()).astype(str)
        if "소속" in df.columns:
            df = df[df["소속"] == company]
        return df
    except:
        return pd.DataFrame()

# =========================================================
# 로그인
# =========================================================
if "company" not in st.session_state:
    with main_container.container():
        st.title("🏢 제이유 그룹 인트라넷")
        with st.form("login"):
            code = st.text_input("회사 접속 코드", type="password")
            if st.form_submit_button("로그인"):
                if code in COMPANIES:
                    st.session_state.company = COMPANIES[code]
                    st.session_state.calendar_key = str(uuid.uuid4())
                    st.rerun()
                else:
                    st.error("잘못된 접속 코드입니다.")
    st.stop()

COMPANY = st.session_state.company

# =========================================================
# 사이드바
# =========================================================
st.sidebar.title(f"📍 {COMPANY}")
if st.sidebar.button("로그아웃"):
    st.session_state.clear()
    st.rerun()

# =========================================================
# 메인 UI
# =========================================================
with main_container.container():
    st.title(f"🏢 {COMPANY} 사내광장")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 공지", "🗣️ 제안", "📆 근무표", "📅 근태신청", "⚙️ 관리자"]
    )

    # -----------------------------------------------------
    # 1. 공지
    # -----------------------------------------------------
    with tab1:
        df = load_data("공지사항", COMPANY)
        if df.empty:
            st.info("공지사항이 없습니다.")
        else:
            for _, r in df.iloc[::-1].iterrows():
                with st.container(border=True):
                    st.subheader(r["제목"])
                    st.caption(r["작성일"])
                    st.write(r["내용"])

    # -----------------------------------------------------
    # 2. 제안
    # -----------------------------------------------------
    with tab2:
        with st.form("suggest"):
            name = st.text_input("작성자")
            pw = st.text_input("비밀번호", type="password")
            title = st.text_input("제목")
            content = st.text_area("내용")
            if st.form_submit_button("등록"):
                ws = get_worksheet("건의사항")
                ws.append_row([COMPANY, get_today(), title, content, name, "FALSE", pw])
                st.success("등록 완료")
                time.sleep(1)
                st.rerun()

    # -----------------------------------------------------
    # 3. 근무표
    # -----------------------------------------------------
    with tab3:
        events = []
        df = load_data("근태신청", COMPANY)
        if not df.empty:
            for _, r in df[df["상태"] == "최종승인"].iterrows():
                events.append({
                    "title": f"[{r['이름']}] {r['구분']}",
                    "start": r["날짜및시간"][:10]
                })
        calendar(events=events, key=st.session_state.calendar_key)

    # -----------------------------------------------------
    # 4. 근태신청
    # -----------------------------------------------------
    with tab4:
        with st.form("attend"):
            name = st.text_input("이름")
            pw = st.text_input("비밀번호", type="password")
            t = st.selectbox("구분", ["연차", "반차", "외출", "조퇴"])
            reason = st.text_input("사유")
            if st.form_submit_button("신청"):
                ws = get_worksheet("근태신청")
                ws.append_row([
                    COMPANY, get_today(), name, t,
                    get_today(), reason, "1차승인대기", pw, ""
                ])
                st.success("신청 완료")
                time.sleep(1)
                st.rerun()

    # -----------------------------------------------------
    # 5. 관리자
    # -----------------------------------------------------
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
                                st.success("설정 완료! 1초 뒤 로그인됩니다.")
                                time.sleep(1); st.rerun()
                            else: st.error("비밀번호가 일치하지 않습니다.")
                else:
                    with st.form("manager_login_form"):
                        input_pw = st.text_input("비밀번호 입력", type="password")
                        if st.form_submit_button("로그인"):
                            if str(input_pw) == str(user_db[selected_name]):
                                st.session_state['logged_in_manager'] = selected_name; st.rerun()
                            else: st.error("비밀번호가 틀렸습니다.")
            with st.expander("시스템 최고 관리자"):
                with st.form("master_login_form"):
                    master_pw = st.text_input("Master PW", type="password")
                    if st.form_submit_button("Master Login"):
                        if master_pw == st.secrets["admin_password"]:
                            st.session_state['logged_in_manager'] = "MASTER"; st.rerun()
                        else: st.error("비밀번호가 틀렸습니다.")
        else:
            manager_id = st.session_state['logged_in_manager']
            manager_name = manager_id
            c_logout, _ = st.columns([0.2, 0.8])
            if c_logout.button("로그아웃"):
                del st.session_state['logged_in_manager']; st.rerun()
            st.success(f"👋 안녕하세요, {manager_name}님")
            
            if manager_id == "MASTER":
                with st.expander("🔐 관리자 비밀번호 초기화 (마스터 기능)"):
                    user_db = load_user_db()
                    registered_users = [u for u in user_db.keys() if u != "MASTER"]
                    if not registered_users: st.info("초기화할 계정이 없습니다.")
                    else:
                        target = st.selectbox("초기화할 관리자 선택", ["선택안함"] + registered_users)
                        if target != "선택안함":
                            if st.button(f"'{target}' 비밀번호 삭제"):
                                del user_db[target]; save_user_db(user_db)
                                st.success(f"✅ {target}님의 비밀번호가 초기화되었습니다.")
                                time.sleep(1); st.rerun()

            m_tab1, m_tab2, m_tab3 = st.tabs(["✅ 결재 관리", "📢 공지/일정", "📊 통계"])
            with m_tab1:
                df = load_data("근태신청", COMPANY)
                if not df.empty and '상태' in df.columns:
                    pend = pd.DataFrame()
                    if manager_id == "MASTER":
                        pend = df[df['상태'] == '최종승인대기']
                        st.info("📢 최종 승인 대기중인 건입니다.")
                    elif manager_id == "반장":
                        pend = df[df['상태'] == '2차승인대기']
                        st.info("📢 중간(반장) 승인 대기중인 건입니다.")
                    else:
                        pend = df[(df['상태'] == '1차승인대기') & (df['승인담당자'] == manager_name)]
                        st.info("📢 1차(조장) 승인 대기중인 건입니다.")

                    if pend.empty: st.info("현재 대기중인 결재 건이 없습니다.")
                    else:
                        st.write(f"총 {len(pend)}건의 문서가 있습니다.")
                        for i, r in pend.iterrows():
                            with st.expander(f"[{r['이름']}] {r['구분']} - {r['날짜및시간']}"):
                                st.write(f"사유: {r['사유']}")
                                c_app, c_rej = st.columns(2)
                                if c_app.button("승인", key=f"app_{i}"):
                                    if manager_id == "MASTER": 
                                        update_attendance_step("근태신청", i, "최종승인")
                                        st.success("✅ 최종 승인 처리되었습니다.")
                                    elif manager_id == "반장": 
                                        update_attendance_step("근태신청", i, "최종승인대기", "MASTER")
                                        st.success("✅ 승인 완료! 최종관리자에게 넘어갑니다.")
                                    else: 
                                        update_attendance_step("근태신청", i, "2차승인대기", "반장")
                                        st.success("✅ 승인 완료! 반장에게 넘어갑니다.")
                                    time.sleep(1); st.rerun()
                                if c_rej.button("반려", key=f"rej_{i}"):
                                    update_attendance_step("근태신청", i, "반려")
                                    st.error("⛔ 반려 처리되었습니다.")
                                    time.sleep(1); st.rerun()
                else: st.info("데이터가 없습니다.")

            with m_tab2:
                st.write("공지사항 및 일정 등록")
                with st.form("n_form", clear_on_submit=True):
                    type_sel = st.selectbox("유형", ["공지사항", "일정"])
                    t = st.text_input("제목")
                    c = st.text_area("내용")
                    is_imp = st.checkbox("중요 공지 (상단 고정)", value=False)
                    d_s = st.date_input("날짜(일정용)", value=datetime.now(KST))
                    if st.form_submit_button("등록"):
                        if type_sel == "공지사항": save_notice(COMPANY, t, c, is_imp)
                        else: save_schedule(COMPANY, str(d_s), t, c, manager_name)
                        st.success("✅ 내용이 등록되었습니다.")
                        time.sleep(1); st.rerun()
            with m_tab3:
                st.write("### 📊 전사원 월별 연차 사용 현황")
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
                    else: st.info("집계할 데이터 없음")
                else: st.info("데이터 없음")