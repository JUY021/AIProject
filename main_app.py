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
# (큐 정의... 동일)
# -------------------------------------------------------------------
ui_queue = Queue()
command_queue = Queue()
job_queue = Queue()
# [수정] 'is_ui_updating' 잠금 변수는 더 이상 필요 없습니다.
# is_ui_updating = False 

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

# [삭제] clear_container 함수는 더 이상 필요 없습니다.

def on_close_item_click(title):
    """(통합 닫기 버튼 콜백)"""
    print(f"'{title}' 항목 닫기 요청...")
    close_window_by_title(title)
    command_queue.put({ "action": "close_tab", "title": title })

def update_ai_summary_tab(parent_frame, ai_summary_json, raw_tabs, raw_windows):
    """(탭 1) "관련 작업" 탭을 'Labelframe'(Collapse 대체) UI로 새로 그립니다."""
    print(f"[DEBUG] 'AI 요약 탭' UI 재생성 (Collapse 미사용)...")
    
    # 1. [TclError 해결] 탭의 이전 내용을 '통째로' 파괴
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # 2. '통째로' 스크롤 가능한 새 프레임 생성
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container # 내용물이 들어갈 곳

    # 3. 새 카드로 채우기
    if not ai_summary_json:
        ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in ai_summary_json:
            category_name = category_group.get('category', '알 수 없음')
            summary = category_group.get('summary', '요약 없음')
            items = category_group.get('items', [])

            # -------------------------------------------------
            # [수정] 'Collapse' 위젯을 'Labelframe'으로 대체
            # (라이브러리 꼬임 문제 우회)
            # -------------------------------------------------
            group_frame = ttk.Labelframe(
                master=container,
                text=category_name, # 제목
                style="Custom.TLabelframe", # "전체 목록" 탭과 동일한 스타일 적용
                padding=10
            )
            group_frame.pack(fill=X, pady=5, padx=5)

            # 1. 요약 (바로 보임)
            summary_label = ttk.Label(group_frame, text=summary, font=("Arial", 10, "italic"), wraplength=550)
            summary_label.pack(anchor="w", fill=X, pady=(0, 10), padx=5)
            
            # 2. 항목 리스트 (바로 보임)
            if not items:
                ttk.Label(group_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item in items:
                    icon = "•" 
                    if item in raw_windows: icon = "🖥️"
                    elif item in raw_tabs: icon = "🌐"
                    
                    item_frame = ttk.Frame(group_frame) # group_frame에 속함
                    item_frame.pack(fill=X, padx=10) 
                    
                    close_button = ttk.Button(
                        item_frame, text="X", bootstyle="danger-outline", width=2,
                        command=lambda title=item: on_close_item_click(title)
                    )
                    close_button.pack(side=RIGHT, padx=5)

                    label = ttk.Label(item_frame, text=f"{icon} {item}", font=("Arial", 10))
                    label.pack(side=LEFT, anchor="w", padx=(0, 5))


def update_raw_list_tab(parent_frame, raw_tabs, raw_windows):
    """(탭 2) "전체 목록" 탭을 '커스텀 스타일' 카드로 새로 그립니다."""
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
            label = ttk.Label(item_frame, text=f"🖥️ {item}", font=("Arial", 10)) 
            label.pack(side=LEFT, anchor="w", padx=(0, 5))

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
            label = ttk.Label(item_frame, text=f"🌐 {item}", font=("Arial", 10))
            label.pack(side=LEFT, anchor="w", padx=(0, 5))
        

def check_queue(root, tab_ai_parent, tab_raw_parent):
    """100ms마다 큐를 확인하여 모든 UI 탭을 업데이트합니다."""
    # [수정] 'is_ui_updating' 잠금 제거
    
    try:
        message_data = ui_queue.get_nowait()
        message_type = message_data.get('type')
        
        if message_type == 'raw_update':
            print("[DEBUG] UI 큐: '실시간' 데이터 수신.")
            try:
                # [수정] '부모 프레임'을 전달하여 UI를 통째로 다시 그림
                update_raw_list_tab(tab_raw_parent, message_data.get('raw_tabs', []), message_data.get('raw_windows', []))
            except Exception as e:
                print(f"[DEBUG] !!! 전체 목록 탭 업데이트 중 오류 발생: {e} !!!")
        
        elif message_type == 'ai_update':
            print("[DEBUG] UI 큐: 'AI 결과' 데이터 수신.")
            try:
                # [수정] '부모 프레임'을 전달하여 UI를 통째로 다시 그림
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
        # [수정] 'is_ui_updating = False' 제거
        root.after(100, check_queue, root, tab_ai_parent, tab_raw_parent) # 다음 큐 확인 예약

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

    # -------------------------------------------------
    # [수정] TclError를 해결하기 위해, ScrollableTab을 직접 추가하지 않고
    # '부모 프레임'만 추가합니다. (check_queue가 이 프레임을 채울 것입니다)
    # -------------------------------------------------
    tab_ai_parent_frame = ttk.Frame(notebook, padding=0)
    tab_raw_parent_frame = ttk.Frame(notebook, padding=0)
    
    notebook.add(tab_raw_parent_frame, text="전체 목록 (원본)")
    notebook.add(tab_ai_parent_frame, text="관련 작업 (AI 요약)")
    
    root.after(100, check_queue, root, tab_ai_parent_frame, tab_raw_parent_frame)

    print("메인 UI 창을 시작합니다...")
    root.mainloop()