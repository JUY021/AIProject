# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
from queue import Queue

# 모듈 import
from gemini_processor import configure_gemini
from websocket_server import start_server_thread
from window_utils import close_window_by_title # <-- [수정] 닫기 함수 import
from ui_components import ScrollableTab

# -------------------------------------------------------------------
# UI 위젯을 저장할 전역 변수
# -------------------------------------------------------------------
ui_queue = Queue() 
is_ui_updating = False 

# -------------------------------------------------------------------
# UI 업데이트 함수
# -------------------------------------------------------------------

def clear_container(container):
    if container:
        for widget in container.winfo_children():
            widget.destroy()

def update_ai_summary_tab(container, ai_summary_json):
    """(탭 1) "관련 작업" 탭을 '접이식' 카드로 채웁니다."""
    if not container: return

    clear_container(container)

    if not ai_summary_json:
        ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in ai_summary_json:
            category_name = category_group.get('category', '알 수 없음')
            summary = category_group.get('summary', '요약 없음')
            items = category_group.get('items', [])

            # '접이식' 위젯 생성
            collapse = ttk.Collapse(
                master=container,
                bootstyle="secondary", 
                text=category_name,
                textvariable=None
            )
            collapse.pack(fill=X, pady=5, padx=5)

            collapsible_frame = collapse.frame 

            summary_label = ttk.Label(collapsible_frame, text=summary, font=("Arial", 10, "italic"), wraplength=550)
            summary_label.pack(anchor="w", fill=X, pady=(5, 10), padx=5)
            
            items_text = "\n".join(f"• {item}" for item in items)
            items_label = ttk.Label(collapsible_frame, text=items_text, font=("Arial", 10), justify=LEFT)
            items_label.pack(anchor="w", fill=X, padx=10, pady=(0, 5))

# -------------------------------------------------
# [신규] 닫기 버튼 콜백 함수 (다시 추가)
# -------------------------------------------------
def on_close_program_button_click(title):
    """닫기 버튼을 누르면 호출되는 함수"""
    print(f"'{title}' 프로그램 닫기 요청...")
    close_window_by_title(title)
    # 참고: 닫힌 후 UI가 바로 새로고침되지 않습니다.
    # 다음 AI 작업이 완료될 때(ai_is_busy=False) 갱신됩니다.

def update_raw_list_tab(container, raw_tabs, raw_windows):
    """(탭 2) [수정] "전체 목록" 탭에 [X] 닫기 버튼을 추가합니다."""
    if not container: return

    clear_container(container)
    
    # 1. 프로그램 창 (닫기 버튼 추가)
    ttk.Label(container, text="프로그램 창", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 5), padx=5)
    if not raw_windows:
        ttk.Label(container, text="- 열린 프로그램이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item in raw_windows:
            # [수정] 각 항목을 프레임으로 묶어 버튼을 추가
            item_frame = ttk.Frame(container)
            item_frame.pack(fill=X, padx=10)
            
            # [신규] 닫기 버튼
            close_button = ttk.Button(
                item_frame, 
                text="X", 
                bootstyle="danger-outline", 
                width=2,
                command=lambda title=item: on_close_program_button_click(title)
            )
            close_button.pack(side=RIGHT, padx=5)

            # 프로그램 제목
            label = ttk.Label(item_frame, text=f"• {item}", font=("Arial", 10))
            label.pack(side=LEFT, anchor="w")

    # 2. 브라우저 탭 (아직 닫기 기능 없음)
    ttk.Label(container, text="브라우저 탭", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20, 5), padx=5)
    if not raw_tabs:
        ttk.Label(container, text="- 열린 탭이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    for item in raw_tabs:
        # [수정] 닫기 버튼과 구별하기 위해 왼쪽 여백 추가
        ttk.Label(container, text=f"• {item}", font=("Arial", 10)).pack(anchor="w", padx=30)
        

def check_queue(root, tab1, tab2):
    """100ms마다 큐를 확인하여 모든 UI 탭을 업데이트합니다."""
    global is_ui_updating 
    
    if is_ui_updating:
        root.after(100, check_queue, root, tab1, tab2)
        return

    try:
        message_data = ui_queue.get_nowait()
        is_ui_updating = True 
        
        if message_data.get('error'):
            print(f"UI 큐 오류 수신: {message_data['error']}")
        else:
            update_ai_summary_tab(tab1.container, message_data.get('ai_summary', []))
            update_raw_list_tab(tab2.container, message_data.get('raw_tabs', []), message_data.get('raw_windows', []))

    except Exception as e:
        pass
    finally:
        is_ui_updating = False 
        root.after(100, check_queue, root, tab1, tab2)

# -------------------------------------------------------------------
# 프로그램의 진짜 시작점
# -------------------------------------------------------------------
if __name__ == "__main__":
    
    configure_gemini()

    server_thread = threading.Thread(target=start_server_thread, args=(ui_queue,), daemon=True)
    server_thread.start()
    
    root = ttk.Window(themename="superhero")
    root.title("내 작업 요약기 (AIProject)")
    root.geometry("600x700")

    title_label = ttk.Label(root, text="실시간 작업 요약 대시보드", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)

    notebook = ttk.Notebook(root)
    notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(0, 10))

    tab1 = ScrollableTab(notebook, padding=10)
    notebook.add(tab1, text="관련 작업 (AI 요약)")

    tab2 = ScrollableTab(notebook, padding=10)
    notebook.add(tab2, text="전체 목록 (원본)")
    
    root.after(100, check_queue, root, tab1, tab2)

    print("메인 UI 창을 시작합니다...")
    root.mainloop()