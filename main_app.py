# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
# --- [수정] tkinter 기본 'simpledialog' import ---
from tkinter import simpledialog
import threading
from queue import Queue, Empty
import time 
from datetime import datetime
import json 

# 모듈 import
from gemini_processor import configure_gemini, get_summary_from_gemini 
from websocket_server import start_server_thread
from window_utils import close_window_by_title, activate_window_by_title
from ui_components import ScrollableTab
from session_utils import save_session, load_sessions, overwrite_sessions
from program_mapper import launch_program_by_title

# -------------------------------------------------------------------
# (큐 정의... 동일)
# -------------------------------------------------------------------
ui_queue = Queue()
command_queue = Queue()
job_queue = Queue()

# --- [신규] 선택 항목 저장을 위한 전역 상태 변수 ---
selected_items_set = set()
global_last_raw_tabs_data = []
global_last_raw_windows = []
# --- [신규 끝] ---

# -------------------------------------------------------------------
# (AI 작업자 스레드... 동일)
# -------------------------------------------------------------------
def ai_worker_thread(job_q, ui_q):
    DEBOUNCE_SECONDS = 15 
    while True:
        try:
            job_data = job_q.get() 
            print("[DEBUG] AI 작업자: 새 작업 감지. 15초 디바운스 시작...")
            time.sleep(DEBOUNCE_SECONDS)
            try:
                while True:
                    job_data = job_q.get_nowait()
                    print("[DEBUG] AI 작업자: 중간 작업 건너뜀...")
            except Empty:
                pass 
            
            print("[DEBUG] AI 작업자: 15초 경과. '마지막' 작업으로 AI 호출 시작...")
            
            tabs_data_with_url = job_data['raw_tabs_data']
            windows_titles = job_data['raw_windows']
            titles_for_ai = [tab['title'] for tab in tabs_data_with_url]
            
            ai_summary_json = get_summary_from_gemini(
                titles_for_ai, 
                windows_titles
            )
            
            ai_data_for_ui = {
                'type': 'ai_update', 
                'ai_summary': ai_summary_json,
                'raw_tabs_data': tabs_data_with_url, 
                'raw_windows': windows_titles
            }
            ui_q.put(ai_data_for_ui)
            print("[DEBUG] AI 작업자: 작업 완료. UI 큐에 'AI 결과' 전송.")
        except Exception as e:
            print(f"AI 작업자(Worker) 스레드 오류: {e}")

# -------------------------------------------------------------------
# (항목 클릭 함수)
# -------------------------------------------------------------------
def on_item_click(title, raw_windows):
    """(항목 활성화/이동 콜백 - 수정 없음)"""
    print(f"'{title}' 항목 클릭됨 (이동 요청)")
    if title in raw_windows:
        success = activate_window_by_title(title)
        if not success:
            print("창 활성화 실패 (이미 닫혔거나 권한 부족)")
    else:
        command_queue.put({ "action": "activate_tab", "title": title })

def on_close_item_click(title):
    """(개별 닫기 콜백 - 수정 없음)"""
    print(f"'{title}' 항목 닫기 요청...")
    close_window_by_title(title)
    command_queue.put({ "action": "close_tab", "title": title })

def on_close_group_click(items_list):
    """(그룹 닫기 콜백 - 수정 없음)"""
    print(f"'{len(items_list)}'개 항목의 그룹 전체 닫기 요청...")
    if not items_list: return
    for title in items_list:
        on_close_item_click(title)

def on_save_group_click(group_data):
    """(그룹 저장 콜백 - 수정 없음)"""
    category = group_data.get('category', '알 수 없음')
    print(f"'{category}' 그룹 저장 요청 (URL 포함)...")
    success = save_session(group_data)
    if success:
        print(f"'{category}' 그룹 저장 완료. '저장된 탭' 갱신을 요청합니다.")
        ui_queue.put({'type': 'refresh_saved_tab'})
    else:
        print(f"'{category}' 그룹 저장 실패.")

def on_restore_group_click(items_data):
    """(그룹 복원 콜백 - 수정 없음)"""
    print(f"'{len(items_data)}'개 항목의 그룹 복원 요청...")
    if not items_data: return
    count = 0
    for item in items_data:
        if on_restore_item_click(item, is_group_call=True):
             count += 1
    print(f"총 {count}개의 항목 (탭/프로그램) 복원 명령을 전송/실행했습니다.")


