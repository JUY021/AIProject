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
from session_utils import save_session, load_sessions

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
# (항목 클릭 함수... on_save_group_click까지 동일)
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

# --- [오류 수정] 구 버전 'str' 데이터 호환성 추가 ---
def on_restore_group_click(items_data):
    """(그룹 복원 콜백) 저장된 그룹을 복원합니다 (브라우저 탭만)."""
    print(f"'{len(items_data)}'개 항목의 그룹 복원 요청... (탭만 복원 시도)")
    
    tabs_opened = 0
    if not items_data:
        return

    for item in items_data:
        # --- [수정] 'item'이 딕셔너리인지 먼저 확인 ---
        if isinstance(item, dict): 
            # 'type'이 'tab'이고 'url' 키가 있는지 확인
            if item.get('type') == 'tab' and item.get('url'):
                url_to_open = item.get('url')
                print(f"  -> [탭 복원] {url_to_open}")
                # 'open_tab' 명령을 background.js로 전송
                command_queue.put({"action": "open_tab", "url": url_to_open})
                tabs_opened += 1
            elif item.get('type') == 'window':
                print(f"  -> [프로그램 복원] '{item.get('title')}' (지원되지 않음, 건너뜀)")
        else:
            # 'item'이 딕셔너리가 아닌 'str' (문자열)인 경우 (구 버전 데이터)
            print(f"  -> [복원 불가] '{item}' (URL 정보가 없는 구 버전 데이터, 건너뜀)")
        # --- [수정 끝] ---
            
    print(f"총 {tabs_opened}개의 탭 복원 명령을 전송했습니다.")
# --- [오류 수정 끝] ---


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


# --- [신규 기능] 접기/펴기 토글 함수 ---
def toggle_frame(frame, button):
    """프레임(내용)을 접거나 폅니다."""
    if frame.winfo_ismapped():
        # 프레임이 보이면 -> 숨김
        frame.pack_forget()
        button.config(text="▶") # 펴기 아이콘
    else:
        # 프레임이 숨겨져 있으면 -> 보임
        frame.pack(fill=X, anchor="w", padx=0, pady=(5,0))
        button.config(text="▼") # 접기 아이콘
# --- [신규 기능 끝] ---


# --- [수정] update_saved_sessions_tab (오류 수정 + 접기 기능) ---
def update_saved_sessions_tab(parent_frame):
    """(탭 3 - 수정) "저장된 작업" 탭 (오류 수정 및 접기 기능 추가)"""
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

            # --- [수정] 요약/버튼/항목을 담을 '내부 프레임' (이 프레임을 접었다 폄) ---
            inner_content_frame = ttk.Frame(group_frame)
            # [신규] 기본은 펼쳐진 상태로 시작
            inner_content_frame.pack(fill=X, anchor="w", padx=0, pady=(5,0)) 

            # --- [수정] 'top_frame'을 'inner_content_frame' 안에 배치 ---
            top_frame = ttk.Frame(inner_content_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)

            summary_label = ttk.Label(
                top_frame, text=summary, 
                font=("Arial", 10, "italic"), wraplength=400 
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            restore_button = ttk.Button(
                top_frame,
                text="그룹 복원 (탭만)",
                bootstyle="primary-outline",
                width=16, 
                command=lambda items=items_data: on_restore_group_click(items)
            )
            restore_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            # --- [신규] '접기/펴기' 버튼 (Labelframe 제목줄에 추가) ---
            # Labelframe 위젯 자체에는 버튼을 추가하기 어려우므로
            # Labelframe 바로 위에 별도 프레임으로 제목줄을 흉내냅니다.
            
            # ... (이 방법은 Labelframe 구조와 충돌하므로, 
            #     더 간단하게 요약(summary) 레이블 옆에 버튼을 추가합니다.)
            
            # (위치 재조정) '복원 버튼'보다 왼쪽에 '접기 버튼' 추가
            toggle_btn = ttk.Button(
                top_frame,
                text="▼", # 기본 (접기)
                bootstyle="light-outline",
                width=2
            )
            toggle_btn.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            # --- [신규] 'items_frame'을 'inner_content_frame' 안에 배치 ---
            # (항목 리스트를 담을 별도 프레임)
            items_frame = ttk.Frame(inner_content_frame)
            items_frame.pack(fill=X, padx=0, pady=0)
            
            # --- [수정] 'items_data' (딕셔너리 리스트)를 순회 ---
            if not items_data:
                ttk.Label(items_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item_data in items_data: # 변수명 변경
                    item_list_frame = ttk.Frame(items_frame) # items_frame에 속함
                    item_list_frame.pack(fill=X, padx=10) 
                    
                    icon = "•"
                    item_title = ""
                    item_url = None

                    # --- [오류 수정] 'item_data'가 딕셔너리인지 문자열인지 확인 ---
                    if isinstance(item_data, dict):
                        # 신규 데이터 ({"type": ..., "title": ...})
                        item_type = item_data.get('type', 'unknown')
                        item_title = item_data.get('title', '제목 없음')
                        
                        if item_type == 'tab':
                            icon = "🌐"
                            item_url = item_data.get('url')
                        elif item_type == 'window':
                            icon = "🖥️"
                    else:
                        # 구 버전 데이터 (단순 "문자열")
                        item_title = str(item_data) # "Google"
                        icon = "❓" # 구 버전 데이터임을 표시
                    # --- [오류 수정 끝] ---

                    label = ttk.Label(
                        item_list_frame, 
                        text=f"{icon} {item_title}",
                        font=("Arial", 10)
                    )
                    label.pack(side=LEFT, anchor="w", padx=(10, 5))
                    
                    if item_url: 
                        url_label = ttk.Label(
                            item_list_frame,
                            text=f"({item_url[:50]}...)",
                            font=("Arial", 9, "italic"),
                            bootstyle="secondary"
                        )
                        url_label.pack(side=LEFT, anchor="w", padx=5)

            # --- [신규] 접기 버튼에 명령 연결 ---
            # (요약 레이블, 복원 버튼, 항목 리스트 프레임이 모두 'inner_content_frame'에
            #  포함되어야 하지만, 지금 구조가 복잡해졌으므로
            #  '항목 리스트(items_frame)'만 접었다 폈다 하도록 수정합니다.)
            
            # (구조 재수정) top_frame과 items_frame을 담는 'inner_content_frame'을
            # 토글하는 것이 아니라, 'items_frame'만 토글하도록 수정.
            
            # (최종 수정)
            # 1. top_frame (요약, 버튼들)은 항상 보이게 둔다.
            # 2. items_frame (항목 리스트)을 토글한다.
            
            # 'toggle_frame' 함수가 'items_frame'과 'toggle_btn'을 참조하도록 람다 수정
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