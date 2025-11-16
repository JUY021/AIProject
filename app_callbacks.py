# app_callbacks.py

import json
from tkinter import simpledialog
from tkinter import filedialog
from datetime import datetime

# 전역 상태 및 유틸리티 import
import app_state
from window_utils import close_window_by_title, activate_window_by_title
from session_utils import save_session, load_sessions, overwrite_sessions
from program_mapper import launch_program_by_title

# 
# --- [main_app.py에서 이동된 모든 on_... 함수들] ---
# 

def on_item_click(title, raw_windows):
    """(항목 활성화/이동 콜백)"""
    print(f"'{title}' 항목 클릭됨 (이동 요청)")
    if title in raw_windows:
        success = activate_window_by_title(title)
        if not success:
            print("창 활성화 실패 (이미 닫혔거나 권한 부족)")
    else:
        app_state.command_queue.put({ "action": "activate_tab", "title": title })

def on_close_item_click(title):
    """(개별 닫기 콜백)"""
    print(f"'{title}' 항목 닫기 요청...")
    close_window_by_title(title)
    app_state.command_queue.put({ "action": "close_tab", "title": title })

def on_close_group_click(items_list):
    """(그룹 닫기 콜백)"""
    print(f"'{len(items_list)}'개 항목의 그룹 전체 닫기 요청...")
    if not items_list: return
    for title in items_list:
        on_close_item_click(title)

def on_save_group_click(group_data):
    """(그룹 저장 콜백)"""
    category = group_data.get('category', '알 수 없음')
    print(f"'{category}' 그룹 저장 요청 (URL 포함)...")
    success = save_session(group_data)
    if success:
        print(f"'{category}' 그룹 저장 완료. '저장된 탭' 갱신을 요청합니다.")
        app_state.ui_queue.put({'type': 'refresh_saved_tab'})
    else:
        print(f"'{category}' 그룹 저장 실패.")

def on_restore_group_click(items_data):
    """(그룹 복원 콜백)"""
    print(f"'{len(items_data)}'개 항목의 그룹 복원 요청...")
    if not items_data: return
    count = 0
    for item in items_data:
        if on_restore_item_click(item, is_group_call=True):
             count += 1
    print(f"총 {count}개의 항목 (탭/프로그램) 복원 명령을 전송/실행했습니다.")


def on_restore_item_click(item_data, is_group_call=False):
    """(개별 복원 콜백)"""
    if not is_group_call:
        print(f"[개별 복원] 요청...")
    if isinstance(item_data, dict): 
        item_type = item_data.get('type')
        if item_type == 'tab' and item_data.get('url'):
            url_to_open = item_data.get('url')
            if not is_group_call: print(f"  -> [탭 복원] {url_to_open}")
            app_state.command_queue.put({"action": "open_tab", "url": url_to_open})
            return True
        elif item_type == 'window' and item_data.get('title'):
            title = item_data.get('title')
            return launch_program_by_title(title)
        else:
            if not is_group_call: print("  -> [복원 불가] 알 수 없는 데이터 타입입니다.")
            return False
    else:
        if not is_group_call: print(f"  -> [복원 불가] '{item_data}' (URL/타입 정보가 없는 구 버전 데이터, 건너뜀)")
        return False

def on_delete_group_click(group_to_delete):
    """(그룹 삭제 콜백)"""
    category = group_to_delete.get('category', '알 수 없음')
    saved_at_id = group_to_delete.get('saved_at') 
    if not saved_at_id:
        print(f"'{category}' 그룹 삭제 실패: 고유 ID(saved_at)가 없습니다.")
        return
    print(f"'{category}' ({saved_at_id}) 그룹 삭제 요청...")
    all_sessions = load_sessions()
    filtered_sessions = [
        session for session in all_sessions 
        if session.get('saved_at') != saved_at_id
    ]
    if len(filtered_sessions) < len(all_sessions):
        success = overwrite_sessions(filtered_sessions)
        if success:
            print("그룹 삭제 완료. 탭을 갱신합니다.")
            app_state.ui_queue.put({'type': 'refresh_saved_tab'})
        else:
            print("파일 덮어쓰기에 실패하여 삭제를 중단합니다.")
    else:
        print("삭제할 그룹을 찾지 못했습니다.")

def on_item_check(item_title, var):
    """(체크박스 콜백)"""
    if var.get():
        app_state.selected_items_set.add(item_title)
        print(f"[선택] '{item_title}' 추가 (총 {len(app_state.selected_items_set)}개)")
    else:
        if item_title in app_state.selected_items_set:
            app_state.selected_items_set.remove(item_title)
            print(f"[선택] '{item_title}' 제거 (총 {len(app_state.selected_items_set)}개)")
    app_state.ui_queue.put({'type': 'force_live_refresh'})

