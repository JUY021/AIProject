# websocket_server.py

import asyncio
import websockets
import json
import functools
import time
import threading 
from queue import Empty 
from window_utils import get_open_windows

global_connected_clients = set() 
last_processed_state = None

async def handler(websocket, ui_queue, job_queue):
    """(데이터 수신 핸들러) 클라이언트가 연결되면 호출되는 함수"""
    
    global last_processed_state, global_connected_clients 
    
    global_connected_clients.add(websocket) 
    print(f"클라이언트 연결됨: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # 1. 원본 데이터 수집
                tab_list = json.loads(message)
                
                # --- [수정] title만 뽑는 대신 (title, url) 딕셔너리 리스트 생성 ---
                # (복원할 수 없는 chrome:// 탭 등은 제외)
                tab_data = [
                    {"title": tab.get('title'), "url": tab.get('url'), "browser": tab.get('browser', 'unknown')} 
                    for tab in tab_list 
                    if tab.get('title') and tab.get('url') and not tab.get('url').startswith('chrome://')
                ]
                # -----------------------------------------------------------
                
                window_titles = get_open_windows()
                
                # 2. [캐시] 데이터 변경 감지
                # --- [수정] 캐시 키는 여전히 title만 사용 ---
                current_tabs_sorted = tuple(sorted([t['title'] for t in tab_data]))
                # ----------------------------------------
                current_windows_sorted = tuple(sorted(window_titles))
                current_state = (current_tabs_sorted, current_windows_sorted)

                if current_state == last_processed_state:
                    continue 
                
                print("[DEBUG] 데이터 변경 감지 (URL/Browser 포함).")
                last_processed_state = current_state

                # 3. 큐로 데이터 전송
                
                # 1. "전체 목록" 탭을 위한 '실시간' 데이터
                raw_data_for_ui = {
                    'type': 'raw_update',
                    # --- [수정] 변수명 변경: raw_tabs -> raw_tabs_data ---
                    'raw_tabs_data': tab_data, 
                    'raw_windows': window_titles
                }
                ui_queue.put(raw_data_for_ui)
                print("[DEBUG] '실시간' 데이터를 UI 큐에 전송.")

                # 2. "AI 그룹핑" 탭을 위한 '작업 지시서'
                job_data_for_ai = {
                    # --- [수정] 변수명 변경: raw_tabs -> raw_tabs_data ---
                    'raw_tabs_data': tab_data,
                    'raw_windows': window_titles
                }
                job_queue.put(job_data_for_ai)
                print("[DEBUG] 'AI 작업'을 Job 큐에 전송.")
                
            except Exception as e:
                print(f"핸들러 내부 오류 발생: {e}")

    except websockets.exceptions.ConnectionClosed:
        print(f"클라이언트 연결 끊김: {websocket.remote_address}")
    finally:
        global_connected_clients.remove(websocket) 
        last_processed_state = None 

# -------------------------------------------------
# (명령 감시자 - 변경 없음)
# -------------------------------------------------
async def command_poller(command_queue):
    while True:
        try:
            command = command_queue.get_nowait()
            if command:
                print(f"[DEBUG] 명령 감지: {command}")
                payload = json.dumps(command)
                for client in global_connected_clients:
                    await client.send(payload) 
        except Empty:
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"명령 감시자(Poller) 오류: {e}")
            await asyncio.sleep(1) 


async def server_main(handler_with_args, command_queue):
    """서버를 실행하는 메인 비동기 함수"""
    asyncio.create_task(command_poller(command_queue))
    async with websockets.serve(handler_with_args, "localhost", 9090):
        print("백그라운드 WebSocket 서버가 9090 포트에서 시작되었습니다.")
        await asyncio.Future()

def start_server_thread(ui_queue, command_queue, job_queue):
    """백그라운드 스레드에서 WebSocket 서버를 실행합니다."""
    handler_with_args = functools.partial(handler, ui_queue=ui_queue, job_queue=job_queue)
    asyncio.run(server_main(handler_with_args, command_queue))