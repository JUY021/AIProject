# window_utils.py

import pygetwindow as gw

def get_open_windows():
    """pygetwindow를 사용해 현재 열린 모든 창의 제목을 가져옵니다."""
    window_titles = []
    try:
        for window in gw.getAllWindows():
            if window.title: # 모든 창 (최소화 포함)
                window_titles.append(window.title)
    except Exception as e:
        print(f"[pygetwindow 오류] {e}")
    
    # 중복 제거
    return list(set(window_titles))

# -------------------------------------------------------------------
# 프로그램을 닫는 함수
# -------------------------------------------------------------------
def close_window_by_title(title_to_close):
    """제목과 일치하는 첫 번째 창을 닫습니다."""
    try:
        # 제목으로 창을 찾습니다. (리스트가 반환될 수 있음)
        windows = gw.getWindowsWithTitle(title_to_close)
        if windows:
            # 첫 번째로 찾은 창을 닫습니다.
            window_to_close = windows[0]
            window_to_close.close()
            print(f"'{title_to_close}' 창을 닫았습니다.")
            return True
        else:
            print(f"'{title_to_close}' 창을 찾을 수 없습니다.")
            return False
    except Exception as e:
        print(f"[창 닫기 오류] {e}")
        return False