def on_select_all_in_group(items_titles):
    """(그룹 전체 선택 콜백)"""
    print(f"[선택] {len(items_titles)}개 그룹 전체 선택")
    for title in items_titles:
        app_state.selected_items_set.add(title)
    app_state.ui_queue.put({'type': 'force_live_refresh'}) # UI 갱신

def on_deselect_all_in_group(items_titles):
    """(그룹 전체 해제 콜백)"""
    print(f"[선택] {len(items_titles)}개 그룹 전체 해제")
    for title in items_titles:
        if title in app_state.selected_items_set:
            app_state.selected_items_set.remove(title)
    app_state.ui_queue.put({'type': 'force_live_refresh'}) # UI 갱신

def on_select_all_in_ai_tab(ai_summary_json):
    """('AI 탭' 전체 선택)"""
    print("[선택] '관련 작업' 탭 전체 선택")
    for group in ai_summary_json:
        for title in group.get('items', []):
            app_state.selected_items_set.add(title)
    app_state.ui_queue.put({'type': 'force_live_refresh'})

def on_deselect_all_in_ai_tab(ai_summary_json):
    """('AI 탭' 전체 해제)"""
    print("[선택] '관련 작업' 탭 전체 해제")
    for group in ai_summary_json:
        for title in group.get('items', []):
            if title in app_state.selected_items_set:
                app_state.selected_items_set.remove(title)
    app_state.ui_queue.put({'type': 'force_live_refresh'})

def on_select_all_in_raw_tab(raw_tabs_data, raw_windows):
    """('Raw 탭' 전체 선택)"""
    print("[선택] '전체 목록' 탭 전체 선택")
    for title in raw_windows:
        app_state.selected_items_set.add(title)
    for tab in raw_tabs_data:
        app_state.selected_items_set.add(tab['title'])
    app_state.ui_queue.put({'type': 'force_live_refresh'})

def on_deselect_all_in_raw_tab(raw_tabs_data, raw_windows):
    """('Raw 탭' 전체 해제)"""
    print("[선택] '전체 목록' 탭 전체 해제")
    for title in raw_windows:
        if title in app_state.selected_items_set:
            app_state.selected_items_set.remove(title)
    for tab in raw_tabs_data:
        if tab['title'] in app_state.selected_items_set:
            app_state.selected_items_set.remove(tab['title'])
    app_state.ui_queue.put({'type': 'force_live_refresh'})


def on_save_selected_click(root):
    """(선택 저장 콜백)"""
    if not app_state.selected_items_set:
        print("[선택 저장] 저장할 항목이 없습니다.")
        return
    print(f"[선택 저장] {len(app_state.selected_items_set)}개 항목 저장 시작...")
    group_name = simpledialog.askstring(
        "그룹 이름 입력", 
        "저장할 그룹의 이름을 입력하세요:",
        initialvalue="새로 저장한 그룹",
        parent=root
    )
    if not group_name:
        print("[선택 저장] 사용자가 취소했습니다.")
        return
    
    hydrated_items_list = []
    url_lookup = {tab['title']: tab['url'] for tab in app_state.global_last_raw_tabs_data}
    
    for title in app_state.selected_items_set:
        item_url = url_lookup.get(title)
        if item_url:
            hydrated_items_list.append({"type": "tab", "title": title, "url": item_url})
        elif title in app_state.global_last_raw_windows:
            hydrated_items_list.append({"type": "window", "title": title})
        else:
            hydrated_items_list.append({"type": "unknown", "title": title})
            
    new_group_data = {
        "category": group_name,
        "summary": f"총 {len(hydrated_items_list)}개의 항목을 수동으로 저장함",
        "items": hydrated_items_list
    }
    
    success = save_session(new_group_data)
    if success:
        print("[선택 저장] 저장 완료. '저장된 탭'을 갱신합니다.")
        app_state.ui_queue.put({'type': 'refresh_saved_tab'})
        app_state.selected_items_set.clear()
        app_state.ui_queue.put({'type': 'force_live_refresh'})
    else:
        print("[선택 저장] 파일 저장에 실패했습니다.")

def on_close_selected_click():
    """(선택 닫기 콜백)"""
    if not app_state.selected_items_set:
        print("[선택 닫기] 선택된 항목이 없습니다.")
        return
    
    print(f"[선택 닫기] {len(app_state.selected_items_set)}개 항목 닫기 시작...")
    items_to_close = list(app_state.selected_items_set)
    for title in items_to_close:
        on_close_item_click(title)
        
    app_state.selected_items_set.clear()
    app_state.ui_queue.put({'type': 'force_live_refresh'})

def on_search_enter(event, tab_name):
    """(신규) 검색창에서 Enter키를 누르면 UI 갱신을 요청합니다."""
    print(f"[검색] {tab_name} 탭 검색 실행...")
    if tab_name == 'saved':
        app_state.ui_queue.put({'type': 'refresh_saved_tab'})
    else:
        app_state.ui_queue.put({'type': 'force_live_refresh'})

