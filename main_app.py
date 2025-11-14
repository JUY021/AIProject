# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
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

# --- (전역 변수... 동일) ---
selected_items_set = set()
global_last_raw_tabs_data = []
global_last_raw_windows = []
global_last_ai_summary = []

# --- [수정] 탭별 검색어 (변수 선언만) ---
global_search_query_ai = None
global_search_query_raw = None
global_search_query_saved = None
# --- [수정 끝] ---

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
# (항목 클릭 함수... on_close_selected_click 까지 동일)
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

def on_item_check(item_title, var):
    """(체크박스 콜백 - 수정 없음)"""
    if var.get():
        selected_items_set.add(item_title)
        print(f"[선택] '{item_title}' 추가 (총 {len(selected_items_set)}개)")
    else:
        if item_title in selected_items_set:
            selected_items_set.remove(item_title)
            print(f"[선택] '{item_title}' 제거 (총 {len(selected_items_set)}개)")
    ui_queue.put({'type': 'force_live_refresh'})

def on_select_all_in_group(items_titles):
    """(그룹 전체 선택 콜백 - 수정 없음)"""
    print(f"[선택] {len(items_titles)}개 그룹 전체 선택")
    for title in items_titles:
        selected_items_set.add(title)
    ui_queue.put({'type': 'force_live_refresh'}) # UI 갱신

def on_deselect_all_in_group(items_titles):
    """(그룹 전체 해제 콜백 - 수정 없음)"""
    print(f"[선택] {len(items_titles)}개 그룹 전체 해제")
    for title in items_titles:
        if title in selected_items_set:
            selected_items_set.remove(title)
    ui_queue.put({'type': 'force_live_refresh'}) # UI 갱신

def on_select_all_in_ai_tab(ai_summary_json):
    """('AI 탭' 전체 선택 - 수정 없음)"""
    print("[선택] '관련 작업' 탭 전체 선택")
    for group in ai_summary_json:
        for title in group.get('items', []):
            selected_items_set.add(title)
    ui_queue.put({'type': 'force_live_refresh'})

def on_deselect_all_in_ai_tab(ai_summary_json):
    """('AI 탭' 전체 해제 - 수정 없음)"""
    print("[선택] '관련 작업' 탭 전체 해제")
    for group in ai_summary_json:
        for title in group.get('items', []):
            if title in selected_items_set:
                selected_items_set.remove(title)
    ui_queue.put({'type': 'force_live_refresh'})

def on_select_all_in_raw_tab(raw_tabs_data, raw_windows):
    """('Raw 탭' 전체 선택 - 수정 없음)"""
    print("[선택] '전체 목록' 탭 전체 선택")
    for title in raw_windows:
        selected_items_set.add(title)
    for tab in raw_tabs_data:
        selected_items_set.add(tab['title'])
    ui_queue.put({'type': 'force_live_refresh'})

def on_deselect_all_in_raw_tab(raw_tabs_data, raw_windows):
    """('Raw 탭' 전체 해제 - 수정 없음)"""
    print("[선택] '전체 목록' 탭 전체 해제")
    for title in raw_windows:
        if title in selected_items_set:
            selected_items_set.remove(title)
    for tab in raw_tabs_data:
        if tab['title'] in selected_items_set:
            selected_items_set.remove(tab['title'])
    ui_queue.put({'type': 'force_live_refresh'})


