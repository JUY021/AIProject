# websocket_server.py

import asyncio
import websockets
import json
import functools
import time
from window_utils import get_open_windows
from gemini_processor import get_summary_from_gemini

connected_clients = set()

last_processed_state = None
last_ai_call_time = 0
AI_COOLDOWN_SECONDS = 30 

async def handler(websocket, ui_queue):
    global last_processed_state, last_ai_call_time 
    
    connected_clients.add(websocket)
    print(f"클라이언트 연결됨: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # 1. 원본 데이터 수집
                tab_list = json.loads(message)
                tab_titles = [tab.get('title', '제목 없음') for tab in tab_list if tab.get('title')]
                window_titles = get_open_windows()
                
                print(f"[DEBUG] 탭 {len(tab_titles)}개, 창 {len(window_titles)}개 수신.") # [DEBUG]

                # 2. [캐시] 데이터 변경 감지
                current_tabs_sorted = tuple(sorted(tab_titles))
                current_windows_sorted = tuple(sorted(window_titles))
                current_state = (current_tabs_sorted, current_windows_sorted)

                if current_state == last_processed_state:
                    # print("[DEBUG] 데이터 변경 없음. 건너뜀.") # (너무 자주 찍히므로 주석 처리)
                    continue 
                
                # 3. [쿨다운]
                print("[DEBUG] 데이터 변경 감지. 쿨다운 확인...") # [DEBUG]
                current_time = time.time()
                if (current_time - last_ai_call_time) < AI_COOLDOWN_SECONDS:
                    print(f"[DEBUG] 쿨다운({AI_COOLDOWN_SECONDS}초) 대기 중... AI 호출 건너뜀.") # [DEBUG]
                    continue 
                
                
                print("[DEBUG] 쿨다운 통과. AI 호출 진행...") # [DEBUG]
                last_processed_state = current_state
                last_ai_call_time = current_time 
                
                if not tab_titles and not window_titles:
                    ui_queue.put({'raw_tabs': [], 'raw_windows': [], 'ai_summary': []})
                    continue

                # 4. Gemini 요약 (AI 가공)
                ai_summary_json = get_summary_from_gemini(tab_titles, window_titles)
                
                print(f"[DEBUG] AI로부터 {len(ai_summary_json)}개 카테고리 받음.") # [DEBUG]

                # 5. UI에 데이터 전송
                data_for_ui = {
                    'raw_tabs': tab_titles,
                    'raw_windows': window_titles,
                    'ai_summary': ai_summary_json 
                }
                print("[DEBUG] UI 큐에 데이터 삽입...") # [DEBUG]
                ui_queue.put(data_for_ui)
                
            except Exception as e:
                print(f"핸들러 내부 오류 발생: {e}")
                ui_queue.put({ 'error': str(e) })

    except websockets.exceptions.ConnectionClosed:
        print(f"클라이언트 연결 끊김: {websocket.remote_address}")
    finally:
        connected_clients.remove(websocket)
        last_processed_state = None 
        last_ai_call_time = 0 

async def server_main(handler_with_args):
    async with websockets.serve(handler_with_args, "localhost", 9090):
        print("백그라운드 WebSocket 서버가 9090 포트에서 시작되었습니다.")
        await asyncio.Future()

def start_server_thread(ui_queue):
    handler_with_args = functools.partial(handler, ui_queue=ui_queue)
    asyncio.run(server_main(handler_with_args))