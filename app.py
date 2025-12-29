import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta # 날짜 계산용 추가
import uuid
import pytz
import holidays
from streamlit_calendar import calendar

# --- [설정] 페이지 기본 UI 설정 ---
st.set_page_config(page_title="제이유 사내광장", page_icon="🏢", layout="centered")

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
    .fc-toolbar-title {
        font-size: 1.2em !important;
    }
    /* 모바일 달력 높이 강제 고정 및 렌더링 보정 */
    @media (max-width: 768px) {
        h1 { font-size: 2.0rem !important; word-break: keep-all !important; }
        div.stButton > button {
            width: 100%;
            height: 3.5rem;
            font-size: 18px;
        }
        iframe[title="streamlit_calendar.calendar"] {
            min-height: 600px !important;
            height: 600px !important;
            display: block !important;
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

def save_attendance(name, type_val, target_time, reason, password):
    sheet = get_worksheet("근태신청")
    sheet.append_row([get_korea_time(), name, type_val, target_time, reason, "대기중", str(password)])
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
# [중요] 캘린더 리렌더링을 위한 고유 키 관리
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
                    if my_rows.empty:
                        st.error("일치하는 글이 없습니다.")
                    else:
                        st.success(f"{len(my_rows)}건이 조회되었습니다.")
                        for i, r in my_rows.iloc[::-1].iterrows():
                            with st.container(border=True):
                                st.write(f"**[{r.get('비공개')}] {r['제목']}**")
                                st.markdown(r['내용'])
                                st.caption(r['작성일'])

# 3. 근무표
with tab3:
    st.write("### 📆 승인된 근무/휴가 현황")
    st.caption("공휴일, 회사일정, 승인된 연차가 표시됩니다.")
    
    c_btn, c_view = st.columns([0.6, 0.4])
    with c_btn:
        if st.button("🔄 근무표 새로고침", key="cal_refresh", use_container_width=True):
            st.cache_data.clear()
            # 새로고침 시 키 값을 변경하여 강제 리렌더링 유도
            st.session_state['calendar_key'] = str(uuid.uuid4())
            st.rerun()
    with c_view:
        view_type = st.radio("보기", ["달력", "목록"], horizontal=True, label_visibility="collapsed", key="view_mode")

    events = []
    
    # [1] 공휴일 추가
    kr_holidays = holidays.KR(years=[datetime.now().year, datetime.now().year + 1])
    for date_obj, name in kr_holidays.items():
        events.append({
            "title": f"🇰🇷 {name}",
            "start": str(date_obj),
            "end": str(date_obj),
            "color": "#FF4B4B",
            "allDay": True,
            "display": "background",
            "extendedProps": {"content": "대한민국 공휴일"} 
        })
        events.append({
            "title": f"{name}",
            "start": str(date_obj),
            "color": "#FF4B4B",
            "allDay": True,
             "extendedProps": {"content": "대한민국 공휴일"}
        })

    # [2] 회사 일정 (기간 처리 로직 추가됨)
    df_sch = load_data("일정관리")
    if not df_sch.empty:
        for idx, row in df_sch.iterrows():
            raw_date = row['날짜']
            start_date = raw_date
            end_date = raw_date
            
            # "~" 가 있으면 기간으로 인식 (예: 2025-01-01 ~ 2025-01-03)
            if "~" in raw_date:
                try:
                    parts = raw_date.split("~")
                    start_date = parts[0].strip()
                    temp_end = parts[1].strip()
                    
                    # [중요] 달력 라이브러리는 종료일 00:00까지를 의미하므로, 
                    # 3일까지 꽉 채워 보여주려면 4일 00:00으로 설정해야 함 (+1일)
                    end_obj = datetime.strptime(temp_end, "%Y-%m-%d") + timedelta(days=1)
                    end_date = end_obj.strftime("%Y-%m-%d")
                except:
                    start_date = raw_date # 에러나면 그냥 원래 값 사용

            events.append({
                "title": f"📢 {row['제목']}",
                "start": start_date,
                "end": end_date, # 종료일 추가
                "color": "#8A2BE2", 
                "allDay": True,
                "extendedProps": {"content": row.get('내용', '')}
            })

    # [3] 근태 신청
    df_cal = load_data("근태신청")
    if not df_cal.empty:
        try:
            df_cal['상태'] = df_cal['상태'].astype(str).str.strip()
            approved_df = df_cal[df_cal['상태'] == '승인']
            
            for index, row in approved_df.iterrows():
                leave_type = str(row.get('구분', '')).strip()
                if "연차" in leave_type: color = "#D9534F"
                elif "반차" in leave_type: color = "#F0AD4E"
                elif "훈련" in leave_type: color = "#5CB85C"
                else: color = "#0275D8"

                raw_date = str(row.get('날짜및시간', '')).strip()
                
                # 근태도 기간(~로 구분)일 경우 처리
                start_d = raw_date.split(' ')[0] # 기본값
                end_d = raw_date.split(' ')[0]
                
                if "~" in raw_date:
                    try:
                        # "2025-01-01 ~ 2025-01-03 (휴가)" 형태일 수 있음
                        clean_range = raw_date.split('(')[0] # 괄호 뒤 날리기
                        parts = clean_range.split("~")
                        start_d = parts[0].strip()
                        temp_e = parts[1].strip()
                        e_obj = datetime.strptime(temp_e, "%Y-%m-%d") + timedelta(days=1)
                        end_d = e_obj.strftime("%Y-%m-%d")
                    except:
                        pass

                if len(start_d) >= 10:
                    events.append({
                        "title": f"[{row.get('이름','')}] {leave_type}",
                        "start": start_d,
                        "end": end_d,
                        "color": color,
                        "allDay": True,
                        "extendedProps": {"content": f"사유: {row.get('사유','')}"}
                    })
        except Exception:
            pass

    if view_type == "달력":
        calendar_options = {
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "dayGridMonth,listMonth"
            },
            "initialView": "dayGridMonth",
            "locale": "ko",
            "height": "750px", 
            "contentHeight": "auto",
            "dayMaxEvents": 3 
        }
        
        # [핵심] 키값에 데이터 길이와 랜덤값을 섞어 화면 갱신 보장
        dynamic_key = f"cal_{st.session_state['calendar_key']}_{len(events)}"
        
        cal_return = calendar(
            events=events,
            options=calendar_options,
            key=dynamic_key,
            custom_css="""
            .fc { background-color: white; padding: 10px; border-radius: 8px; color: black; }
            """
        )
        
        if cal_return.get("callback") == "eventClick":
            clicked_event = cal_return["eventClick"]["event"]
            title = clicked_event["title"]
            date_info = clicked_event["start"].split("T")[0]
            content = clicked_event.get("extendedProps", {}).get("content", "내용 없음")
            
            st.info(f"📌 **{title}**")
            st.write(f"일시: {date_info}")
            st.write(f"내용: {content}")
            
    else:
        st.write("#### 📝 전체 일정 목록")
        if events:
            sorted_events = sorted(events, key=lambda x: x['start'], reverse=True)
            for e in sorted_events:
                if e.get("display") != "background":
                    with st.container(border=True):
                        st.write(f"**{e['start']}** {e['title']}")
                        st.caption(e.get("extendedProps", {}).get("content", ""))
        else:
            st.info("일정이 없습니다.")


# 4. 근태신청
with tab4:
    st.write("### 📅 연차/근태 신청")
    
    if st.button("📝 근태 신청서 작성 (터치)", on_click=toggle_attend, use_container_width=True): pass
    
    if st.session_state['show_attend_form']:
        with st.container(border=True):
            st.info("결과 조회를 위해 비밀번호를 꼭 기억하세요.")
            with st.form("attend_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1: name = st.text_input("이름 (필수)")
                with c2: pw_att = st.text_input("비밀번호 (확인용)", type="password")
                
                type_val = st.selectbox("구분", ["연차", "반차(오전)", "반차(오후)", "조퇴", "외출", "결근", "예비군/훈련"])
                
                c3, c4 = st.columns(2)
                kst_now = datetime.now(pytz.timezone('Asia/Seoul'))
                # [수정] 여기도 기간 선택 가능하게 변경 (하지만 단순화를 위해 단일 날짜 유지 또는 문자열로 받음)
                # 여기서는 '하루' 신청이 기본이지만 사용자가 텍스트로 쓸 수 있게 안내
                with c3: date_val = st.date_input("시작 날짜", value=kst_now)
                with c4: time_val = st.text_input("기간/시간 (예: 1/1~1/3, 14시~16시)")
                reason = st.text_input("사유")
                
                if st.form_submit_button("신청하기", use_container_width=True):
                    if not name or not pw_att:
                        st.warning("이름과 비밀번호는 필수입니다.")
                    else:
                        # 날짜와 기간 정보를 합쳐서 저장 (달력 로직에서 파싱 가능하도록)
                        if time_val and "~" in time_val and "시" not in time_val:
                            # 사용자가 기간을 직접 입력한 경우 (예: 2025-01-01 ~ 2025-01-05)
                             dt = f"{time_val}" 
                        else:
                             dt = f"{date_val} ({time_val})" if time_val else str(date_val)
                        
                        save_attendance(name, type_val, dt, reason, pw_att)
                        st.success("신청되었습니다.")
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
            if df_a.empty:
                st.info("데이터가 없습니다.")
            elif not search_name or not search_pw:
                st.warning("이름과 비밀번호를 입력해주세요.")
            else:
                my_result = df_a[(df_a['이름'] == search_name) & (df_a['비밀번호'].astype(str) == str(search_pw))]
                if my_result.empty:
                    st.error("일치하는 내역이 없습니다.")
                else:
                    st.success(f"총 {len(my_result)}건의 신청 내역이 있습니다.")
                    for idx, row in my_result.iloc[::-1].iterrows():
                        status = row.get("상태", "대기중")
                        color = "orange"
                        if status == "승인": color = "green"
                        elif status == "반려": color = "red"
                        with st.container(border=True):
                            st.markdown(f"**{row['구분']}** - :{color}[**{status}**]")
                            st.text(f"일시: {row['날짜및시간']}")
                            st.caption(f"사유: {row['사유']} (신청일: {row['신청일']})")

# 5. 관리자
with tab5:
    st.write("🔒 관리자 전용")
    pw = st.text_input("비밀번호", type="password")
    
    if str(pw).strip() == str(st.secrets["admin_password"]).strip():
        st.success("관리자 접속 성공")
        mode = st.radio("작업", ["📝 공지쓰기", "📆 일정추가(회사)", "🔧 공지관리", "🔧 건의함관리", "✅ 근태승인/관리"])
        
        if mode == "📝 공지쓰기":
            with st.form("new_n"):
                t = st.text_input("제목")
                c = st.text_area("내용")
                i = st.checkbox("중요")
                if st.form_submit_button("등록"):
                    save_notice(t, c, i)
                    st.toast("등록됨")
        
        # [수정] 일정 추가 시 '기간 선택' 가능하도록 변경
        elif mode == "📆 일정추가(회사)":
            st.info("달력에 표시될 회사 전체 일정을 등록합니다.")
            with st.form("new_sch"):
                # [핵심] 날짜 범위를 선택하도록 변경 (value=[] 빈 리스트 주면 선택 전까지 비어있음)
                d_range = st.date_input(
                    "날짜 선택 (시작일과 종료일을 클릭하세요)", 
                    value=[],
                    min_value=datetime.today() - timedelta(days=365),
                    max_value=datetime.today() + timedelta(days=365)
                )
                sch_title = st.text_input("일정 제목 (예: 전체 회식)")
                sch_content = st.text_area("상세 내용")
                
                if st.form_submit_button("일정 등록"):
                    if len(d_range) == 2:
                        # 시작일 ~ 종료일
                        start_s = d_range[0].strftime("%Y-%m-%d")
                        end_s = d_range[1].strftime("%Y-%m-%d")
                        date_str = f"{start_s} ~ {end_s}"
                        save_schedule(date_str, sch_title, sch_content, "관리자")
                        st.success(f"{date_str} 일정이 등록되었습니다.")
                    elif len(d_range) == 1:
                        # 하루짜리
                        date_str = d_range[0].strftime("%Y-%m-%d")
                        save_schedule(date_str, sch_title, sch_content, "관리자")
                        st.success("일정이 등록되었습니다.")
                    else:
                        st.warning("날짜를 선택해주세요.")

            st.markdown("---")
            st.write("🗑️ **등록된 일정 삭제**")
            df_sch = load_data("일정관리")
            if not df_sch.empty:
                del_sch = st.selectbox("삭제할 일정 선택", [f"[{i}] {r['날짜']} : {r['제목']}" for i, r in df_sch.iterrows()])
                if st.button("선택한 일정 삭제", type="primary"):
                    idx = int(del_sch.split(']')[0].replace('[',''))
                    delete_row("일정관리", idx)
                    st.rerun()
            else:
                st.caption("등록된 일정이 없습니다.")

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

        elif mode == "✅ 근태승인/관리":
            st.write("### ⚡ 근태 신청 처리")
            df_a = load_data("근태신청")
            
            if df_a.empty:
                st.info("데이터가 없습니다.")
            else:
                df_a['상태'] = df_a['상태'].astype(str).str.strip()
                pending_df = df_a[df_a['상태'] == '대기중']
                
                if pending_df.empty:
                    st.info("✅ 현재 처리할 대기 문서가 없습니다.")
                else:
                    st.warning(f"처리가 필요한 건이 {len(pending_df)}개 있습니다.")
                    
                    opts = [f"[{i}] {r['이름']} ({r['구분']})" for i, r in pending_df.iterrows()]
                    sel_a = st.selectbox("처리할 내역 선택", opts)
                    
                    if sel_a:
                        idx_a = int(sel_a.split(']')[0].replace('[',''))
                        row_a = df_a.loc[idx_a]
                        
                        with st.container(border=True):
                            st.info(f"👤 **{row_a['이름']}**님의 신청서")
                            st.write(f"일시: {row_a['날짜및시간']}")
                            st.write(f"사유: {row_a['사유']}")
                            st.caption(f"비밀번호: {row_a.get('비밀번호', '없음')}")
                        
                        c_app, c_rej, c_del = st.columns(3)
                        with c_app:
                            if st.button("✅ 승인", use_container_width=True):
                                update_attendance_status(idx_a, "승인")
                                st.success("승인됨.")
                                st.rerun()
                        with c_rej:
                            if st.button("⛔ 반려", use_container_width=True):
                                update_attendance_status(idx_a, "반려")
                                st.warning("반려됨.")
                                st.rerun()
                        with c_del:
                            if st.button("🗑️ 영구 삭제", type="primary", use_container_width=True):
                                delete_row("근태신청", idx_a)
                                st.error("데이터가 삭제되었습니다.")
                                st.rerun()

    elif pw:
        st.error("비밀번호 불일치")