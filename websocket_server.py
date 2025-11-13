# websocket_server.py

import asyncio
import websockets
import json
import functools
import time
import threading 
from queue import Empty # [신규] 큐가 비었을 때 예외
from window_utils import get_open_windows
from gemini_processor import get_summary_from_gemini

# [수정] 닫기 명령을 보낼 '연결된 클라이언트'를 전역으로 관리
global_connected_clients = set() 

last_processed_state = None
ai_is_busy = False 

def ai_task_thread(tab_titles, window_titles, queue):
    """ (AI 작업 스레드 - 변경 없음) """
    global ai_is_busy
    try:
        ai_summary_json = get_summary_from_gemini(tab_titles, window_titles)
        data_for_ui = {
            'raw_tabs': tab_titles,
            'raw_windows': window_titles,
            'ai_summary': ai_summary_json 
        }
        queue.put(data_for_ui)
    except Exception as e:
        print(f"AI 작업 스레드 오류: {e}")
        queue.put({ 'error': str(e) })
    finally:
        print("AI 작업 완료. 잠금 해제.")
        ai_is_busy = False

async def handler(websocket, ui_queue):
    """(데이터 수신 핸들러) 클라이언트가 연결되면 호출되는 함수"""
    
    global last_processed_state, ai_is_busy, global_connected_clients 
    
    global_connected_clients.add(websocket) # [수정] 전역 세트에 클라이언트 추가
    print(f"클라이언트 연결됨: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # (데이터 수집, 캐시, AI 잠금 확인... 로직은 동일)
                tab_list = json.loads(message)
                tab_titles = [tab.get('title', '제목 없음') for tab in tab_list if tab.get('title')]
                window_titles = get_open_windows()
                current_tabs_sorted = tuple(sorted(tab_titles))
                current_windows_sorted = tuple(sorted(window_titles))
                current_state = (current_tabs_sorted, current_windows_sorted)

                if current_state == last_processed_state:
                    continue 
                if ai_is_busy:
                    print("데이터 변경 감지. 하지만 AI가 아직 작업 중... 이번 요청은 건너뜀.")
                    continue 
                
                print("데이터 변경 감지. AI 작업 스레드 시작...")
                last_processed_state = current_state
                ai_is_busy = True 
                
                # (AI 스레드 시작... 로직 동일)
                threading.Thread(
                    target=ai_task_thread, 
                    args=(tab_titles, window_titles, ui_queue), 
                    daemon=True
                ).start()
                
            except Exception as e:
                print(f"핸들러 내부 오류 발생: {e}")
                if ai_is_busy:
                    ai_is_busy = False

    except websockets.exceptions.ConnectionClosed:
        print(f"클라이언트 연결 끊김: {websocket.remote_address}")
    finally:
        global_connected_clients.remove(websocket) # [수정] 전역 세트에서 제거
        last_processed_state = None 
        ai_is_busy = False 

# -------------------------------------------------
# [신규] 명령 감시자 (Command Poller)
# -------------------------------------------------
async def command_poller(command_queue):
    """
    (UI -> 서버) '명령 큐'를 0.1초마다 비동기적으로 확인하고
    명령이 있으면 모든 클라이언트(JS)에게 전송합니다.
    """
    while True:
        try:
            # 1. (UI가 보낸) 명령 큐를 확인 (non-blocking)
            command = command_queue.get_nowait()
            
            if command:
                print(f"[DEBUG] 명령 감지: {command}")
                payload = json.dumps(command)
                
                # 2. (Python -> JS) 연결된 모든 클라이언트에게 명령 전송
                # (주의: 여러 브라우저가 열려있으면 모두에게 전송됨)
                for client in global_connected_clients:
                    print(f"[DEBUG] 클라이언트 {client.remote_address}에게 명령 전송...")
                    await client.send(payload) # 'await'를 사용하는 비동기 전송
                    
        except Empty:
            # 큐가 비어있으면 0.1초 대기 (비동기)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"명령 감시자(Poller) 오류: {e}")
            await asyncio.sleep(1) # 오류 시 1초 대기


async def server_main(handler_with_args, command_queue):
    """서버를 실행하는 메인 비동기 함수"""
    
    # [신규] 명령 감시자(Poller)를 백그라운드 작업으로 시작
    asyncio.create_task(command_poller(command_queue))
    
    # 메인 핸들러(데이터 수신) 시작
    async with websockets.serve(handler_with_args, "localhost", 9090):
        print("백그라운드 WebSocket 서버가 9090 포트에서 시작되었습니다.")
        await asyncio.Future()

def start_server_thread(ui_queue, command_queue): # [수정] command_queue 받기
    """백그라운드 스레드에서 WebSocket 서버를 실행합니다."""
    handler_with_args = functools.partial(handler, ui_queue=ui_queue)
    # [수정] command_queue를 server_main으로 전달
    asyncio.run(server_main(handler_with_args, command_queue))