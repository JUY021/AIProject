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
from window_utils import close_window_by_title 
from ui_components import ScrollableTab

# -------------------------------------------------------------------
# 큐(Queue) 정의
# -------------------------------------------------------------------
ui_queue = Queue()      # (서버/AI -> UI) *모든* UI 업데이트 통로
command_queue = Queue() # (UI -> 서버) '탭 닫기' 명령을 보내는 통로
job_queue = Queue()     # [신규] (서버 -> AI) '작업 지시서'가 쌓이는 대기열
is_ui_updating = False 

# -------------------------------------------------------------------
# AI 작업자(Worker) 스레드
# -------------------------------------------------------------------
def ai_worker_thread(job_q, ui_q):
    """
    'job_queue'를 계속 감시하며, "15초 디바운싱" 로직으로
    AI를 호출하고, 그 결과를 'ui_queue'에 넣습니다.
    """
    DEBOUNCE_SECONDS = 15 # 15초간 변경이 없으면 처리
    
    while True:
        try:
            # 1. 큐에서 작업이 올 때까지 '숨 참고' 대기 (Blocking)
            job_data = job_q.get() 
            print("[DEBUG] AI 작업자: 새 작업 감지. 15초 디바운스 시작...")

            # 2. 15초 대기. 그동안 큐에 쌓인 모든 작업을 '무시'하고
            #    '마지막' 작업만 남깁니다.
            time.sleep(DEBOUNCE_SECONDS)
            
            try:
                while True:
                    job_data = job_q.get_nowait() # 논블로킹으로 큐 비우기
                    print("[DEBUG] AI 작업자: 중간 작업 건너뜀...")
            except Empty:
                pass # 큐가 다 비워졌으면 통과
            
            print("[DEBUG] AI 작업자: 15초 경과. '마지막' 작업으로 AI 호출 시작...")
            
            # 3. (오래 걸리는) AI 작업 호출
            ai_summary_json = get_summary_from_gemini(
                job_data['raw_tabs'], 
                job_data['raw_windows']
            )
            
            # 4. AI 작업이 끝나면, 결과물을 UI 큐에 넣음
            ai_data_for_ui = {
                'type': 'ai_update', 
                'ai_summary': ai_summary_json 
            }
            ui_q.put(ai_data_for_ui)
            
            print("[DEBUG] AI 작업자: 작업 완료. UI 큐에 'AI 결과' 전송.")
            
        except Exception as e:
            print(f"AI 작업자(Worker) 스레드 오류: {e}")

# -------------------------------------------------------------------
# UI 업데이트 함수
# -------------------------------------------------------------------

def clear_container(container):
    if container:
        for widget in container.winfo_children():
            widget.destroy()

# -------------------------------------------------
# [신규] "통합 닫기" 버튼 콜백 (main_app.py로 이동)
# -------------------------------------------------
def on_close_item_click(title):
    """
    [X] 버튼을 누르면 호출되는 '통합' 함수입니다.
    (프로그램 닫기 + 탭 닫기 명령을 둘 다 보냅니다)
    """
    print(f"'{title}' 항목 닫기 요청...")
    
    # 1. (Python) 프로그램 닫기 시도
    close_window_by_title(title)
    
    # 2. (JS) 브라우저 탭 닫기 시도
    command_queue.put({
        "action": "close_tab",
        "title": title
    })

def update_ai_summary_tab(container, ai_summary_json):
    """(탭 1) "관련 작업" 탭에 [X] 닫기 버튼을 추가합니다."""
    print(f"[DEBUG] 'AI 요약 탭' 업데이트 시작. {len(ai_summary_json)}개 카테고리.")
    if not container: return

    clear_container(container)

    if not ai_summary_json:
        ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in ai_summary_json:
            category_name = category_group.get('category', '알 수 없음')
            items = category_group.get('items', [])

            # 1. 카드 프레임 (Labelframe)
            card_frame = ttk.Labelframe(
                master=container,
                text=category_name, 
                bootstyle="secondary",
                padding=10
            )
            card_frame.pack(fill=X, pady=5, padx=5)
            
            # -------------------------------------------------
            # [수정] AI 요약 탭에도 닫기 버튼이 있는 항목 리스트
            # -------------------------------------------------
            if not items:
                ttk.Label(card_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item in items:
                    item_frame = ttk.Frame(card_frame)
                    item_frame.pack(fill=X)
                    
                    close_button = ttk.Button(
                        item_frame, 
                        text="X", 
                        bootstyle="danger-outline", 
                        width=2,
                        command=lambda title=item: on_close_item_click(title)
                    )
                    close_button.pack(side=RIGHT, padx=5)

                    label = ttk.Label(item_frame, text=f"• {item}", font=("Arial", 10))
                    label.pack(side=LEFT, anchor="w")


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
                command=lambda title=item: on_close_item_click(title) 
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
                command=lambda title=item: on_close_item_click(title) 
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
        
        message_type = message_data.get('type')
        
        if message_type == 'raw_update':
            print("[DEBUG] UI 큐: '실시간' 데이터 수신.")
            is_ui_updating = True 
            try:
                update_raw_list_tab(tab_raw.container, message_data.get('raw_tabs', []), message_data.get('raw_windows', []))
            except Exception as e:
                print(f"[DEBUG] !!! 전체 목록 탭 업데이트 중 오류 발생: {e} !!!")
            root.update_idletasks()
        
        elif message_type == 'ai_update':
            print("[DEBUG] UI 큐: 'AI 결과' 데이터 수신.")
            is_ui_updating = True 
            try:
                update_ai_summary_tab(tab_ai.container, message_data.get('ai_summary', []))
            except Exception as e:
                print(f"[DEBUG] !!! AI 요약 탭 업데이트 중 오류 발생: {e} !!!")
            root.update_idletasks()

        elif message_data.get('error'):
            print(f"UI 큐 오류 수신: {message_data['error']}")
        
    except Empty:
        pass
    except Exception as e:
        print(f"Check_queue 오류: {e}")
    finally:
        is_ui_updating = False 
        root.after(100, check_queue, root, tab_ai, tab_raw)

# -------------------------------------------------------------------
# 프로그램의 진짜 시작점
# -------------------------------------------------------------------
if __name__ == "__main__":
    
    configure_gemini()

    # 1. 웹소켓 서버 스레드 시작
    server_thread = threading.Thread(
        target=start_server_thread, 
        args=(ui_queue, command_queue, job_queue), # <-- 3개 큐 전달
        daemon=True
    )
    server_thread.start()
    
    # 2. AI 작업자 스레드 시작
    worker_thread = threading.Thread(
        target=ai_worker_thread,
        args=(job_queue, ui_queue), 
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