def on_save_selected_click(root):
    """(선택 저장 콜백 - 수정 없음)"""
    global selected_items_set, global_last_raw_tabs_data, global_last_raw_windows
    if not selected_items_set:
        print("[선택 저장] 저장할 항목이 없습니다.")
        return
    print(f"[선택 저장] {len(selected_items_set)}개 항목 저장 시작...")
    group_name = simpledialog.askstring(
        "그룹 이름 입력", 
        "저장할 그룹의 이름을 입력하세요:",
        initialvalue="새로 저장한 그룹",
        parent=root
    )
    if not group_name:
        print("[선택 저장] 사용자가 취소했습니다.")
        return
    hydrated_items_list = []
    url_lookup = {tab['title']: tab['url'] for tab in global_last_raw_tabs_data}
    for title in selected_items_set:
        item_url = url_lookup.get(title)
        if item_url:
            hydrated_items_list.append({"type": "tab", "title": title, "url": item_url})
        elif title in global_last_raw_windows:
            hydrated_items_list.append({"type": "window", "title": title})
        else:
            hydrated_items_list.append({"type": "unknown", "title": title})
    new_group_data = {
        "category": group_name,
        "summary": f"총 {len(hydrated_items_list)}개의 항목을 수동으로 저장함",
        "items": hydrated_items_list
    }
    success = save_session(new_group_data)
    if success:
        print("[선택 저장] 저장 완료. '저장된 탭'을 갱신합니다.")
        ui_queue.put({'type': 'refresh_saved_tab'})
        selected_items_set.clear()
        ui_queue.put({'type': 'force_live_refresh'})
    else:
        print("[선택 저장] 파일 저장에 실패했습니다.")

def on_close_selected_click():
    """(선택 닫기 콜백 - 수정 없음)"""
    global selected_items_set
    if not selected_items_set:
        print("[선택 닫기] 선택된 항목이 없습니다.")
        return
    print(f"[선택 닫기] {len(selected_items_set)}개 항목 닫기 시작...")
    items_to_close = list(selected_items_set)
    for title in items_to_close:
        on_close_item_click(title)
    selected_items_set.clear()
    ui_queue.put({'type': 'force_live_refresh'})
# --- [함수 끝] ---


# --- [신규] 검색창 Enter 키 이벤트 핸들러 ---
def on_search_enter(event, tab_name):
    """(신규) 검색창에서 Enter키를 누르면 UI 갱신을 요청합니다."""
    print(f"[검색] {tab_name} 탭 검색 실행...")
    if tab_name == 'saved':
        ui_queue.put({'type': 'refresh_saved_tab'})
    else:
        ui_queue.put({'type': 'force_live_refresh'})
# --- [신규 끝] ---


# -------------------------------------------------------------------
# (UI 업데이트 함수)
# -------------------------------------------------------------------