def on_restore_item_click(item_data, is_group_call=False):
    """(개별 복원 콜백 - 수정 없음)"""
    if not is_group_call:
        print(f"[개별 복원] 요청...")
    if isinstance(item_data, dict): 
        item_type = item_data.get('type')
        if item_type == 'tab' and item_data.get('url'):
            url_to_open = item_data.get('url')
            if not is_group_call: print(f"  -> [탭 복원] {url_to_open}")
            command_queue.put({"action": "open_tab", "url": url_to_open})
            return True
        elif item_type == 'window' and item_data.get('title'):
            title = item_data.get('title')
            return launch_program_by_title(title)
        else:
            if not is_group_call: print("  -> [복원 불가] 알 수 없는 데이터 타입입니다.")
            return False
    else:
        if not is_group_call: print(f"  -> [복원 불가] '{item_data}' (URL/타입 정보가 없는 구 버전 데이터, 건너뜀)")
        return False

def on_delete_group_click(group_to_delete):
    """(그룹 삭제 콜백 - 수정 없음)"""
    category = group_to_delete.get('category', '알 수 없음')
    saved_at_id = group_to_delete.get('saved_at') 
    if not saved_at_id:
        print(f"'{category}' 그룹 삭제 실패: 고유 ID(saved_at)가 없습니다.")
        return
    print(f"'{category}' ({saved_at_id}) 그룹 삭제 요청...")
    all_sessions = load_sessions()
    filtered_sessions = [
        session for session in all_sessions 
        if session.get('saved_at') != saved_at_id
    ]
    if len(filtered_sessions) < len(all_sessions):
        success = overwrite_sessions(filtered_sessions)
        if success:
            print("그룹 삭제 완료. 탭을 갱신합니다.")
            ui_queue.put({'type': 'refresh_saved_tab'})
        else:
            print("파일 덮어쓰기에 실패하여 삭제를 중단합니다.")
    else:
        print("삭제할 그룹을 찾지 못했습니다.")

# --- [신규 기능] 체크박스 클릭 시 호출 ---
def on_item_check(item_title, var):
    """(신규) 체크박스 상태가 변경되면 전역 'selected_items_set'을 업데이트합니다."""
    if var.get():
        selected_items_set.add(item_title)
        print(f"[선택] '{item_title}' 추가 (총 {len(selected_items_set)}개)")
    else:
        if item_title in selected_items_set:
            selected_items_set.remove(item_title)
            print(f"[선택] '{item_title}' 제거 (총 {len(selected_items_set)}개)")

# --- [수정] '선택 항목 저장' 버튼 클릭 시 (root 인자 받도록 수정) ---
def on_save_selected_click(root):
    """(신규) 'selected_items_set'에 저장된 항목들을 새 그룹으로 저장합니다."""
    global selected_items_set, global_last_raw_tabs_data, global_last_raw_windows
    
    if not selected_items_set:
        print("[선택 저장] 저장할 항목이 없습니다.")
        return

    print(f"[선택 저장] {len(selected_items_set)}개 항목 저장 시작...")

    # 1. 사용자에게 그룹 이름 입력받기 (팝업)
    # --- [수정] tkinter 'simpledialog' 사용 ---
    group_name = simpledialog.askstring(
        "그룹 이름 입력", 
        "저장할 그룹의 이름을 입력하세요:",
        initialvalue="새로 저장한 그룹",
        parent=root # 팝업이 메인창 위에 뜨도록 설정
    )
    # --- [수정 끝] ---
    
    if not group_name:
        print("[선택 저장] 사용자가 취소했습니다.")
        return

    # 2. 'hydrated' (URL/Type 포함) 데이터 생성
    hydrated_items_list = []
    # 최신 URL 정보가 담긴 '룩업' 생성
    url_lookup = {tab['title']: tab['url'] for tab in global_last_raw_tabs_data}

    for title in selected_items_set:
        item_url = url_lookup.get(title) # 룩업에서 URL 검색
        
        if item_url:
            # URL이 있으면 '탭'으로 저장
            hydrated_items_list.append({
                "type": "tab", "title": title, "url": item_url
            })
        elif title in global_last_raw_windows:
            # 윈도우 목록에 있으면 '윈도우'로 저장
            hydrated_items_list.append({
                "type": "window", "title": title
            })
        else:
            # (그 사이에 닫힌 경우) '알 수 없음'으로 저장
            hydrated_items_list.append({
                "type": "unknown", "title": title
            })

    # 3. 저장할 새 그룹 데이터 생성
    new_group_data = {
        "category": group_name,
        "summary": f"총 {len(hydrated_items_list)}개의 항목을 수동으로 저장함",
        "items": hydrated_items_list
    }
    
    # 4. 파일에 저장 (session_utils.py 호출)
    success = save_session(new_group_data)
    
    if success:
        print("[선택 저장] 저장 완료. '저장된 탭'을 갱신합니다.")
        # 5. '저장된 탭' 새로고침
        ui_queue.put({'type': 'refresh_saved_tab'})
        
        # 6. 선택 상태 초기화
        selected_items_set.clear()
        
        # 7. [신규] '라이브 탭' 강제 새로고침
        # (체크박스 해제를 즉시 반영하기 위해)
        ui_queue.put({'type': 'force_live_refresh'})
    else:
        print("[선택 저장] 파일 저장에 실패했습니다.")
