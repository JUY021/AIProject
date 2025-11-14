# session_utils.py
# (새 파일)

import json
import os
from datetime import datetime

# 저장할 파일명
SESSION_FILE = "saved_sessions.json"

def load_sessions():
    """저장된 세션 파일을 읽어 리스트로 반환합니다."""
    if not os.path.exists(SESSION_FILE):
        return [] # 파일이 없으면 빈 리스트 반환
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e:
        print(f"세션 파일({SESSION_FILE}) 로드 오류: {e}")
        return [] # 오류 발생 시 빈 리스트

def save_session(group_data):
    """
    전달받은 'group_data' 딕셔너리(AI가 생성한 그룹)를
    JSON 파일에 추가(append)하여 저장합니다.
    """
    # 1. 기존에 저장된 세션들을 불러옵니다.
    sessions = load_sessions()
    
    # 2. 새 그룹 데이터에 '저장 시각'을 추가합니다.
    group_data['saved_at'] = datetime.now().isoformat()
    
    # 3. 새 그룹을 리스트에 추가합니다.
    sessions.append(group_data)
    
    # 4. 전체 리스트를 파일에 덮어씁니다. (overwrite 함수 재사용)
    return overwrite_sessions(sessions)

# --- [신규 기능] ---
def overwrite_sessions(sessions_list):
    """(신규) 전달받은 전체 세션 리스트를 파일에 덮어씁니다 (삭제/수정용)."""
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions_list, f, ensure_ascii=False, indent=4)
        print(f"세션 파일을 덮어썼습니다. (총 {len(sessions_list)}개 그룹)")
        return True
    except IOError as e:
        print(f"세션 파일({SESSION_FILE}) 덮어쓰기 오류: {e}")
        return False
# --- [신규 기능 끝] ---