def update_ai_summary_tab(parent_frame, ai_summary_json, raw_tabs_data, raw_windows):
    """(탭 1) "관련 작업" 탭 (검색창 추가, 필터링 로직 추가)"""
    global selected_items_set, global_search_query_ai
    print(f"[DEBUG] 'AI 요약 탭' UI 재생성... (선택 {len(selected_items_set)}개 복원)")
    
    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    url_lookup = {tab['title']: tab['url'] for tab in raw_tabs_data}
    current_tab_titles = list(url_lookup.keys())
    
    # --- [신규] 검색창 프레임 ---
    search_frame = ttk.Frame(container)
    search_frame.pack(fill=X, padx=5, pady=(5, 0))
    
    search_label = ttk.Label(search_frame, text="검색:")
    search_label.pack(side=LEFT, padx=(0, 5))
    
    search_entry = ttk.Entry(search_frame, textvariable=global_search_query_ai)
    search_entry.pack(side=LEFT, fill=X, expand=True)
    search_entry.bind("<Return>", lambda e: on_search_enter(e, 'ai'))
    # --- [신규 끝] ---

    # --- [신규] '탭' 전체 선택/해제 버튼 ---
    tab_actions_frame = ttk.Frame(container)
    tab_actions_frame.pack(fill=X, padx=5, pady=(5, 10))
    
    tab_select_all_btn = ttk.Button(
        tab_actions_frame, text="탭 전체 선택", bootstyle="info",
        command=lambda js=ai_summary_json: on_select_all_in_ai_tab(js)
    )
    tab_select_all_btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
    
    tab_deselect_all_btn = ttk.Button(
        tab_actions_frame, text="탭 전체 해제", bootstyle="warning",
        command=lambda js=ai_summary_json: on_deselect_all_in_ai_tab(js)
    )
    tab_deselect_all_btn.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))
    
    ttk.Separator(container).pack(fill=X, padx=5, pady=5)

    # --- [신규] 검색 필터링 로직 ---
    query = global_search_query_ai.get().lower()
    filtered_summary = ai_summary_json
    
    if query:
        print(f"  -> 'AI 요약' 탭 '{query}'로 필터링")
        filtered_summary = []
        for group in ai_summary_json:
            # 카테고리, 요약, 또는 항목 리스트 중 하나라도 일치하면 그룹 포함
            if (query in group.get('category', '').lower() or
                query in group.get('summary', '').lower() or
                any(query in item.lower() for item in group.get('items', []))):
                filtered_summary.append(group)
    # --- [신규 끝] ---

    if not filtered_summary:
        if query:
            ttk.Label(container, text=f"'{query}'에 대한 검색 결과가 없습니다.", font=("Arial", 12)).pack(pady=10)
        else:
            ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        # [수정] 'ai_summary_json' 대신 'filtered_summary' 사용
        for category_group in filtered_summary:
            category_name = category_group.get('category', '알 수 없음')
            summary = category_group.get('summary', '요약 없음')
            items_titles_only = category_group.get('items', [])

            group_frame = ttk.Labelframe(
                master=container, text=category_name,
                style="Custom.TLabelframe", padding=10
            )
            group_frame.pack(fill=X, pady=5, padx=5)

            top_frame = ttk.Frame(group_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)
            
            toggle_btn = ttk.Button(
                top_frame, text="▼", bootstyle="light-outline", width=2
            )
            toggle_btn.pack(side=LEFT, padx=(0, 5), pady=(0, 10))
            
            summary_label = ttk.Label(
                top_frame, text=summary, 
                font=("Arial", 10, "italic"), wraplength=300
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
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
            
            group_close_button = ttk.Button(
                top_frame, text="전체 닫기", bootstyle="danger-outline", width=8,
                command=lambda current_items=items_titles_only: on_close_group_click(current_items)
            )
            group_close_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            group_save_button = ttk.Button(
                top_frame, text="전체 저장", bootstyle="success-outline", width=8,
                command=lambda data=hydrated_group_data: on_save_group_click(data)
            )
            group_save_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            deselect_all_btn = ttk.Button(
                top_frame, text="전체 해제", bootstyle="warning-outline", width=8,
                command=lambda items=items_titles_only: on_deselect_all_in_group(items)
            )
            deselect_all_btn.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            select_all_btn = ttk.Button(
                top_frame, text="전체 선택", bootstyle="info-outline", width=8,
                command=lambda items=items_titles_only: on_select_all_in_group(items)
            )
            select_all_btn.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            inner_content_frame = ttk.Frame(group_frame)
            inner_content_frame.pack(fill=X, padx=0, pady=0)

            if not items_titles_only:
                ttk.Label(inner_content_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item_title in items_titles_only:
                    icon = "•" 
                    if item_title in raw_windows: icon = "🖥️"
                    elif item_title in current_tab_titles: icon = "🌐"
                    
                    item_frame = ttk.Frame(inner_content_frame) 
                    item_frame.pack(fill=X, padx=10) 
                    
                    var = tk.BooleanVar()
                    if item_title in selected_items_set:
                        var.set(True)
                    chk = ttk.Checkbutton(
                        item_frame,
                        variable=var,
                        command=lambda t=item_title, v=var: on_item_check(t, v)
                    )
                    chk.pack(side=LEFT, padx=(5,0))
                    
                    close_button = ttk.Button(
                        item_frame, text="X", bootstyle="danger-outline", width=2,
                        command=lambda title=item_title: on_close_item_click(title)
                    )
                    close_button.pack(side=RIGHT, padx=5)

                    label = ttk.Label(
                        item_frame, text=f"{icon} {item_title}", 
                        font=("Arial", 10), cursor="hand2"
                    )
                    label.pack(side=LEFT, anchor="w", padx=(0, 5)) 
                    label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))
            
            toggle_btn.config(command=lambda f=inner_content_frame, b=toggle_btn: toggle_frame(f, b))


