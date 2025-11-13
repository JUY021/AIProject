# websocket_server.py

import asyncio
import websockets
import json
import functools
import time
import threading 
from queue import Empty 
from window_utils import get_open_windows
# [수정] AI 프로세서를 직접 호출하지 않으므로 import 제거
# from gemini_processor import get_summary_from_gemini 

global_connected_clients = set() 
last_processed_state = None
# [수정] AI 관련 잠금(lock)이나 스레드(thread) 로직이 모두 제거됨
# (이 로직은 main_app.py로 이동)

async def handler(websocket, ui_queue, job_queue): # [수정] job_queue를 받음
    """(데이터 수신 핸들러) 클라이언트가 연결되면 호출되는 함수"""
    
    global last_processed_state, global_connected_clients 
    
    global_connected_clients.add(websocket) 
    print(f"클라이언트 연결됨: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # 1. 원본 데이터 수집
                tab_list = json.loads(message)
                tab_titles = [tab.get('title', '제목 없음') for tab in tab_list if tab.get('title')]
                window_titles = get_open_windows()
                
                # 2. [캐시] 데이터 변경 감지
                current_tabs_sorted = tuple(sorted(tab_titles))
                current_windows_sorted = tuple(sorted(window_titles))
                current_state = (current_tabs_sorted, current_windows_sorted)

                if current_state == last_processed_state:
                    continue 
                
                # -------------------------------------------------
                # [수정] AI를 직접 호출하는 대신, 'job_queue'에 작업을 넣습니다.
                # -------------------------------------------------
                print("[DEBUG] 데이터 변경 감지. AI 작업 큐에 추가...")
                last_processed_state = current_state
                
                job_data = {
                    'raw_tabs': tab_titles,
                    'raw_windows': window_titles
                }
                job_queue.put(job_data) # AI 작업자(Worker)에게 일감 전달
                # -------------------------------------------------
                
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
                    print(f"[DEBUG] 클라이언트 {client.remote_address}에게 명령 전송...")
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

def start_server_thread(ui_queue, command_queue, job_queue): # [수정] job_queue 받기
    """백그라운드 스레드에서 WebSocket 서버를 실행합니다."""
    # [수정] 핸들러에 job_queue도 전달
    handler_with_args = functools.partial(handler, ui_queue=ui_queue, job_queue=job_queue)
    asyncio.run(server_main(handler_with_args, command_queue))