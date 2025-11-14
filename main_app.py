# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
from queue import Queue, Empty
import time 

# 모듈 import
from gemini_processor import configure_gemini, get_summary_from_gemini 
from websocket_server import start_server_thread
from window_utils import close_window_by_title, activate_window_by_title
from ui_components import ScrollableTab
# --- [신규] 세션 유틸리티 import ---
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
            
            ai_summary_json = get_summary_from_gemini(
                job_data['raw_tabs'], 
                job_data['raw_windows']
            )
            
            ai_data_for_ui = {
                'type': 'ai_update', 
                'ai_summary': ai_summary_json,
                'raw_tabs': job_data['raw_tabs'],
                'raw_windows': job_data['raw_windows']
            }
            ui_q.put(ai_data_for_ui)
            
            print("[DEBUG] AI 작업자: 작업 완료. UI 큐에 'AI 결과' 전송.")
            
        except Exception as e:
            print(f"AI 작업자(Worker) 스레드 오류: {e}")

# -------------------------------------------------------------------
# UI 업데이트 함수
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# 항목 클릭 시 실행될 함수 (이동/활성화/닫기)
# -------------------------------------------------------------------
def on_item_click(title, raw_windows):
    """
    항목을 클릭했을 때 호출됩니다.
    - PC 창이면: activate_window_by_title 호출
    - 브라우저 탭이면: WebSocket으로 'activate_tab' 명령 전송
    """
    print(f"'{title}' 항목 클릭됨 (이동 요청)")
    
    if title in raw_windows:
        # PC 프로그램 창인 경우
        success = activate_window_by_title(title)
        if not success:
            print("창 활성화 실패 (이미 닫혔거나 권한 부족)")
    else:
        # 브라우저 탭인 경우 (창 목록에 없으면 탭으로 간주)
        command_queue.put({ "action": "activate_tab", "title": title })

def on_close_item_click(title):
    """(통합 닫기 버튼 콜백)"""
    print(f"'{title}' 항목 닫기 요청...")
    # PC 창 닫기 시도
    close_window_by_title(title)
    # 브라우저 탭 닫기 시도 (어차피 둘 중 하나만 성공함)
    command_queue.put({ "action": "close_tab", "title": title })

def on_close_group_click(items_list):
    """(그룹 닫기 콜백) AI가 분류한 그룹 전체를 닫습니다."""
    print(f"'{len(items_list)}'개 항목의 그룹 전체 닫기 요청...")
    
    if not items_list:
        return
        
    for title in items_list:
        # 개별 닫기 로직 재사용
        on_close_item_click(title)

# --- [신규 기능] ---
def on_save_group_click(group_data):
    """(신규) 그룹을 JSON 파일에 저장하고 닫습니다."""
    category = group_data.get('category', '알 수 없는 그룹')
    print(f"'{category}' 그룹 저장 요청...")
    
    # 1. 파일에 저장 (session_utils.py 호출)
    success = save_session(group_data)
    
    if success:
        # 2. 저장이 성공하면, 그룹 닫기 (기존 로직 재사용)
        items_list = group_data.get('items', [])
        on_close_group_click(items_list)
    else:
        print(f"'{category}' 그룹 저장 실패. 닫기 작업을 중단합니다.")
# --- [신규 기능 끝] ---