# --- [신규 기능 끝] ---

# -------------------------------------------------------------------
# (UI 업데이트 함수)
# -------------------------------------------------------------------

def update_ai_summary_tab(parent_frame, ai_summary_json, raw_tabs_data, raw_windows):
    """(탭 1) "관련 작업" 탭 (체크박스 추가)"""
    global selected_items_set
    print(f"[DEBUG] 'AI 요약 탭' UI 재생성... (선택 {len(selected_items_set)}개 복원)")
    
    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    url_lookup = {tab['title']: tab['url'] for tab in raw_tabs_data}
    current_tab_titles = list(url_lookup.keys())

    if not ai_summary_json:
        ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in ai_summary_json:
            category_name = category_group.get('category', '알 수 없음')
            summary = category_group.get('summary', '요약 없음')
            items_titles_only = category_group.get('items', [])

            group_frame = ttk.Labelframe(
                master=container, text=category_name,
                style="Custom.TLabelframe", padding=10
            )
            group_frame.pack(fill=X, pady=5, padx=5)

            # (상단 프레임)
            top_frame = ttk.Frame(group_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)
            summary_label = ttk.Label(
                top_frame, text=summary, 
                font=("Arial", 10, "italic"), wraplength=450
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            # (데이터 강화 로직)
            hydrated_group_data = json.loads(json.dumps(category_group))
            hydrated_items_list = [] 
            for title in items_titles_only:
                item_url = url_lookup.get(title) 
                if item_url:
                    hydrated_items_list.append({"type": "tab", "title": title, "url": item_url})
                elif title in raw_windows:
                    hydrated_items_list.append({"type": "window", "title": title})
                else:
                    hydrated_items_list.append({"type": "unknown", "title": title})
            hydrated_group_data['items'] = hydrated_items_list
            
            # (그룹 버튼)
            group_close_button = ttk.Button(
                top_frame, text="그룹 닫기", bootstyle="danger-outline", width=10,
                command=lambda current_items=items_titles_only: on_close_group_click(current_items)
            )
            group_close_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            group_save_button = ttk.Button(
                top_frame, text="그룹 저장", bootstyle="success-outline", width=10,
                command=lambda data=hydrated_group_data: on_save_group_click(data)
            )
            group_save_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            # --- [수정] 항목 리스트에 체크박스 추가 ---
            if not items_titles_only:
                ttk.Label(group_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item_title in items_titles_only:
                    icon = "•" 
                    if item_title in raw_windows: icon = "🖥️"
                    elif item_title in current_tab_titles: icon = "🌐"
                    
                    item_frame = ttk.Frame(group_frame)
                    item_frame.pack(fill=X, padx=10) 
                    
                    # --- [신규] 체크박스 ---
                    var = tk.BooleanVar()
                    if item_title in selected_items_set:
                        var.set(True) # UI 복원
                    
                    chk = ttk.Checkbutton(
                        item_frame,
                        variable=var,
                        command=lambda t=item_title, v=var: on_item_check(t, v)
                    )
                    chk.pack(side=LEFT, padx=(5,0))
                    # --- [신규 끝] ---
                    
                    close_button = ttk.Button(
                        item_frame, text="X", bootstyle="danger-outline", width=2,
                        command=lambda title=item_title: on_close_item_click(title)
                    )
                    close_button.pack(side=RIGHT, padx=5)

                    label = ttk.Label(
                        item_frame, text=f"{icon} {item_title}", 
                        font=("Arial", 10), cursor="hand2"
                    )
                    # [수정] 체크박스가 생겼으므로 LEFT로 pack
                    label.pack(side=LEFT, anchor="w", padx=(0, 5)) 
                    label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))
            # --- [수정 끝] ---