def on_force_ai_refresh():
    """(신규) '관련 작업' 탭의 새로고침 버튼 콜백"""
    print("[Refresh] AI 그룹 갱신을 수동으로 요청합니다.")
    # check_queue가 이 메시지를 받고 job_queue에 작업을 넣도록 함
    app_state.ui_queue.put({'type': 'force_ai_refresh'})

def on_export_group_click(group_data):
    """(신규) '저장된 탭'의 그룹을 개별 JSON 파일로 내보냅니다."""
    category = group_data.get('category', '저장된_그룹')
    # 파일명으로 부적절한 문자 제거
    default_filename = "".join(
        c for c in category if c.isalnum() or c in (' ', '_', '-')
    ).rstrip() + ".json"

    print(f"'{category}' 그룹 내보내기 요청...")

    file_path = filedialog.asksaveasfilename(
        title=f"'{category}' 그룹 저장 위치 선택",
        initialfile=default_filename,
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

    if not file_path:
        print("  -> 사용자가 내보내기를 취소했습니다.")
        return

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            # 단일 그룹 객체만 파일에 씀 (리스트 아님)
            json.dump(group_data, f, ensure_ascii=False, indent=4)
        print(f"  -> 그룹을 '{file_path}'에 성공적으로 저장했습니다.")
    except Exception as e:
        print(f"  -> 파일 저장 중 오류 발생: {e}")

def on_import_session_click(root):
    """(신규) '내보낸' 세션 JSON 파일을 불러와 '저장된 탭'에 추가합니다."""
    print("세션 가져오기 요청...")

    file_paths = filedialog.askopenfilenames(
        title="가져올 세션 파일 선택 (여러 개 선택 가능)",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        parent=root
    )

    if not file_paths:
        print("  -> 사용자가 가져오기를 취소했습니다.")
        return

    imported_count = 0
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            groups_to_process = []
            
            # [수정] 불러온 데이터가 '단일 그룹(dict)'인지 '전체 백업(list)'인지 확인
            if isinstance(loaded_data, dict):
                # 단일 그룹 파일
                groups_to_process.append(loaded_data)
            elif isinstance(loaded_data, list):
                # '전체 내보내기' 백업 파일
                print(f"  -> '{file_path}' (전체 백업) 파일을 감지. {len(loaded_data)}개 그룹 처리를 시도합니다.")
                groups_to_process = loaded_data
            else:
                # 유효하지 않은 형식
                print(f"  -> '{file_path}'는 유효한 세션 파일 형식이 아닙니다 (건너뜀).")
                continue # 다음 파일로
            
            # [수정] 식별된 그룹 목록을 순회하며 저장
            for group_data in groups_to_process:
                if isinstance(group_data, dict) and 'category' in group_data:
                    # session_utils.save_session을 재사용하여 리스트에 추가
                    if save_session(group_data):
                        imported_count += 1
                        print(f"    -> '{group_data.get('category')}' 그룹 가져오기 성공.")
                    else:
                        print(f"    -> '{group_data.get('category')}' 저장 실패 (save_session 오류)")
                else:
                    print(f"    -> 파일 내에 유효하지 않은 그룹 데이터가 있습니다 (건너뜀).")

        except Exception as e:
            print(f"  -> '{file_path}' 파일 읽기/처리 중 오류 발생: {e}")
            
    if imported_count > 0:
        print(f"총 {imported_count}개의 그룹을 가져왔습니다. 탭을 갱신합니다.")
        app_state.ui_queue.put({'type': 'refresh_saved_tab'})

def on_export_all_sessions_click(root):
    """(신규) '저장된 탭'의 *모든* 그룹을 단일 JSON 파일로 내보냅니다."""
    print("모든 세션 내보내기 요청...")
    
    all_sessions = load_sessions()
    if not all_sessions:
        print("  -> 내보낼 세션이 없습니다.")
        # (Optional: Show a message box to the user)
        # from tkinter import messagebox
        # messagebox.showinfo("내보내기", "내보낼 세션이 없습니다.", parent=root)
        return

    default_filename = f"WorkDash_백업_{datetime.now().strftime('%Y%m%d')}.json"
    
    file_path = filedialog.asksaveasfilename(
        title="모든 세션 백업 위치 선택",
        initialfile=default_filename,
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        parent=root
    )
    
    if not file_path:
        print("  -> 사용자가 내보내기를 취소했습니다.")
        return

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            # (중요) 세션 *리스트* 전체를 파일에 씀
            json.dump(all_sessions, f, ensure_ascii=False, indent=4)
        print(f"  -> {len(all_sessions)}개 그룹을 '{file_path}'에 성공적으로 저장했습니다.")
    except Exception as e:
        print(f"  -> 파일 저장 중 오류 발생: {e}")