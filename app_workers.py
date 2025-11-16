# app_workers.py

import time
from queue import Empty

# 전역 상태 및 Gemini 프로세서 import
import app_state
from gemini_processor import get_summary_from_gemini

def ai_worker_thread():
    """AI 작업을 처리하는 백그라운드 스레드"""
    
    job_q = app_state.job_queue
    ui_q = app_state.ui_queue
    
    DEBOUNCE_SECONDS = 15 
    while True:
        try:
            # [수정] app_state에서 큐를 직접 참조
            job_data = job_q.get() 
            print("[DEBUG] AI 작업자: 새 작업 감지. 15초 디바운스 시작...")
            
            # --- [신규] '요약 중' 상태 설정 및 UI 갱신 요청 ---
            if app_state.global_is_ai_summarizing:
                app_state.global_is_ai_summarizing.set(True)
                # 'force_live_refresh'는 AI탭과 Raw탭을 모두 갱신함
                ui_q.put({'type': 'force_live_refresh'})
            # --- [신규 끝] ---

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

            # '요약 중' 상태 해제
            if app_state.global_is_ai_summarizing:
                app_state.global_is_ai_summarizing.set(False)

            ai_data_for_ui = {
                'type': 'ai_update', 
                'ai_summary': ai_summary_json,
                'raw_tabs_data': tabs_data_with_url, 
                'raw_windows': windows_titles
            }
            ui_q.put(ai_data_for_ui)
            print("[DEBUG] AI 작업자: 작업 완료. UI 큐에 'AI 결과' 전송.")
        except Exception as e:
            # 오류 발생 시에도 '요약 중' 상태 해제
            if app_state.global_is_ai_summarizing:
                app_state.global_is_ai_summarizing.set(False)
            print(f"AI 작업자(Worker) 스레드 오류: {e}")