def update_raw_list_tab(parent_frame, raw_tabs_data, raw_windows):
    """(탭 2) "전체 목록" 탭 (체크박스 추가)"""
    global selected_items_set
    print(f"[DEBUG] '전체 목록 탭' UI 재생성... (선택 {len(selected_items_set)}개 복원)")
    
    for widget in parent_frame.winfo_children():
        widget.destroy()
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container

    # (프로그램 창 부분 - 수정됨)
    prog_frame = ttk.Labelframe(
        container, text="프로그램 창", style="Custom.TLabelframe", padding=10
    )
    prog_frame.pack(fill=X, pady=5, padx=5)
    if not raw_windows:
        ttk.Label(prog_frame, text="- 열린 프로그램이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item_title in raw_windows: # 'item_title'은 '제목' 문자열
            item_frame = ttk.Frame(prog_frame) 
            item_frame.pack(fill=X, padx=10)
            
            # --- [신규] 체크박스 ---
            var = tk.BooleanVar()
            if item_title in selected_items_set:
                var.set(True)
            chk = ttk.Checkbutton(
                item_frame, 
                variable=var,
                command=lambda t=item_title, v=var: on_item_check(t, v)
            )
            chk.pack(side=LEFT, padx=(5,0))
            # --- [신규 끝] ---
            
            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item_title: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)
            label = ttk.Label(item_frame, text=f"🖥️ {item_title}", font=("Arial", 10), cursor="hand2") 
            label.pack(side=LEFT, anchor="w", padx=(0, 5))
            label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))

    # (브라우저 탭 부분 - 수정됨)
    tab_frame = ttk.Labelframe(
        container, text="브라우저 탭", style="Custom.TLabelframe", padding=10
    )
    tab_frame.pack(fill=X, pady=5, padx=5)
    if not raw_tabs_data:
        ttk.Label(tab_frame, text="- 열린 탭이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for tab_dict in raw_tabs_data:
            item_title = tab_dict['title']
            item_frame = ttk.Frame(tab_frame) 
            item_frame.pack(fill=X, padx=10)
            
            # --- [신규] 체크박스 ---
            var = tk.BooleanVar()
            if item_title in selected_items_set:
                var.set(True)
            chk = ttk.Checkbutton(
                item_frame, 
                variable=var,
                command=lambda t=item_title, v=var: on_item_check(t, v)
            )
            chk.pack(side=LEFT, padx=(5,0))
            # --- [신규 끝] ---

            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item_title: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)
            label = ttk.Label(item_frame, text=f"🌐 {item_title}", font=("Arial", 10), cursor="hand2")
            label.pack(side=LEFT, anchor="w", padx=(0, 5))
            label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))

def toggle_frame(frame, button):
    """(접기/펴기 콜백 - 수정 없음)"""
    if frame.winfo_ismapped():
        frame.pack_forget()
        button.config(text="▶") 
    else:
        frame.pack(fill=X, anchor="w", padx=0, pady=(5,0))
        button.config(text="▼")