def update_raw_list_tab(parent_frame, raw_tabs_data, raw_windows):
    """(탭 2) "전체 목록" 탭 (검색창 추가, 필터링 로직 추가)"""
    global selected_items_set, global_search_query_raw
    print(f"[DEBUG] '전체 목록 탭' UI 재생성... (선택 {len(selected_items_set)}개 복원)")
    
    for widget in parent_frame.winfo_children():
        widget.destroy()
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container

    # --- [신규] 검색창 프레임 ---
    search_frame = ttk.Frame(container)
    search_frame.pack(fill=X, padx=5, pady=(5, 0))
    
    search_label = ttk.Label(search_frame, text="검색:")
    search_label.pack(side=LEFT, padx=(0, 5))
    
    search_entry = ttk.Entry(search_frame, textvariable=global_search_query_raw)
    search_entry.pack(side=LEFT, fill=X, expand=True)
    search_entry.bind("<Return>", lambda e: on_search_enter(e, 'raw'))
    # --- [신규 끝] ---

    # --- [신규] '탭' 전체 선택/해제 버튼 ---
    tab_actions_frame = ttk.Frame(container)
    tab_actions_frame.pack(fill=X, padx=5, pady=(5, 10))
    
    tab_select_all_btn = ttk.Button(
        tab_actions_frame, text="탭 전체 선택", bootstyle="info",
        command=lambda tabs=raw_tabs_data, wins=raw_windows: on_select_all_in_raw_tab(tabs, wins)
    )
    tab_select_all_btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
    
    tab_deselect_all_btn = ttk.Button(
        tab_actions_frame, text="탭 전체 해제", bootstyle="warning",
        command=lambda tabs=raw_tabs_data, wins=raw_windows: on_deselect_all_in_raw_tab(tabs, wins)
    )
    tab_deselect_all_btn.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))
    # --- [신규 끝] ---
    
    ttk.Separator(container).pack(fill=X, padx=5, pady=5)

    # --- [신규] 검색 필터링 로직 ---
    query = global_search_query_raw.get().lower()
    filtered_windows = raw_windows
    filtered_tabs = raw_tabs_data
    
    if query:
        print(f"  -> '전체 목록' 탭 '{query}'로 필터링")
        filtered_windows = [w for w in raw_windows if query in w.lower()]
        filtered_tabs = [t for t in raw_tabs_data if query in t['title'].lower()]
    # --- [신규 끝] ---


    # (프로그램 창 부분 - 'filtered_windows' 사용)
    prog_frame = ttk.Labelframe(
        container, text="프로그램 창", style="Custom.TLabelframe", padding=10
    )
    prog_frame.pack(fill=X, pady=5, padx=5)
    
    prog_btn_frame = ttk.Frame(prog_frame)
    prog_btn_frame.pack(fill=X, padx=10, pady=(0, 5))
    
    prog_toggle_btn = ttk.Button(
        prog_btn_frame, text="▼", bootstyle="light-outline", width=2
    )
    prog_toggle_btn.pack(side=LEFT, padx=(0, 5))
    
    prog_select_all_btn = ttk.Button(
        prog_btn_frame, text="그룹 선택", bootstyle="info-outline",
        command=lambda items=filtered_windows: on_select_all_in_group(items) # [수정] 필터된 리스트 전달
    )
    prog_select_all_btn.pack(side=LEFT, padx=(0, 5))
    
    prog_deselect_all_btn = ttk.Button(
        prog_btn_frame, text="그룹 해제", bootstyle="warning-outline",
        command=lambda items=filtered_windows: on_deselect_all_in_group(items) # [수정] 필터된 리스트 전달
    )
    prog_deselect_all_btn.pack(side=LEFT)
    
    prog_items_frame = ttk.Frame(prog_frame)
    prog_items_frame.pack(fill=X, padx=0, pady=0)
    
    if not filtered_windows:
        ttk.Label(prog_items_frame, text="- 열린 프로그램이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item_title in filtered_windows: # [수정]
            item_frame = ttk.Frame(prog_items_frame) 
            item_frame.pack(fill=X, padx=10)
            
            var = tk.BooleanVar()
            if item_title in selected_items_set:
                var.set(True)
            chk = ttk.Checkbutton(
                item_frame, 
                variable=var,
                command=lambda t=item_title, v=var: on_item_check(t, v)
            )
            chk.pack(side=LEFT, padx=(5,0))
            
            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item_title: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)
            label = ttk.Label(item_frame, text=f"🖥️ {item_title}", font=("Arial", 10), cursor="hand2") 
            label.pack(side=LEFT, anchor="w", padx=(0, 5))
            label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))
            
    prog_toggle_btn.config(command=lambda f=prog_items_frame, b=prog_toggle_btn: toggle_frame(f, b))


    # (브라우저 탭 부분 - 'filtered_tabs' 사용)
    tab_frame = ttk.Labelframe(
        container, text="브라우저 탭", style="Custom.TLabelframe", padding=10
    )
    tab_frame.pack(fill=X, pady=5, padx=5)
    
    tab_btn_frame = ttk.Frame(tab_frame)
    tab_btn_frame.pack(fill=X, padx=10, pady=(0, 5))
    
    tab_toggle_btn = ttk.Button(
        tab_btn_frame, text="▼", bootstyle="light-outline", width=2
    )
    tab_toggle_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_titles_only = [tab['title'] for tab in filtered_tabs] # [수정]
    
    tab_select_all_btn = ttk.Button(
        tab_btn_frame, text="그룹 선택", bootstyle="info-outline",
        command=lambda items=tab_titles_only: on_select_all_in_group(items) # [수정]
    )
    tab_select_all_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_deselect_all_btn = ttk.Button(
        tab_btn_frame, text="그룹 해제", bootstyle="warning-outline",
        command=lambda items=tab_titles_only: on_deselect_all_in_group(items) # [수정]
    )
    tab_deselect_all_btn.pack(side=LEFT)
    
    tab_items_frame = ttk.Frame(tab_frame)
    tab_items_frame.pack(fill=X, padx=0, pady=0)
    
    if not filtered_tabs:
        ttk.Label(tab_items_frame, text="- 열린 탭이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for tab_dict in filtered_tabs: # [수정]
            item_title = tab_dict['title']
            item_frame = ttk.Frame(tab_items_frame) 
            item_frame.pack(fill=X, padx=10)
            
            var = tk.BooleanVar()
            if item_title in selected_items_set:
                var.set(True)
            chk = ttk.Checkbutton(
                item_frame, 
                variable=var,
                command=lambda t=item_title, v=var: on_item_check(t, v)
            )
            chk.pack(side=LEFT, padx=(5,0))

            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item_title: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)
            label = ttk.Label(item_frame, text=f"🌐 {item_title}", font=("Arial", 10), cursor="hand2")
            label.pack(side=LEFT, anchor="w", padx=(0, 5))
            label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))
            
    tab_toggle_btn.config(command=lambda f=tab_items_frame, b=tab_toggle_btn: toggle_frame(f, b))


