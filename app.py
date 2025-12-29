import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import uuid
import pytz
import holidays
from streamlit_calendar import calendar

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="제이유 사내광장", page_icon="🏢", layout="centered")

# 1단계: 현장 반장 (PW: 0001 ~ 0005)
FOREMEN = {
    "0001": "1라인 반장",
    "0002": "2라인 반장",
    "0003": "3라인 반장",
    "0004": "4라인 반장",
    "0005": "5라인 반장"
}

# 2단계: 중간 관리자 (PW: 1111 ~ 4444)
MIDDLE_MANAGERS = {
    "1111": "인사팀장",
    "2222": "생산팀장",
    "3333": "영업팀장",
    "4444": "품질팀장"
}

# --- [스타일] CSS ---
st.markdown("""
<style>
    div[data-testid="stMarkdownContainer"] p {
        font-size: 18px !important;
        line-height: 1.6 !important;
        word-break: keep-all !important;
    }
    .fc-event-title {
        font-weight: bold !important;
        font-size: 0.85em !important;
        color: white !important;
    }
    iframe[title="streamlit_calendar.calendar"] {
        height: 750px !important;
        min-height: 750px !important;
        display: block !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px !important;
        color: #FF4B4B !important;
    }
    @media (max-width: 768px) {
        h1 { font-size: 2.0rem !important; word-break: keep-all !important; }
        div.stButton > button {
            width: 100%;
            height: 3.5rem;
            font-size: 18px;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- [함수] 한국 시간 구하기 ---
def get_korea_time():
    kst = pytz.timezone('Asia/Seoul')
    return datetime.now(kst).strftime("%Y-%m-%d")

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
        df = pd.DataFrame(data)
        return df.astype(str) 
    except Exception as e:
        return pd.DataFrame()

# --- [함수] 저장/수정/삭제 로직 ---
def save_notice(title, content, is_important):
    sheet = get_worksheet("공지사항")
    sheet.append_row([get_korea_time(), title, content, "TRUE" if is_important else "FALSE"])
    st.cache_data.clear()

def save_suggestion(title, content, author, is_private, password):
    sheet = get_worksheet("건의사항")
    sheet.append_row([get_korea_time(), title, content, author, "TRUE" if is_private else "FALSE", str(password)])
    st.cache_data.clear()

def save_attendance(name, type_val, target_time, reason, password, approver):
    sheet = get_worksheet("근태신청")
    # 8번째 열에 '승인담당자(반장)' 저장
    sheet.append_row([get_korea_time(), name, type_val, target_time, reason, "대기중", str(password), approver])
    st.cache_data.clear()

def save_schedule(date_str, title, content, author):
    sheet = get_worksheet("일정관리")
    sheet.append_row([date_str, title, content, author])
    st.cache_data.clear()

def delete_row(sheet_name, row_idx):
    sheet = get_worksheet(sheet_name)
    sheet.delete_rows(row_idx + 2)
    st.cache_data.clear()

def update_notice(row_idx, date, title, content, is_important):
    sheet = get_worksheet("공지사항")
    target_row = row_idx + 2
    sheet.update(range_name=f"A{target_row}:D{target_row}", 
                 values=[[date, title, content, "TRUE" if is_important else "FALSE"]])
    st.cache_data.clear()

def update_attendance_status(row_idx, new_status):
    sheet = get_worksheet("근태신청")
    sheet.update_cell(row_idx + 2, 6, new_status)
    st.cache_data.clear()


# --- [UI] 메인 화면 ---
st.title("🏢 제이유 사내광장")

if 'show_sugg_form' not in st.session_state: st.session_state['show_sugg_form'] = False
if 'show_attend_form' not in st.session_state: st.session_state['show_attend_form'] = False
if 'calendar_key' not in st.session_state: st.session_state['calendar_key'] = str(uuid.uuid4())

def toggle_sugg(): st.session_state['show_sugg_form'] = not st.session_state['show_sugg_form']
def toggle_attend(): st.session_state['show_attend_form'] = not st.session_state['show_attend_form']

# 탭 구성
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 공지", "🗣️ 건의", "📆 근무표", "📅 근태신청", "⚙️ 관리자"])

# 1. 공지사항
with tab1:
    if st.button("🔄 공지 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    df = load_data("공지사항")
    st.markdown("---")
    if df.empty:
        st.info("공지사항이 없습니다.")
    else:
        for index, row in df.iloc[::-1].iterrows():
            is_imp = str(row.get("중요", "FALSE")).upper() == "TRUE"
            with st.container(border=True):
                if is_imp: st.markdown(f":red[**[중요] 🔥 {row['제목']}**]")
                else: st.subheader(f"📌 {row['제목']}")
                st.caption(f"📅 {row['작성일']}")
                st.markdown(f"{row['내용']}")

# 2. 건의사항
with tab2:
    st.write("### 🗣️ 자유 게시판")
    if st.button("✍️ 건의사항 작성 (터치)", on_click=toggle_sugg, use_container_width=True): pass
    
    if st.session_state['show_sugg_form']:
        with st.container(border=True):
            st.info("비밀번호는 본인 확인용입니다.")
            with st.form("suggestion_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1: author = st.text_input("작성자 (필수)", placeholder="홍길동")
                with c2: pw_input = st.text_input("비밀번호 (4자리)", type="password", max_chars=4)
                title = st.text_input("제목")
                content = st.text_area("내용", height=100)
                private = st.checkbox("🔒 비공개 (나와 관리자만 봄)")
                if st.form_submit_button("등록", use_container_width=True):
                    if not content or not author or not pw_input:
                        st.warning("작성자, 비밀번호, 내용을 모두 입력하세요.")
                    else:
                        save_suggestion(title, content, author, private, pw_input)
                        st.success("등록됨")
                        st.session_state['show_sugg_form'] = False
                        st.rerun()
    st.divider()
    search_mode = st.radio("보기 모드", ["공개 게시판 보기", "🔒 내 건의사항 조회"], horizontal=True)
    df_s = load_data("건의사항")
    if search_mode == "공개 게시판 보기":
        if not df_s.empty:
            for index, row in df_s.iloc[::-1].iterrows():
                if str(row.get("비공개", "FALSE")).upper() != "TRUE":
                    with st.container(border=True):
                        st.markdown(f"**💬 {row['제목']}**")
                        st.caption(f"👤 {row.get('작성자','익명')} | 📅 {row['작성일']}")
                        st.markdown(f"{row['내용']}")
    else:
        with st.form("my_sugg_search"):
            c1, c2 = st.columns(2)
            with c1: my_name = st.text_input("작성자 이름")
            with c2: my_pw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("조회"):
                if not df_s.empty and my_name and my_pw:
                    my_rows = df_s[(df_s['작성자'] == my_name) & (df_s['비밀번호'].astype(str) == str(my_pw))]
                    if my_rows.empty: st.error("일치하는 글이 없습니다.")
                    else:
                        st.success(f"{len(my_rows)}건이 조회되었습니다.")
                        for i, r in my_rows.iloc[::-1].iterrows():
                            with st.container(border=True):
                                st.write(f"**[{r.get('비공개')}] {r['제목']}**")
                                st.markdown(r['내용'])
                                st.caption(r['작성일'])

# 3. 근무표 (최종승인 된 건만 표시)
with tab3:
    st.write("### 📆 승인된 근무/휴가 현황")
    st.caption("최종 승인된 일정만 달력에 표시됩니다.")
    c_btn, c_view = st.columns([0.6, 0.4])
    with c_btn:
        if st.button("🔄 근무표 새로고침", key="cal_refresh", use_container_width=True):
            st.cache_data.clear()
            st.session_state['calendar_key'] = str(uuid.uuid4())
            st.rerun()
    with c_view:
        view_type = st.radio("보기", ["달력", "목록"], horizontal=True, label_visibility="collapsed", key="view_mode")

    events = []
    # [1] 공휴일
    kr_holidays = holidays.KR(years=[datetime.now().year, datetime.now().year + 1])
    for date_obj, name in kr_holidays.items():
        events.append({
            "title": f"🇰🇷 {name}", "start": str(date_obj), "end": str(date_obj),
            "color": "#FF4B4B", "allDay": True, "display": "background", "extendedProps": {"content": "대한민국 공휴일"} 
        })
        events.append({
            "title": f"{name}", "start": str(date_obj), "color": "#FF4B4B", "allDay": True, "extendedProps": {"content": "대한민국 공휴일"}
        })

    # [2] 회사 일정
    df_sch = load_data("일정관리")
    if not df_sch.empty:
        for idx, row in df_sch.iterrows():
            raw_date = row['날짜']
            start_date = raw_date
            end_date = raw_date
            if "~" in raw_date:
                try:
                    parts = raw_date.split("~")
                    start_date = parts[0].strip()
                    temp_end = parts[1].strip()
                    end_obj = datetime.strptime(temp_end, "%Y-%m-%d") + timedelta(days=1)
                    end_date = end_obj.strftime("%Y-%m-%d")
                except: pass
            events.append({
                "title": f"📢 {row['제목']}", "start": start_date, "end": end_date,
                "color": "#8A2BE2", "allDay": True, "extendedProps": {"content": row.get('내용', '')}
            })

    # [3] 근태 신청 (최종승인만 표시)
    df_cal = load_data("근태신청")
    if not df_cal.empty:
        try:
            df_cal['상태'] = df_cal['상태'].astype(str).str.strip()
            # 과거 데이터('승인')도 호환되도록 포함
            approved_df = df_cal[df_cal['상태'].isin(['최종승인', '승인'])]
            for index, row in approved_df.iterrows():
                leave_type = str(row.get('구분', '')).strip()
                if "연차" in leave_type: color = "#D9534F"
                elif "반차" in leave_type: color = "#F0AD4E"
                elif "훈련" in leave_type: color = "#5CB85C"
                else: color = "#0275D8"
                raw_date = str(row.get('날짜및시간', '')).strip()
                start_d = raw_date.split(' ')[0]
                end_d = start_d
                if "~" in raw_date:
                    try:
                        clean_range = raw_date.split('(')[0].strip()
                        parts = clean_range.split("~")
                        start_d = parts[0].strip()
                        temp_e = parts[1].strip()
                        e_obj = datetime.strptime(temp_e, "%Y-%m-%d") + timedelta(days=1)
                        end_d = e_obj.strftime("%Y-%m-%d")
                    except: pass
                if len(start_d) >= 10:
                    events.append({
                        "title": f"[{row.get('이름','')}] {leave_type}", "start": start_d, "end": end_d,
                        "color": color, "allDay": True, "extendedProps": {"content": f"사유: {row.get('사유','')}"}
                    })
        except Exception: pass

    if view_type == "달력":
        calendar_options = {
            "headerToolbar": { "left": "today prev,next", "center": "title", "right": "dayGridMonth,listMonth" },
            "initialView": "dayGridMonth", "locale": "ko", "height": 750, "contentHeight": 700, "dayMaxEvents": 3
        }
        dynamic_key = f"cal_{st.session_state['calendar_key']}_{len(events)}"
        cal_return = calendar(events=events, options=calendar_options, key=dynamic_key,
            custom_css=".fc { background-color: white; padding: 10px; border-radius: 8px; color: black; }")
        if cal_return.get("callback") == "eventClick":
            clicked_event = cal_return["eventClick"]["event"]
            st.info(f"📌 **{clicked_event['title']}**")
            st.write(f"날짜: {clicked_event['start'].split('T')[0]}")
            st.write(f"내용: {clicked_event.get('extendedProps', {}).get('content', '내용 없음')}")
    else:
        st.write("#### 📝 전체 일정 목록")
        if events:
            sorted_events = sorted(events, key=lambda x: x['start'], reverse=True)
            for e in sorted_events:
                if e.get("display") != "background":
                    with st.container(border=True):
                        st.write(f"**{e['start']}** {e['title']}")
                        st.caption(e.get("extendedProps", {}).get("content", ""))
        else: st.info("일정이 없습니다.")

# 4. 근태신청 (반장 선택 기능)
with tab4:
    st.write("### 📅 연차/근태 신청")
    if st.button("📝 근태 신청서 작성 (터치)", on_click=toggle_attend, use_container_width=True): pass
    
    if st.session_state['show_attend_form']:
        with st.container(border=True):
            st.info("비밀번호는 조회용입니다.")
            with st.form("attend_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1: name = st.text_input("이름 (필수)")
                with c2: pw_att = st.text_input("비밀번호 (확인용)", type="password")
                
                type_val = st.selectbox("구분", ["연차", "반차(오전)", "반차(오후)", "조퇴", "외출", "결근", "예비군/훈련"])
                
                # [설정] 반장 목록 드롭다운
                foreman_list = list(FOREMEN.values())
                approver = st.selectbox("승인 요청 대상 (반장 선택)", foreman_list)
                
                st.caption("💡 며칠씩 쉴 경우 '기간/시간' 칸에 '1/1~1/3' 처럼 적어주세요.")
                c3, c4 = st.columns(2)
                kst_now = datetime.now(pytz.timezone('Asia/Seoul'))
                with c3: date_val = st.date_input("시작 날짜", value=kst_now)
                with c4: time_val = st.text_input("기간/시간 (예: 1/1~1/3)")
                reason = st.text_input("사유")
                
                if st.form_submit_button("신청하기", use_container_width=True):
                    if not name or not pw_att:
                        st.warning("이름과 비밀번호는 필수입니다.")
                    else:
                        if time_val and "~" in time_val: dt = f"{time_val}" 
                        else: dt = f"{date_val} ({time_val})" if time_val else str(date_val)
                        save_attendance(name, type_val, dt, reason, pw_att, approver)
                        st.success(f"{approver}님께 승인 요청되었습니다. (대기중)")
                        st.session_state['show_attend_form'] = False
                        st.rerun()
    st.divider()
    st.write("#### 🔒 내 신청 결과 조회")
    with st.form("my_attend_search"):
        col_search1, col_search2 = st.columns([1,1])
        with col_search1: search_name = st.text_input("이름")
        with col_search2: search_pw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("내역 조회", use_container_width=True):
            df_a = load_data("근태신청")
            if df_a.empty: st.info("데이터가 없습니다.")
            elif not search_name or not search_pw: st.warning("이름과 비밀번호를 입력해주세요.")
            else:
                my_result = df_a[(df_a['이름'] == search_name) & (df_a['비밀번호'].astype(str) == str(search_pw))]
                if my_result.empty: st.error("일치하는 내역이 없습니다.")
                else:
                    st.success(f"총 {len(my_result)}건의 신청 내역이 있습니다.")
                    for idx, row in my_result.iloc[::-1].iterrows():
                        status = row.get("상태", "대기중")
                        color = "orange"
                        if status == "최종승인": color = "green"
                        elif status == "2차승인": color = "blue"
                        elif status == "1차승인": color = "violet"
                        elif status == "반려": color = "red"
                        with st.container(border=True):
                            st.markdown(f"**{row['구분']}** - :{color}[**{status}**]")
                            st.text(f"일시: {row['날짜및시간']}")
                            st.caption(f"사유: {row['사유']} | 승인자: {row.get('승인담당자','미지정')}")

# 5. 관리자
with tab5:
    st.write("🔒 관리자 전용")
    pw = st.text_input("비밀번호", type="password")
    
    # -------------------------------------------------------------
    # [A] 최고 관리자 (Super Pass 가능)
    # -------------------------------------------------------------
    if str(pw).strip() == str(st.secrets["admin_password"]).strip():
        st.success("🌟 최고 관리자 접속 (Super Pass 활성화)")
        
        df_a = load_data("근태신청")
        if not df_a.empty:
            df_a['상태'] = df_a['상태'].astype(str).str.strip()
            # [핵심] 슈퍼 패스: 대기중, 1차승인, 2차승인 모두 처리 가능
            pending_list = ['대기중', '1차승인', '2차승인']
            pending_count = len(df_a[df_a['상태'].isin(pending_list)])
            
            if pending_count > 0:
                st.metric(label="🔔 전체 결재 대기", value=f"{pending_count}건", delta="처리 필요")
            else: st.info("🔔 처리할 문서가 없습니다.")
            
        mode = st.radio("작업", ["📝 공지쓰기", "📆 일정추가(회사)", "🔧 공지관리", "🔧 건의함관리", "✅ 통합 결재 관리"])
        
        if mode == "📝 공지쓰기":
            with st.form("new_n"):
                t = st.text_input("제목")
                c = st.text_area("내용")
                i = st.checkbox("중요")
                if st.form_submit_button("등록"):
                    save_notice(t, c, i)
                    st.toast("등록됨")
        
        elif mode == "📆 일정추가(회사)":
            st.info("회사 전체 일정을 등록합니다.")
            with st.form("new_sch"):
                d_range = st.date_input("날짜 선택", value=[], min_value=datetime.today()-timedelta(days=365))
                sch_title = st.text_input("일정 제목")
                sch_content = st.text_area("상세 내용")
                if st.form_submit_button("일정 등록"):
                    if len(d_range) >= 1:
                        start_s = d_range[0].strftime("%Y-%m-%d")
                        end_s = d_range[-1].strftime("%Y-%m-%d") if len(d_range) > 1 else start_s
                        date_str = f"{start_s} ~ {end_s}" if start_s != end_s else start_s
                        save_schedule(date_str, sch_title, sch_content, "최고관리자")
                        st.success(f"{date_str} 일정 등록 완료")
                    else: st.warning("날짜를 선택하세요")
            st.markdown("---")
            df_sch = load_data("일정관리")
            if not df_sch.empty:
                del_sch = st.selectbox("삭제할 일정", [f"[{i}] {r['날짜']} : {r['제목']}" for i, r in df_sch.iterrows()])
                if st.button("삭제", type="primary"):
                    idx = int(del_sch.split(']')[0].replace('[',''))
                    delete_row("일정관리", idx)
                    st.rerun()

        elif mode == "🔧 공지관리":
            df = load_data("공지사항")
            if not df.empty:
                sel = st.selectbox("공지 선택", [f"[{i}] {r['제목']}" for i, r in df.iterrows()])
                if sel:
                    idx = int(sel.split(']')[0].replace('[',''))
                    r = df.loc[idx]
                    with st.form("edit_n"):
                        nt = st.text_input("제목", value=r['제목'])
                        nc = st.text_area("내용", value=r['내용'])
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.form_submit_button("수정"):
                                update_notice(idx, r['작성일'], nt, nc, str(r['중요'])=='TRUE')
                                st.rerun()
                        with c2:
                            if st.form_submit_button("삭제", type="primary"):
                                delete_row("공지사항", idx)
                                st.rerun()
                                
        elif mode == "🔧 건의함관리":
            df_s = load_data("건의사항")
            if not df_s.empty:
                st.dataframe(df_s)
                sel_s = st.selectbox("삭제할 건의", [f"[{i}] {r['제목']}" for i, r in df_s.iterrows()])
                if st.button("삭제하기", type="primary"):
                    delete_row("건의사항", int(sel_s.split(']')[0].replace('[','')))
                    st.rerun()

        elif mode == "✅ 통합 결재 관리":
            st.write("### 👑 슈퍼 패스 결재 (모든 단계 즉시 최종승인)")
            st.caption("대기중/1차/2차 승인 건을 즉시 '최종 승인'하여 달력에 게시합니다.")
            
            if df_a.empty: st.info("데이터가 없습니다.")
            else:
                # [핵심] 슈퍼패스 필터: 대기, 1차, 2차 모두 포함
                pending_list = ['대기중', '1차승인', '2차승인']
                final_pending = df_a[df_a['상태'].isin(pending_list)]
                
                if final_pending.empty: st.info("✅ 현재 승인 처리할 문서가 없습니다.")
                else:
                    opts = [f"[{i}] {r['이름']} ({r['구분']}) - 현재: {r['상태']}" for i, r in final_pending.iterrows()]
                    sel_a = st.selectbox("처리할 내역 선택", opts)
                    if sel_a:
                        idx_a = int(sel_a.split(']')[0].replace('[',''))
                        row_a = df_a.loc[idx_a]
                        with st.container(border=True):
                            st.info(f"👤 **{row_a['이름']}**")
                            st.write(f"일시: {row_a['날짜및시간']} | 사유: {row_a['사유']}")
                            st.caption(f"승인요청: {row_a.get('승인담당자')} | 현재상태: {row_a['상태']}")
                        c_app, c_rej = st.columns(2)
                        with c_app:
                            if st.button("👑 최종 승인 (즉시 반영)", use_container_width=True):
                                update_attendance_status(idx_a, "최종승인")
                                st.success("최종 승인 완료! 달력에 표시됩니다.")
                                st.rerun()
                        with c_rej:
                            if st.button("⛔ 반려", use_container_width=True):
                                update_attendance_status(idx_a, "반려")
                                st.warning("반려 처리됨.")
                                st.rerun()

    # -------------------------------------------------------------
    # [B] 중간 관리자 (2차 승인) - PW: 1111~4444
    # -------------------------------------------------------------
    elif str(pw).strip() in MIDDLE_MANAGERS:
        manager_name = MIDDLE_MANAGERS[str(pw).strip()]
        st.success(f"👔 {manager_name}님 접속 (중간 관리자)")
        
        df_a = load_data("근태신청")
        if not df_a.empty:
            df_a['상태'] = df_a['상태'].astype(str).str.strip()
            # 중간 관리자는 '1차승인' 된 것만 처리 가능
            mid_pending = df_a[df_a['상태'] == '1차승인']
            
            if len(mid_pending) > 0:
                st.metric(label="🔔 2차 승인 대기", value=f"{len(mid_pending)}건", delta="결재 필요")
            else: st.info("🔔 처리할 대기 문서가 없습니다.")
            
            if not mid_pending.empty:
                opts = [f"[{i}] {r['이름']} ({r['구분']})" for i, r in mid_pending.iterrows()]
                sel_a = st.selectbox("처리할 내역 선택", opts)
                if sel_a:
                    idx_a = int(sel_a.split(']')[0].replace('[',''))
                    row_a = df_a.loc[idx_a]
                    with st.container(border=True):
                        st.info(f"신청자: **{row_a['이름']}**")
                        st.write(f"일시: {row_a['날짜및시간']} | 사유: {row_a['사유']}")
                        st.caption(f"1차승인 완료됨. (승인요청: {row_a.get('승인담당자')})")
                    c_app, c_rej = st.columns(2)
                    with c_app:
                        if st.button("✅ 2차 승인", use_container_width=True):
                            update_attendance_status(idx_a, "2차승인")
                            st.success("2차 승인 완료. 최고 관리자에게 넘어갑니다.")
                            st.rerun()
                    with c_rej:
                        if st.button("⛔ 반려", use_container_width=True):
                            update_attendance_status(idx_a, "반려")
                            st.rerun()

    # -------------------------------------------------------------
    # [C] 반장 (1차 승인) - PW: 0001~0005
    # -------------------------------------------------------------
    elif str(pw).strip() in FOREMEN:
        foreman_name = FOREMEN[str(pw).strip()]
        st.success(f"⛑️ {foreman_name}님 접속 (반장)")
        
        df_a = load_data("근태신청")
        if not df_a.empty:
            df_a['상태'] = df_a['상태'].astype(str).str.strip()
            df_a['승인담당자'] = df_a.get('승인담당자', '').astype(str).str.strip()
            
            # 반장은 본인 앞으로 온 '대기중' 건만 처리 가능
            my_pending = df_a[ (df_a['상태'] == '대기중') & (df_a['승인담당자'] == foreman_name) ]
            
            if len(my_pending) > 0:
                st.metric(label="🔔 1차 승인 대기", value=f"{len(my_pending)}건", delta="결재 필요")
            else: 
                st.info(f"🔔 {foreman_name}님 앞으로 온 결재 요청이 없습니다.")
            
            if not my_pending.empty:
                opts = [f"[{i}] {r['이름']} ({r['구분']})" for i, r in my_pending.iterrows()]
                sel_a = st.selectbox("처리할 내역 선택", opts)
                if sel_a:
                    idx_a = int(sel_a.split(']')[0].replace('[',''))
                    row_a = df_a.loc[idx_a]
                    with st.container(border=True):
                        st.info(f"신청자: **{row_a['이름']}**")
                        st.write(f"일시: {row_a['날짜및시간']} | 사유: {row_a['사유']}")
                    c_app, c_rej = st.columns(2)
                    with c_app:
                        if st.button("✅ 1차 승인", use_container_width=True):
                            update_attendance_status(idx_a, "1차승인")
                            st.success("1차 승인 완료. 중간 관리자에게 넘어갑니다.")
                            st.rerun()
                    with c_rej:
                        if st.button("⛔ 반려", use_container_width=True):
                            update_attendance_status(idx_a, "반려")
                            st.rerun()

    elif pw:
        st.error("비밀번호 불일치")