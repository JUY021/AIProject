# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
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
# --- [수정] overwrite_sessions import 추가 ---
from session_utils import save_session, load_sessions, overwrite_sessions

# -------------------------------------------------------------------
# (큐 정의... 동일)
# -------------------------------------------------------------------
ui_queue = Queue()
command_queue = Queue()
job_queue = Queue()

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
    """(그룹 복원 콜백 - 수정 없음, 호환성 코드 포함)"""
    print(f"'{len(items_data)}'개 항목의 그룹 복원 요청... (탭만 복원 시도)")
    
    tabs_opened = 0
    if not items_data:
        return

    for item in items_data:
        if isinstance(item, dict): 
            if item.get('type') == 'tab' and item.get('url'):
                url_to_open = item.get('url')
                print(f"  -> [탭 복원] {url_to_open}")
                command_queue.put({"action": "open_tab", "url": url_to_open})
                tabs_opened += 1
            elif item.get('type') == 'window':
                print(f"  -> [프로그램 복원] '{item.get('title')}' (지원되지 않음, 건너뜀)")
        else:
            print(f"  -> [복원 불가] '{item}' (URL 정보가 없는 구 버전 데이터, 건너뜀)")
            
    print(f"총 {tabs_opened}개의 탭 복원 명령을 전송했습니다.")

# --- [신규 기능] ---
def on_restore_item_click(item_data):
    """(신규) 저장된 개별 '탭' 항목을 복원합니다."""
    print(f"[개별 복원] '{item_data.get('title')}' 요청...")
    # (이미 on_restore_group_click 에서 검증된 로직)
    if isinstance(item_data, dict) and item_data.get('type') == 'tab' and item_data.get('url'):
        url_to_open = item_data.get('url')
        print(f"  -> [탭 복원] {url_to_open}")
        command_queue.put({"action": "open_tab", "url": url_to_open})
    else:
        print("  -> [복원 불가] 탭이 아니거나 URL 정보가 없습니다.")

def on_delete_group_click(group_to_delete):
    """(신규) 저장된 그룹을 'saved_sessions.json'에서 삭제합니다."""
    category = group_to_delete.get('category', '알 수 없음')
    # 'saved_at'은 session_utils.py에서 저장 시 추가한 고유 ID입니다.
    saved_at_id = group_to_delete.get('saved_at') 
    
    if not saved_at_id:
        print(f"'{category}' 그룹 삭제 실패: 고유 ID(saved_at)가 없습니다.")
        return

    print(f"'{category}' ({saved_at_id}) 그룹 삭제 요청...")
    
    # 1. 모든 세션 로드
    all_sessions = load_sessions()
    
    # 2. 'saved_at' ID를 기준으로 해당 그룹을 '제외한' 새 리스트 생성
    filtered_sessions = [
        session for session in all_sessions 
        if session.get('saved_at') != saved_at_id
    ]
    
    # 3. 덮어쓰기
    if len(filtered_sessions) < len(all_sessions):
        success = overwrite_sessions(filtered_sessions) # session_utils 호출
        if success:
            print("그룹 삭제 완료. 탭을 갱신합니다.")
            # 4. UI 갱신
            ui_queue.put({'type': 'refresh_saved_tab'})
        else:
            print("파일 덮어쓰기에 실패하여 삭제를 중단합니다.")
    else:
        print("삭제할 그룹을 찾지 못했습니다.")
# --- [신규 기능 끝] ---


# -------------------------------------------------------------------
# (UI 업데이트 함수)
# -------------------------------------------------------------------