def update_saved_sessions_tab(parent_frame):
    """(탭 3) "저장된 작업" 탭 (수정 없음)"""
    print(f"[DEBUG] '저장된 작업 탭' UI 재생성...")

    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    saved_sessions = load_sessions()

    if not saved_sessions:
        ttk.Label(container, text="저장된 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for session_group in reversed(saved_sessions):
            category_name = session_group.get('category', '알 수 없음')
            summary = session_group.get('summary', '요약 없음')
            items_data = session_group.get('items', []) 
            saved_at_iso = session_group.get('saved_at')
            
            try:
                saved_at_dt = datetime.fromisoformat(saved_at_iso)
                saved_at_str = saved_at_dt.strftime('%Y-%m-%d %H:%M')
            except (ValueError, TypeError, AttributeError):
                saved_at_str = "시간 정보 없음"

            group_frame = ttk.Labelframe(
                master=container,
                text=f"{category_name} ({saved_at_str})",
                style="Custom.TLabelframe",
                padding=10
            )
            group_frame.pack(fill=X, pady=5, padx=5)

            top_frame = ttk.Frame(group_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)

            summary_label = ttk.Label(
                top_frame, text=summary, 
                font=("Arial", 10, "italic"), wraplength=300 
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            toggle_btn = ttk.Button(
                top_frame, text="▼", bootstyle="light-outline", width=2
            )
            toggle_btn.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            restore_button = ttk.Button(
                top_frame,
                text="그룹 복원",
                bootstyle="primary-outline",
                width=9, 
                command=lambda items=items_data: on_restore_group_click(items)
            )
            restore_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            group_delete_button = ttk.Button(
                top_frame,
                text="그룹 삭제",
                bootstyle="danger-outline",
                width=9,
                command=lambda group=session_group: on_delete_group_click(group)
            )
            group_delete_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            items_frame = ttk.Frame(group_frame)
            items_frame.pack(fill=X, padx=0, pady=0)
            
            if not items_data:
                ttk.Label(items_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item_data in items_data:
                    item_list_frame = ttk.Frame(items_frame)
                    item_list_frame.pack(fill=X, padx=10) 
                    
                    icon = "•"
                    item_title = ""
                    item_url = None
                    is_restorable = False 

                    if isinstance(item_data, dict):
                        item_type = item_data.get('type', 'unknown')
                        item_title = item_data.get('title', '제목 없음')
                        
                        if item_type == 'tab':
                            icon = "🌐"
                            item_url = item_data.get('url')
                            if item_url: 
                                is_restorable = True 
                        elif item_type == 'window':
                            icon = "🖥️"
                            is_restorable = True 
                    else:
                        item_title = str(item_data) 
                        icon = "❓" 

                    label = ttk.Label(
                        item_list_frame, 
                        text=f"{icon} {item_title}",
                        font=("Arial", 10)
                    )
                    label.pack(side=LEFT, anchor="w", padx=(10, 5))
                    
                    if item_url: 
                        url_label = ttk.Label(
                            item_list_frame,
                            text=f"({item_url[:30]}...)", 
                            font=("Arial", 9, "italic"),
                            bootstyle="secondary"
                        )
                        url_label.pack(side=LEFT, anchor="w", padx=5)
                    
                    if is_restorable:
                        restore_item_btn = ttk.Button(
                            item_list_frame,
                            text="복원",
                            bootstyle="info-outline", 
                            width=4,
                            command=lambda item=item_data: on_restore_item_click(item, is_group_call=False)
                        )
                        restore_item_btn.pack(side=RIGHT, padx=5)

            toggle_btn.config(command=lambda f=items_frame, b=toggle_btn: toggle_frame(f, b))


def check_queue(root, tab_ai_parent, tab_raw_parent, tab_saved_parent):
    """(수정) 100ms마다 큐를 확인 (전역 변수 갱신, force_live_refresh 처리)"""
    global global_last_raw_tabs_data, global_last_raw_windows
    
    try:
        message_data = ui_queue.get_nowait()
        message_type = message_data.get('type')
        
        if message_type == 'raw_update':
            print("[DEBUG] UI 큐: '실시간' 데이터 수신.")
            
            # [신규] 전역 변수 갱신
            global_last_raw_tabs_data = message_data.get('raw_tabs_data', [])
            global_last_raw_windows = message_data.get('raw_windows', [])
            
            try:
                update_raw_list_tab(
                    tab_raw_parent, 
                    global_last_raw_tabs_data, 
                    global_last_raw_windows
                )
            except Exception as e:
                print(f"[DEBUG] !!! 전체 목록 탭 업데이트 중 오류 발생: {e} !!!")
        
        elif message_type == 'ai_update':
            print("[DEBUG] UI 큐: 'AI 결과' 데이터 수신.")
            
            # [신규] 전역 변수 갱신
            global_last_raw_tabs_data = message_data.get('raw_tabs_data', [])
            global_last_raw_windows = message_data.get('raw_windows', [])
            
            try:
                update_ai_summary_tab(
                    tab_ai_parent, 
                    message_data.get('ai_summary', []),
                    global_last_raw_tabs_data,
                    global_last_raw_windows
                )
            except Exception as e:
                print(f"[DEBUG] !!! AI 요약 탭 업데이트 중 오류 발생: {e} !!!")

        elif message_type == 'refresh_saved_tab':
            print("[DEBUG] UI 큐: '저장 탭 갱신' 요청 수신.")
            try:
                update_saved_sessions_tab(tab_saved_parent)
            except Exception as e:
                print(f"[DEBUG] !!! 저장 탭 업데이트 중 오류 발생: {e} !!!")

        # --- [신규] '선택 저장' 완료 후 라이브 탭 강제 갱신 ---
        elif message_type == 'force_live_refresh':
            print("[DEBUG] UI 큐: '라이브 탭' 갱신 요청 수신 (선택 초기화).")
            # (저장 후 체크박스를 해제하기 위해 두 탭 모두 갱신)
            try:
                # 1. 전체 목록 탭 갱신
                update_raw_list_tab(
                    tab_raw_parent, 
                    global_last_raw_tabs_data, 
                    global_last_raw_windows
                )
                # 2. AI 탭 갱신
                #    AI 요약본이 없으므로, 빈 리스트로 갱신하여 체크박스만 초기화
                #    (다음 AI 갱신 시 어차피 다시 그려짐)
                update_ai_summary_tab(
                    tab_ai_parent, 
                    [], # AI 요약본이 없으므로 빈 리스트 전달
                    global_last_raw_tabs_data,
                    global_last_raw_windows
                )
            except Exception as e:
                print(f"[DEBUG] !!! 라이브 탭(Raw/AI) 갱신 중 오류 발생: {e} !!!")
        # --- [신규 끝] ---

        elif message_data.get('error'):
            print(f"UI 큐 오류 수신: {message_data['error']}")
        
    except Empty:
        pass
    except Exception as e:
        print(f"Check_queue 오류: {e}")
    finally:
        root.after(100, check_queue, root, tab_ai_parent, tab_raw_parent, tab_saved_parent)

# -------------------------------------------------------------------
# 프로그램의 진짜 시작점
# -------------------------------------------------------------------
if __name__ == "__main__":
    
    configure_gemini()
    server_thread = threading.Thread(
        target=start_server_thread, 
        args=(ui_queue, command_queue, job_queue),
        daemon=True
    )
    server_thread.start()
    worker_thread = threading.Thread(
        target=ai_worker_thread,
        args=(job_queue, ui_queue), 
        daemon=True
    )
    worker_thread.start()
    
    root = ttk.Window(themename="superhero")
    root.title("내 작업 요약기 (AIProject)")
    root.geometry("600x700")

    style = ttk.Style()
    default_fg = style.lookup("TLabel", "foreground") 
    style.configure(
        "Custom.TLabelframe", 
        relief="solid", borderwidth=1, bordercolor=default_fg 
    )
    style.configure(
        "Custom.TLabelframe.Label",
        font=("Arial", 14, "bold"), foreground=default_fg      
    )

    title_label = ttk.Label(root, text="실시간 작업 요약 대시보드", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)

    notebook = ttk.Notebook(root)
    # [수정] 하단 버튼 공간 확보를 위해 Pady 변경
    notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(10, 5)) 

    tab_ai_parent_frame = ttk.Frame(notebook, padding=0)
    tab_raw_parent_frame = ttk.Frame(notebook, padding=0)
    tab_saved_parent_frame = ttk.Frame(notebook, padding=0)
    
    notebook.add(tab_ai_parent_frame, text="관련 작업 (AI 요약)")
    notebook.add(tab_raw_parent_frame, text="전체 목록 (원본)")
    notebook.add(tab_saved_parent_frame, text="저장된 작업 (보관함)")
    
    # --- [신규] 하단 '선택 항목 저장' 버튼 프레임 ---
    bottom_frame = ttk.Frame(root)
    bottom_frame.pack(fill=X, padx=10, pady=(5, 10))
    
    save_selected_button = ttk.Button(
        bottom_frame,
        text="선택 항목 저장하기",
        bootstyle="success", # (눈에 띄는 'success' 스타일)
        # --- [수정] 람다에 'root' 전달 ---
        command=lambda: on_save_selected_click(root)
    )
    save_selected_button.pack(fill=X, expand=YES)
    # --- [신규 끝] ---
    
    root.after(100, check_queue, root, tab_ai_parent_frame, tab_raw_parent_frame, tab_saved_parent_frame)
    ui_queue.put({'type': 'refresh_saved_tab'})
    
    print("메인 UI 창을 시작합니다...")
    root.mainloop()