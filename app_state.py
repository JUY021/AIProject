# app_state.py

from queue import Queue

# 1. 스레드 간 통신 큐
ui_queue = Queue()
command_queue = Queue()
job_queue = Queue()

# 2. 전역 상태 변수
selected_items_set = set()
global_last_raw_tabs_data = []
global_last_raw_windows = []
global_last_ai_summary = []

# 3. Tkinter 전용 변수 (main_app.py에서 root 생성 후 초기화될 예정)
global_search_query_ai = None
global_search_query_raw = None
global_search_query_saved = None