def toggle_frame(frame, button):
    """(접기/펴기 콜백 - 수정 없음)"""
    if frame.winfo_ismapped():
        frame.pack_forget()
        button.config(text="▶") 
    else:
        frame.pack(fill=X, anchor="w", padx=0, pady=(5,0))
        button.config(text="▼")

def update_saved_sessions_tab(parent_frame):
    """(탭 3) "저장된 작업" 탭 (검색창 추가, 필터링 로직 추가)"""
    global global_search_query_saved
    print(f"[DEBUG] '저장된 작업 탭' UI 재생성...")

    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    # --- [신규] 검색창 프레임 ---
    search_frame = ttk.Frame(container)
    search_frame.pack(fill=X, padx=5, pady=(5, 0))
    
    search_label = ttk.Label(search_frame, text="검색:")
    search_label.pack(side=LEFT, padx=(0, 5))
    
    search_entry = ttk.Entry(search_frame, textvariable=global_search_query_saved)
    search_entry.pack(side=LEFT, fill=X, expand=True)
    search_entry.bind("<Return>", lambda e: on_search_enter(e, 'saved'))
    # --- [신규 끝] ---
    
    ttk.Separator(container).pack(fill=X, padx=5, pady=(10, 5))

    saved_sessions = load_sessions()

    # --- [신규] 검색 필터링 로직 ---
    query = global_search_query_saved.get().lower()
    filtered_sessions = saved_sessions
    
    if query:
        print(f"  -> '저장된 작업' 탭 '{query}'로 필터링")
        filtered_sessions = []
        
        def item_matches(item, query):
            # 구/신 버전 데이터 호환
            if isinstance(item, dict):
                return query in item.get('title', '').lower()
            else:
                return query in str(item).lower()
                
        for group in saved_sessions:
            if (query in group.get('category', '').lower() or
                query in group.get('summary', '').lower() or
                any(item_matches(item, query) for item in group.get('items', []))):
                filtered_sessions.append(group)
    # --- [신규 끝] ---

    if not filtered_sessions:
        if query:
            ttk.Label(container, text=f"'{query}'에 대한 검색 결과가 없습니다.", font=("Arial", 12)).pack(pady=10)
        else:
            ttk.Label(container, text="저장된 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        # [수정] 'saved_sessions' 대신 'filtered_sessions' 사용
        for session_group in reversed(filtered_sessions):
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
    global global_last_ai_summary
    
    try:
        message_data = ui_queue.get_nowait()
        message_type = message_data.get('type')
        
        if message_type == 'raw_update':
            print("[DEBUG] UI 큐: '실시간' 데이터 수신.")
            
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
            
            global_last_raw_tabs_data = message_data.get('raw_tabs_data', [])
            global_last_raw_windows = message_data.get('raw_windows', [])
            global_last_ai_summary = message_data.get('ai_summary', []) 
            
            try:
                update_ai_summary_tab(
                    tab_ai_parent, 
                    global_last_ai_summary,
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

        elif message_type == 'force_live_refresh':
            print("[DEBUG] UI 큐: '라이브 탭' 갱신 요청 수신 (선택/검색 동기화).")
            try:
                update_raw_list_tab(
                    tab_raw_parent, 
                    global_last_raw_tabs_data, 
                    global_last_raw_windows
                )
                update_ai_summary_tab(
                    tab_ai_parent, 
                    global_last_ai_summary, 
                    global_last_raw_tabs_data,
                    global_last_raw_windows
                )
            except Exception as e:
                print(f"[DEBUG] !!! 라이브 탭(Raw/AI) 갱신 중 오류 발생: {e} !!!")

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

    # --- [수정] 전역 Tkinter 변수 초기화 (반드시 root 생성 후) ---
    # [오류 수정] 이 블록은 이미 전역이므로 'global' 키워드를 사용하지 않습니다.
    global_search_query_ai = tk.StringVar(root) 
    global_search_query_raw = tk.StringVar(root) 
    global_search_query_saved = tk.StringVar(root)
    # --- [수정 끝] ---

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
    notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(10, 5)) 

    tab_ai_parent_frame = ttk.Frame(notebook, padding=0)
    tab_raw_parent_frame = ttk.Frame(notebook, padding=0)
    tab_saved_parent_frame = ttk.Frame(notebook, padding=0)
    
    notebook.add(tab_ai_parent_frame, text="관련 작업 (AI 요약)")
    notebook.add(tab_raw_parent_frame, text="전체 목록 (원본)")
    notebook.add(tab_saved_parent_frame, text="저장된 작업 (보관함)")
    
    # (하단 버튼 프레임 - 수정 없음)
    bottom_frame = ttk.Frame(root)
    bottom_frame.pack(fill=X, padx=10, pady=(5, 10))
    
    save_selected_button = ttk.Button(
        bottom_frame,
        text="선택 항목 저장",
        bootstyle="success",
        command=lambda: on_save_selected_click(root)
    )
    save_selected_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
    
    close_selected_button = ttk.Button(
        bottom_frame,
        text="선택 항목 닫기",
        bootstyle="danger",
        command=on_close_selected_click
    )
    close_selected_button.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))
    
    root.after(100, check_queue, root, tab_ai_parent_frame, tab_raw_parent_frame, tab_saved_parent_frame)
    ui_queue.put({'type': 'refresh_saved_tab'})
    
    print("메인 UI 창을 시작합니다...")
    root.mainloop()