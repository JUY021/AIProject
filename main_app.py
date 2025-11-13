# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
from queue import Queue

# 모듈 import
from gemini_processor import configure_gemini, get_summary_from_gemini # [수정] AI 함수 import
from websocket_server import start_server_thread
from window_utils import close_window_by_title 
from ui_components import ScrollableTab

# -------------------------------------------------------------------
# [수정] 큐(Queue) 정의
# -------------------------------------------------------------------
ui_queue = Queue()      # (AI -> UI) AI 요약 결과를 받는 통로
command_queue = Queue() # (UI -> 서버) '탭 닫기' 명령을 보내는 통로
job_queue = Queue()     # [신규] (서버 -> AI) '작업 지시서'가 쌓이는 대기열
is_ui_updating = False 

# -------------------------------------------------------------------
# [신규] AI 작업자(Worker) 스레드
# -------------------------------------------------------------------
def ai_worker_thread(job_q, ui_q):
    """
    'job_queue'를 계속 감시하며, 작업이 들어오면 '순서대로'
    Gemini AI를 호출하고, 그 결과를 'ui_queue'에 넣습니다.
    (이 함수는 별도의 스레드에서 영원히 실행됩니다.)
    """
    while True:
        try:
            # 1. 큐에서 작업이 올 때까지 '숨 참고' 대기 (Blocking)
            job_data = job_q.get() 
            
            print("[DEBUG] AI 작업자: 새 작업 수신. AI 호출 시작...")
            
            # 2. (오래 걸리는) AI 작업 호출
            ai_summary_json = get_summary_from_gemini(
                job_data['raw_tabs'], 
                job_data['raw_windows']
            )
            
            # 3. AI 작업이 끝나면, 결과물을 UI 큐에 넣음
            data_for_ui = {
                'raw_tabs': job_data['raw_tabs'],
                'raw_windows': job_data['raw_windows'],
                'ai_summary': ai_summary_json 
            }
            ui_q.put(data_for_ui)
            
            print("[DEBUG] AI 작업자: 작업 완료. UI 큐에 결과 전송.")
            
            # 4. 작업 완료 신호
            job_q.task_done()

        except Exception as e:
            print(f"AI 작업자(Worker) 스레드 오류: {e}")
            job_q.task_done() # 오류가 나도 큐는 비워줌

# -------------------------------------------------------------------
# (UI 업데이트 함수... 이하는 모두 동일)
# -------------------------------------------------------------------

def clear_container(container):
    if container:
        for widget in container.winfo_children():
            widget.destroy()

def update_ai_summary_tab(container, ai_summary_json):
    """(탭 1) "관련 작업" 탭을 'Labelframe' 카드로 채웁니다."""
    print(f"[DEBUG] 'AI 요약 탭' 업데이트 시작. {len(ai_summary_json)}개 카테고리.")
    if not container: return

    clear_container(container)

    if not ai_summary_json:
        ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in ai_summary_json:
            category_name = category_group.get('category', '알 수 없음')
            items = category_group.get('items', [])

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
    print(f"'{title}' 프로그램 닫기 요청...")
    close_window_by_title(title)

def update_raw_list_tab(container, raw_tabs, raw_windows):
    """(탭 2) "전체 목록" 탭에 [X] 닫기 버튼과 아이콘을 추가합니다."""
    print(f"[DEBUG] '전체 목록 탭' 업데이트 시작. 탭 {len(raw_tabs)}개, 창 {len(raw_windows)}개.")
    if not container: return

    clear_container(container)
    
    # 1. 프로그램 창
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
            item_frame = ttk.Frame(container)
            item_frame.pack(fill=X, padx=10)
            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
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

    # 1. [수정] 웹소켓 서버 스레드 시작 (job_queue 전달)
    server_thread = threading.Thread(
        target=start_server_thread, 
        args=(ui_queue, command_queue, job_queue), # <-- job_queue 추가
        daemon=True
    )
    server_thread.start()
    
    # 2. [신규] AI 작업자 스레드 시작
    worker_thread = threading.Thread(
        target=ai_worker_thread,
        args=(job_queue, ui_queue), # <-- 큐 2개 전달
        daemon=True
    )
    worker_thread.start()
    
    # 3. 메인 UI 스레드 시작
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