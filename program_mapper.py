# program_mapper.py
# (새 파일)

import subprocess
import os

# -------------------------------------------------------------------
# [중요] 사용자가 직접 이 사전을 채워야 합니다.
# 
# '창 제목에 포함된 키워드': '실행할 .exe 파일명'
# -------------------------------------------------------------------
PROGRAM_MAP = {
    # 예시:
    "Excel": "excel.exe",
    "메모장": "notepad.exe",
    "Visual Studio Code": "code.exe",
    "계산기": "calc.exe",
    "파일 탐색기": "explorer.exe",
    "cmd.exe": "cmd.exe"
    # (필요한 만큼 여기에 계속 추가...)
}

def launch_program_by_title(title):
    """창 제목을 보고 PROGRAM_MAP에서 일치하는 프로그램을 찾아 실행합니다."""
    
    if not title:
        return False
        
    found_exe = None
    
    # 1. 맵을 순회하며 키워드가 제목에 포함되어 있는지 확인
    for keyword, exe_name in PROGRAM_MAP.items():
        if keyword in title:
            found_exe = exe_name
            break # 첫 번째로 일치하는 것 사용
            
    if found_exe:
        print(f"  -> [프로그램 실행] '{title}'에서 '{found_exe}' 실행 시도...")
        try:
            # 'start' 명령어를 사용하면 전체 경로 없이도 PATH에서 찾아 실행
            subprocess.Popen(
                ["start", found_exe], 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                # 새 콘솔 창이 뜨지 않도록 CREATE_NO_WINDOW 플래그 사용 (Windows)
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return True
        except Exception as e:
            print(f"    -> [오류] {e}")
            return False
    else:
        print(f"  -> [실행 불가] '{title}'에 대해 맵핑된 프로그램이 없습니다.")
        return False