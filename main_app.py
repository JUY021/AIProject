# main_app.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
from queue import Empty

# --- [수정] 모듈 import 방식 변경 ---
# 1. 전역 상태 (큐, 변수)
import app_state

# 2. 핵심 기능 모듈
from gemini_processor import configure_gemini
from websocket_server import start_server_thread

# 3. 분리된 모듈
from app_workers import ai_worker_thread
from ui_builders import update_ai_summary_tab, update_raw_list_tab, update_saved_sessions_tab
from app_callbacks import on_save_selected_click, on_close_selected_click, on_force_ai_refresh
# --- [수정 끝] ---


def check_queue(root, tab_ai_parent, tab_raw_parent, tab_saved_parent):
    """100ms마다 UI 큐를 확인하고 탭 갱신 함수를 호출합니다."""
    
    try:
        # [수정] app_state에서 큐를 직접 참조
        message_data = app_state.ui_queue.get_nowait()
        message_type = message_data.get('type')
        
        if message_type == 'raw_update':
            print("[DEBUG] UI 큐: '실시간' 데이터 수신.")
            
            app_state.global_last_raw_tabs_data = message_data.get('raw_tabs_data', [])
            app_state.global_last_raw_windows = message_data.get('raw_windows', [])
            
            try:
                update_raw_list_tab(
                    tab_raw_parent, 
                    root,
                    app_state.global_last_raw_tabs_data, 
                    app_state.global_last_raw_windows
                )
            except Exception as e:
                print(f"[DEBUG] !!! 전체 목록 탭 업데이트 중 오류 발생: {e} !!!")
        
        elif message_type == 'ai_update':
            print("[DEBUG] UI 큐: 'AI 결과' 데이터 수신.")
            
            app_state.global_last_raw_tabs_data = message_data.get('raw_tabs_data', [])
            app_state.global_last_raw_windows = message_data.get('raw_windows', [])
            app_state.global_last_ai_summary = message_data.get('ai_summary', []) 
            
            try:
                update_ai_summary_tab(
                    tab_ai_parent, 
                    root,
                    app_state.global_last_ai_summary,
                    app_state.global_last_raw_tabs_data,
                    app_state.global_last_raw_windows
                )
            except Exception as e:
                print(f"[DEBUG] !!! AI 요약 탭 업데이트 중 오류 발생: {e} !!!")

        elif message_type == 'refresh_saved_tab':
            print("[DEBUG] UI 큐: '저장 탭 갱신' 요청 수신.")
            try:
                update_saved_sessions_tab(tab_saved_parent, root)
            except Exception as e:
                print(f"[DEBUG] !!! 저장 탭 업데이트 중 오류 발생: {e} !!!")

        elif message_type == 'force_live_refresh':
            print("[DEBUG] UI 큐: '라이브 탭' 갱신 요청 수신 (선택/검색 동기화).")
            try:
                update_raw_list_tab(
                    tab_raw_parent, 
                    root,
                    app_state.global_last_raw_tabs_data, 
                    app_state.global_last_raw_windows
                )
                update_ai_summary_tab(
                    tab_ai_parent, 
                    root,
                    app_state.global_last_ai_summary, 
                    app_state.global_last_raw_tabs_data,
                    app_state.global_last_raw_windows
                )
            except Exception as e:
                print(f"[DEBUG] !!! 라이브 탭(Raw/AI) 갱신 중 오류 발생: {e} !!!")
                
        elif message_type == 'force_ai_refresh':
            print("[DEBUG] UI 큐: 'AI 수동 갱신' 요청 수신.")
            # AI 작업자에게 현재 최신 데이터를 기반으로 작업을 지시
            # (AI Worker의 15초 디바운싱이 적용됨)
            job_data = {
                'raw_tabs_data': app_state.global_last_raw_tabs_data,
                'raw_windows': app_state.global_last_raw_windows
            }
            app_state.job_queue.put(job_data)

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
    
    # 1. API 설정
    configure_gemini()
    
    # 2. 백그라운드 스레드 시작
    server_thread = threading.Thread(
        target=start_server_thread, 
        args=(app_state.ui_queue, app_state.command_queue, app_state.job_queue),
        daemon=True
    )
    server_thread.start()
    
    worker_thread = threading.Thread(
        target=ai_worker_thread,
        args=(), # [수정] app_workers가 app_state에서 직접 큐를 가져감
        daemon=True
    )
    worker_thread.start()
    
    # 3. 메인 UI 윈도우 생성
    root = ttk.Window(themename="superhero")
    root.title("WorkDash")
    root.geometry("600x700")

    # app_state에 정의된 Tkinter 변수 초기화 ---
    app_state.global_search_query_ai = tk.StringVar(root) 
    app_state.global_search_query_raw = tk.StringVar(root) 
    app_state.global_search_query_saved = tk.StringVar(root)
    # AI 작업 상태 변수 초기화
    app_state.global_is_ai_summarizing = tk.BooleanVar(root, value=False)

    # 4. 공통 스타일 정의
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

    try:
        # 1. AI 탭 새로고침 버튼용 스타일
        style.configure("Refresh.TButton", font=("Arial", 11))
        # 2. '라이브 탭' (AI, 전체) 아이콘용 스타일
        style.configure("Icon.TLabel", font=("Arial", 11))
        # 3. '저장된 탭' 아이콘용 스타일
        style.configure("SavedIcon.TLabel", font=("Arial", 11))

        # 4. 브라우저별 아이콘 스타일 (이모지 변경 가능)
        style.configure("ChromeIcon.TLabel", font=("Arial", 11))
        style.configure("FirefoxIcon.TLabel", font=("Arial", 11))
        style.configure("EdgeIcon.TLabel", font=("Arial", 11))
        style.configure("DefaultBrowserIcon.TLabel", font=("Arial", 11))

    except Exception as e:
        print(f"!!! 스타일 설정 오류: {e} !!!")

    # 5. 메인 레이아웃 (제목, 탭)
    title_label = ttk.Label(root, text="대시보드", font=("Arial", 20, "bold"))
    title_label.pack(pady=10)

    notebook = ttk.Notebook(root)
    notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(10, 5)) 

    tab_ai_parent_frame = ttk.Frame(notebook, padding=0)
    tab_raw_parent_frame = ttk.Frame(notebook, padding=0)
    tab_saved_parent_frame = ttk.Frame(notebook, padding=0)
    
    notebook.add(tab_ai_parent_frame, text="관련 작업 (AI 요약)")
    notebook.add(tab_raw_parent_frame, text="전체 목록 (원본)")
    notebook.add(tab_saved_parent_frame, text="저장된 작업 (보관함)")
    
    # 6. 하단 버튼 프레임
    bottom_frame = ttk.Frame(root)
    bottom_frame.pack(fill=X, padx=10, pady=(5, 10))
    
    save_selected_button = ttk.Button(
        bottom_frame,
        text="선택 항목 저장",
        bootstyle="success",
        command=lambda: on_save_selected_click(root) # [수정] 콜백 import
    )
    save_selected_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
    
    close_selected_button = ttk.Button(
        bottom_frame,
        text="선택 항목 닫기",
        bootstyle="danger",
        command=on_close_selected_click # [수정] 콜백 import
    )
    close_selected_button.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))
    
    # 7. UI 큐 폴링 시작 및 초기 탭 로드
    root.after(100, check_queue, root, tab_ai_parent_frame, tab_raw_parent_frame, tab_saved_parent_frame)
    app_state.ui_queue.put({'type': 'refresh_saved_tab'})
    
    # 8. 메인 루프 시작
    print("메인 UI 창을 시작합니다...")
    root.mainloop()