def update_ai_summary_tab(parent_frame, ai_summary_json, raw_tabs, raw_windows):
    """(탭 1) "관련 작업" 탭을 'Labelframe' UI로 새로 그립니다."""
    print(f"[DEBUG] 'AI 요약 탭' UI 재생성 (Collapse 미사용)...")
    
    # 1. 이전 내용 파괴
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # 2. 스크롤 탭 생성
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    # 3. 새 카드로 채우기
    if not ai_summary_json:
        ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in ai_summary_json:
            category_name = category_group.get('category', '알 수 없음')
            summary = category_group.get('summary', '요약 없음')
            items = category_group.get('items', [])

            # Labelframe 생성
            group_frame = ttk.Labelframe(
                master=container,
                text=category_name,
                style="Custom.TLabelframe",
                padding=10
            )
            group_frame.pack(fill=X, pady=5, padx=5)

            # --- [수정] 요약 레이블과 버튼을 한 줄에 배치 ---
            top_frame = ttk.Frame(group_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)

            # 1. 요약 (왼쪽 정렬)
            summary_label = ttk.Label(
                top_frame, 
                text=summary, 
                font=("Arial", 10, "italic"), 
                wraplength=450 # 버튼 공간 확보를 위해 너비 살짝 줄임
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            # --- [버튼 순서 변경 및 추가] ---
            # (pack()은 오른쪽(RIGHT)부터 쌓으므로, '닫기'를 먼저 pack해야 오른쪽에 갑니다)
            
            # 3. [기존] 그룹 닫기 버튼 (가장 오른쪽)
            group_close_button = ttk.Button(
                top_frame,
                text="그룹 닫기",
                bootstyle="danger-outline",
                width=10,
                command=lambda current_items=items: on_close_group_click(current_items)
            )
            group_close_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            # 2. [신규] 그룹 저장 버튼 (닫기 버튼 왼쪽)
            group_save_button = ttk.Button(
                top_frame,
                text="그룹 저장",
                bootstyle="success-outline", # '저장'에 어울리는 'success'
                width=10,
                # [중요] 람다에 'items'가 아닌 'category_group' 전체를 넘김
                command=lambda data=category_group: on_save_group_click(data)
            )
            group_save_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            # --- [수정 끝] ---

            # 4. 항목 리스트 (기존과 동일)
            if not items:
                ttk.Label(group_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item in items:
                    icon = "•" 
                    if item in raw_windows: icon = "🖥️"
                    elif item in raw_tabs: icon = "🌐"
                    
                    item_frame = ttk.Frame(group_frame)
                    item_frame.pack(fill=X, padx=10) 
                    
                    close_button = ttk.Button(
                        item_frame, text="X", bootstyle="danger-outline", width=2,
                        command=lambda title=item: on_close_item_click(title)
                    )
                    close_button.pack(side=RIGHT, padx=5)

                    label = ttk.Label(
                        item_frame, 
                        text=f"{icon} {item}", 
                        font=("Arial", 10),
                        cursor="hand2"
                    )
                    label.pack(side=LEFT, anchor="w", padx=(0, 5))
                    
                    label.bind("<Button-1>", lambda e, t=item: on_item_click(t, raw_windows))


def update_raw_list_tab(parent_frame, raw_tabs, raw_windows):
    """(탭 2) "전체 목록" 탭 (수정 없음)"""
    # ... (이 함수는 수정 사항 없음) ...
    print(f"[DEBUG] '전체 목록 탭' UI 재생성...")

    # 1. [TclError 해결] 탭의 이전 내용을 '통째로' 파괴
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # 2. '통째로' 스크롤 가능한 새 프레임 생성
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container # 내용물이 들어갈 곳

    # 3. 새 카드로 채우기
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
    
    if not raw_tabs:
        ttk.Label(tab_frame, text="- 열린 탭이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item in raw_tabs:
            item_frame = ttk.Frame(tab_frame) 
            item_frame.pack(fill=X, padx=10)
            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)
            label = ttk.Label(item_frame, text=f"🌐 {item}", font=("Arial", 10), cursor="hand2")
            label.pack(side=LEFT, anchor="w", padx=(0, 5))
            label.bind("<Button-1>", lambda e, t=item: on_item_click(t, raw_windows))
        

def check_queue(root, tab_ai_parent, tab_raw_parent):
    """(수정 없음) 100ms마다 큐를 확인하여 모든 UI 탭을 업데이트합니다."""
    # ... (이 함수는 수정 사항 없음) ...
    try:
        message_data = ui_queue.get_nowait()
        message_type = message_data.get('type')
        
        if message_type == 'raw_update':
            print("[DEBUG] UI 큐: '실시간' 데이터 수신.")
            try:
                update_raw_list_tab(tab_raw_parent, message_data.get('raw_tabs', []), message_data.get('raw_windows', []))
            except Exception as e:
                print(f"[DEBUG] !!! 전체 목록 탭 업데이트 중 오류 발생: {e} !!!")
        
        elif message_type == 'ai_update':
            print("[DEBUG] UI 큐: 'AI 결과' 데이터 수신.")
            try:
                update_ai_summary_tab(
                    tab_ai_parent, 
                    message_data.get('ai_summary', []),
                    message_data.get('raw_tabs', []),
                    message_data.get('raw_windows', [])
                )
            except Exception as e:
                print(f"[DEBUG] !!! AI 요약 탭 업데이트 중 오류 발생: {e} !!!")

        elif message_data.get('error'):
            print(f"UI 큐 오류 수신: {message_data['error']}")
        
    except Empty:
        pass
    except Exception as e:
        print(f"Check_queue 오류: {e}")
    finally:
        root.after(100, check_queue, root, tab_ai_parent, tab_raw_parent)

# -------------------------------------------------------------------
# 프로그램의 진짜 시작점 (수정 없음)
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

    # (커스텀 스타일 정의... 동일)
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

    # (부모 프레임 추가... 동일)
    tab_ai_parent_frame = ttk.Frame(notebook, padding=0)
    tab_raw_parent_frame = ttk.Frame(notebook, padding=0)
    
    # (AI 탭을 기본 탭으로 설정... 동일)
    notebook.add(tab_ai_parent_frame, text="관련 작업 (AI 요약)")
    notebook.add(tab_raw_parent_frame, text="전체 목록 (원본)")
    
    root.after(100, check_queue, root, tab_ai_parent_frame, tab_raw_parent_frame)

    print("메인 UI 창을 시작합니다...")
    root.mainloop()