def update_ai_summary_tab(parent_frame, ai_summary_json, raw_tabs_data, raw_windows):
    """(탭 1) "관련 작업" 탭 (수정 없음)"""
    print(f"[DEBUG] 'AI 요약 탭' UI 재생성...")
    
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

            top_frame = ttk.Frame(group_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)

            summary_label = ttk.Label(
                top_frame, text=summary, 
                font=("Arial", 10, "italic"), wraplength=450
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            # (데이터 강화 로직... 동일)
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
            
            # (버튼 로직... 동일)
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

            # (항목 리스트 로직... 동일)
            if not items_titles_only:
                ttk.Label(group_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item_title in items_titles_only:
                    icon = "•" 
                    if item_title in raw_windows: icon = "🖥️"
                    elif item_title in current_tab_titles: icon = "🌐"
                    
                    item_frame = ttk.Frame(group_frame)
                    item_frame.pack(fill=X, padx=10) 
                    
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


def update_raw_list_tab(parent_frame, raw_tabs_data, raw_windows):
    """(탭 2) "전체 목록" 탭 (수정 없음)"""
    print(f"[DEBUG] '전체 목록 탭' UI 재생성...")
    for widget in parent_frame.winfo_children():
        widget.destroy()
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container
    prog_frame = ttk.Labelframe(
        container, text="프로그램 창", style="Custom.TLabelframe", padding=10
    )
    prog_frame.pack(fill=X, pady=5, padx=5)
    if not raw_windows:
        ttk.Label(prog_frame, text="- 열린 프로그램이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item in raw_windows:
            item_frame = ttk.Frame(prog_frame) 
            item_frame.pack(fill=X, padx=10)
            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)
            label = ttk.Label(item_frame, text=f"🖥️ {item}", font=("Arial", 10), cursor="hand2") 
            label.pack(side=LEFT, anchor="w", padx=(0, 5))
            label.bind("<Button-1>", lambda e, t=item: on_item_click(t, raw_windows))
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


# --- [수정] update_saved_sessions_tab (개별 복원 / 그룹 삭제 버튼 추가) ---
def update_saved_sessions_tab(parent_frame):
    """(탭 3 - 수정) "저장된 작업" 탭 (개별 복원 / 그룹 삭제 추가)"""
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
                font=("Arial", 10, "italic"), wraplength=300 # 버튼 공간 확보
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            # --- [신규] 버튼 3개 (pack 순서가 UI 표시 순서의 역순임) ---
            
            # 1. (가장 왼쪽) 접기/펴기
            toggle_btn = ttk.Button(
                top_frame, text="▼", bootstyle="light-outline", width=2
            )
            toggle_btn.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            # 2. (중간) 그룹 복원
            restore_button = ttk.Button(
                top_frame,
                text="그룹 복원", # (텍스트 짧게 수정)
                bootstyle="primary-outline",
                width=9, 
                command=lambda items=items_data: on_restore_group_click(items)
            )
            restore_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            # 3. [신규] (가장 오른쪽) 그룹 삭제
            group_delete_button = ttk.Button(
                top_frame,
                text="그룹 삭제",
                bootstyle="danger-outline", # 삭제 버튼
                width=9,
                # 람다에 'session_group' (고유 ID 포함) 전달
                command=lambda group=session_group: on_delete_group_click(group)
            )
            group_delete_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            # --- [신규 끝] ---
            
            # (항목 리스트 프레임 - 수정 없음)
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
                    is_tab = False # [신규] 개별 복원 버튼 표시용 플래그

                    if isinstance(item_data, dict):
                        item_type = item_data.get('type', 'unknown')
                        item_title = item_data.get('title', '제목 없음')
                        
                        if item_type == 'tab':
                            icon = "🌐"
                            item_url = item_data.get('url')
                            is_tab = True # 탭 확인
                        elif item_type == 'window':
                            icon = "🖥️"
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
                            text=f"({item_url[:30]}...)", # 툴팁 길이 조절
                            font=("Arial", 9, "italic"),
                            bootstyle="secondary"
                        )
                        url_label.pack(side=LEFT, anchor="w", padx=5)
                    
                    # --- [신규] 개별 복원 버튼 ---
                    if is_tab:
                        restore_item_btn = ttk.Button(
                            item_list_frame,
                            text="복원",
                            bootstyle="info-outline", # (개별 버튼 스타일)
                            width=4,
                            command=lambda item=item_data: on_restore_item_click(item)
                        )
                        restore_item_btn.pack(side=RIGHT, padx=5)
                    # --- [신규 끝] ---

            # (접기 버튼 명령 연결 - 수정 없음)
            toggle_btn.config(command=lambda f=items_frame, b=toggle_btn: toggle_frame(f, b))
# --- [수정 끝] ---


# -------------------------------------------------------------------
# (check_queue... 동일)
# -------------------------------------------------------------------
def check_queue(root, tab_ai_parent, tab_raw_parent, tab_saved_parent):
    """(수정 없음) 100ms마다 큐를 확인하여 모든 UI 탭을 업데이트합니다."""
    
    try:
        message_data = ui_queue.get_nowait()
        message_type = message_data.get('type')
        
        if message_type == 'raw_update':
            print("[DEBUG] UI 큐: '실시간' 데이터 수신.")
            try:
                update_raw_list_tab(
                    tab_raw_parent, 
                    message_data.get('raw_tabs_data', []), 
                    message_data.get('raw_windows', [])
                )
            except Exception as e:
                print(f"[DEBUG] !!! 전체 목록 탭 업데이트 중 오류 발생: {e} !!!")
        
        elif message_type == 'ai_update':
            print("[DEBUG] UI 큐: 'AI 결과' 데이터 수신.")
            try:
                update_ai_summary_tab(
                    tab_ai_parent, 
                    message_data.get('ai_summary', []),
                    message_data.get('raw_tabs_data', []),
                    message_data.get('raw_windows', [])
                )
            except Exception as e:
                print(f"[DEBUG] !!! AI 요약 탭 업데이트 중 오류 발생: {e} !!!")

        elif message_type == 'refresh_saved_tab':
            print("[DEBUG] UI 큐: '저장 탭 갱신' 요청 수신.")
            try:
                update_saved_sessions_tab(tab_saved_parent)
            except Exception as e:
                print(f"[DEBUG] !!! 저장 탭 업데이트 중 오류 발생: {e} !!!")

        elif message_data.get('error'):
            print(f"UI 큐 오류 수신: {message_data['error']}")
        
    except Empty:
        pass
    except Exception as e:
        print(f"Check_queue 오류: {e}")
    finally:
        root.after(100, check_queue, root, tab_ai_parent, tab_raw_parent, tab_saved_parent)

# -------------------------------------------------------------------
# (프로그램 시작점 __main__... 동일)
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
    notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(0, 10))

    tab_ai_parent_frame = ttk.Frame(notebook, padding=0)
    tab_raw_parent_frame = ttk.Frame(notebook, padding=0)
    tab_saved_parent_frame = ttk.Frame(notebook, padding=0)
    
    notebook.add(tab_ai_parent_frame, text="관련 작업 (AI 요약)")
    notebook.add(tab_raw_parent_frame, text="전체 목록 (원본)")
    notebook.add(tab_saved_parent_frame, text="저장된 작업 (보관함)")
    
    root.after(100, check_queue, root, tab_ai_parent_frame, tab_raw_parent_frame, tab_saved_parent_frame)
    ui_queue.put({'type': 'refresh_saved_tab'})
    
    print("메인 UI 창을 시작합니다...")
    root.mainloop()