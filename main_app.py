# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
from queue import Queue # [수정] 큐를 2개 사용할 것이므로 이름 변경 안 함

# 모듈 import
from gemini_processor import configure_gemini
from websocket_server import start_server_thread
from window_utils import close_window_by_title 
from ui_components import ScrollableTab

# -------------------------------------------------------------------
# UI 위젯을 저장할 전역 변수
# -------------------------------------------------------------------
ui_queue = Queue()     # (서버 -> UI) AI 요약 결과를 받는 통로
command_queue = Queue() # [신규] (UI -> 서버) '탭 닫기' 명령을 보내는 통로
is_ui_updating = False 

# -------------------------------------------------------------------
# UI 업데이트 함수
# -------------------------------------------------------------------

def clear_container(container):
    if container:
        for widget in container.winfo_children():
            widget.destroy()

def update_ai_summary_tab(container, ai_summary_json):
    """(탭 1) "관련 작업" 탭을 UI에 그립니다."""
    print(f"[DEBUG] 'AI 요약 탭' 업데이트 시작. {len(ai_summary_json)}개 카테고리.")
    if not container: return

    clear_container(container)

    if not ai_summary_json:
        ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in ai_summary_json:
            category_name = category_group.get('category', '알 수 없음')
            items = category_group.get('items', [])

            # [수정] UI를 'Labelframe' 카드로 복구 (Collapse 오류 방지)
            card_frame = ttk.Labelframe(
                master=container,
                text=category_name, 
                bootstyle="secondary",
                padding=10
            )
            card_frame.pack(fill=X, pady=5, padx=5)
            
            items_text = "\n".join(f"• {item}" for item in items)
            items_label = ttk.Label(card_frame, text=items_text, font=("Arial", 10), justify=LEFT)
            items_label.pack(anchor="w", fill=X, padx=10, pady=10)


def on_close_program_button_click(title):
    """(프로그램용) 닫기 버튼 콜백"""
    print(f"'{title}' 프로그램 닫기 요청...")
    close_window_by_title(title)

# -------------------------------------------------
# [신규] '탭 닫기' 버튼 콜백
# -------------------------------------------------
def on_close_tab_button_click(title):
    """(브라우저 탭용) 닫기 버튼 콜백"""
    print(f"'{title}' 탭 닫기 요청...")
    # [신규] '명령 큐'에 JSON 명령을 넣습니다.
    command_queue.put({
        "action": "close_tab",
        "title": title
    })

def update_raw_list_tab(container, raw_tabs, raw_windows):
    """(탭 2) "전체 목록" 탭에 [X] 닫기 버튼을 추가합니다."""
    print(f"[DEBUG] '전체 목록 탭' 업데이트 시작. 탭 {len(raw_tabs)}개, 창 {len(raw_windows)}개.")
    if not container: return

    clear_container(container)
    
    # 1. 프로그램 창 (닫기 버튼)
    ttk.Label(container, text="프로그램 창", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 5), padx=5)
    if not raw_windows:
        ttk.Label(container, text="- 열린 프로그램이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item in raw_windows:
            item_frame = ttk.Frame(container)
            item_frame.pack(fill=X, padx=10)
            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item: on_close_program_button_click(title)
            )
            close_button.pack(side=RIGHT, padx=5)
            label = ttk.Label(item_frame, text=f"🖥️ {item}", font=("Arial", 10)) 
            label.pack(side=LEFT, anchor="w")

    # 2. 브라우저 탭
    ttk.Label(container, text="브라우저 탭", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20, 5), padx=5)
    if not raw_tabs:
        ttk.Label(container, text="- 열린 탭이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item in raw_tabs:
            # -------------------------------------------------
            # [수정] 브라우저 탭에도 [X] 닫기 버튼 추가
            # -------------------------------------------------
            item_frame = ttk.Frame(container)
            item_frame.pack(fill=X, padx=10)
            
            close_button = ttk.Button(
                item_frame, 
                text="X", 
                bootstyle="danger-outline", # (일단 'danger'로 표시, 나중에 'info' 등으로 변경)
                width=2,
                command=lambda title=item: on_close_tab_button_click(title)
            )
            close_button.pack(side=RIGHT, padx=5)

            label = ttk.Label(item_frame, text=f"🌐 {item}", font=("Arial", 10))
            label.pack(side=LEFT, anchor="w")
        

def check_queue(root, tab_ai, tab_raw):
    """100ms마다 큐를 확인하여 모든 UI 탭을 업데이트합니다."""
    global is_ui_updating 
    
    if is_ui_updating:
        root.after(100, check_queue, root, tab_ai, tab_raw)
        return

    try:
        message_data = ui_queue.get_nowait()
        print(f"[DEBUG] UI 큐에서 새 데이터 수신: {len(message_data.get('ai_summary', []))}개 카테고리")
        is_ui_updating = True 
        
        if message_data.get('error'):
            print(f"UI 큐 오류 수신: {message_data['error']}")
        else:
            try:
                update_ai_summary_tab(tab_ai.container, message_data.get('ai_summary', []))
            except Exception as e:
                print(f"[DEBUG] !!! AI 요약 탭 업데이트 중 오류 발생: {e} !!!")
            
            try:
                update_raw_list_tab(tab_raw.container, message_data.get('raw_tabs', []), message_data.get('raw_windows', []))
            except Exception as e:
                print(f"[DEBUG] !!! 전체 목록 탭 업데이트 중 오류 발생: {e} !!!")

            root.update_idletasks()
            print("[DEBUG] UI 강제 새로고침 (update_idletasks) 완료.")

    except Exception as e:
        pass
    finally:
        is_ui_updating = False 
        root.after(100, check_queue, root, tab_ai, tab_raw)

# -------------------------------------------------------------------
# 프로그램의 진짜 시작점
# -------------------------------------------------------------------
if __name__ == "__main__":
    
    configure_gemini()

    # [수정] command_queue를 start_server_thread로 전달
    server_thread = threading.Thread(
        target=start_server_thread, 
        args=(ui_queue, command_queue), # <-- command_queue 추가
        daemon=True
    )
    server_thread.start()
    
    root = ttk.Window(themename="superhero")
    root.title("내 작업 요약기 (AIProject)")
    root.geometry("600x700")

    title_label = ttk.Label(root, text="실시간 작업 요약 대시보드", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)

    notebook = ttk.Notebook(root)
    notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(0, 10))

    tab_ai_summary = ScrollableTab(notebook, padding=10)
    tab_raw_list = ScrollableTab(notebook, padding=10)
    
    notebook.add(tab_raw_list, text="전체 목록 (원본)")
    notebook.add(tab_ai_summary, text="관련 작업 (AI 요약)")
    
    root.after(100, check_queue, root, tab_ai_summary, tab_raw_list)

    print("메인 UI 창을 시작합니다...")
    root.mainloop()