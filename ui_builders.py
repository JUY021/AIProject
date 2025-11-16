# ui_builders.py
# (기능 3개 추가 완료)

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import json
from datetime import datetime

# 전역 상태, 콜백, 커스텀 위젯 import
import app_state
from app_callbacks import *
from ui_components import ScrollableTab
from session_utils import load_sessions

# 
# --- [신규] 브라우저 아이콘/스타일 매핑 헬퍼 ---
#
def get_browser_icon_and_style(browser_name_raw):
    """브라우저 이름(소문자)을 받아 아이콘(이모지)과 스타일 이름을 반환"""
    b = browser_name_raw.lower()
    
    if 'chrome' in b:
        return "🌍", "ChromeIcon.TLabel" # (아이콘, 스타일)
    elif 'firefox' in b:
        return "🔥", "FirefoxIcon.TLabel"
    elif 'edge' in b:
        return "🌐", "EdgeIcon.TLabel" # (기본 🌐 아이콘 사용)
    else:
        # 'unknown' 또는 기타
        return "🌐", "DefaultBrowserIcon.TLabel" 


# 
# --- [main_app.py에서 이동된 UI 렌더링 함수들] ---
# 

def update_ai_summary_tab(parent_frame, root, ai_summary_json, raw_tabs_data, raw_windows):
    """(탭 1) "관련 작업" 탭 UI 갱신"""
    
    all_toggles = []
    
    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    # --- [신규] 'AI 요약 중' 상태 표시 ---
    if app_state.global_is_ai_summarizing and app_state.global_is_ai_summarizing.get():
        print("[DEBUG] 'AI 요약 탭' UI: '요약 중' 화면 표시...")
        loading_frame = ttk.Frame(container, padding=20)
        loading_frame.pack(fill=BOTH, expand=YES, anchor=CENTER)
        
        ttk.Label(
            loading_frame, 
            text="AI가 작업을 요약하는 중입니다...", 
            font=("Arial", 14, "bold"),
            bootstyle="info"
        ).pack(pady=10, anchor=CENTER)
        
        # ttk.Label(
        #     loading_frame, 
        #     text="(최대 15초 소요)", 
        #     font=("Arial", 10, "italic"),
        #     bootstyle="secondary"
        # ).pack(pady=5, anchor=CENTER)
        
        pb = ttk.Progressbar(loading_frame, mode='indeterminate', bootstyle="info")
        pb.pack(fill=X, padx=50, pady=10, anchor=CENTER)
        pb.start(10) # 10ms 간격으로 이동
        
        return # '요약 중' 화면을 표시하고 나머지 UI 렌더링 중단
    # --- [신규 끝] ---
    
    print(f"[DEBUG] 'AI 요약 탭' UI 재생성... (선택 {len(app_state.selected_items_set)}개 복원)")

    # [수정] URL뿐 아니라 'browser' 정보도 조회할 수 있도록 전체 tab 객체를 저장
    tab_lookup = {tab['title']: tab for tab in raw_tabs_data}
    
    # --- [수정] 헬퍼 함수로 상단 컨트롤 생성 ---
    create_tab_top_controls(
        container,
        root, # [수정] root 전달
        search_var=app_state.global_search_query_ai,
        search_tab_name='ai',
        all_toggles_list=all_toggles,
        on_select_all_cb=lambda js=ai_summary_json: on_select_all_in_ai_tab(js),
        on_deselect_all_cb=lambda js=ai_summary_json: on_deselect_all_in_ai_tab(js),
        on_force_refresh_cb=on_force_ai_refresh
    )
    # --- [수정 끝] ---

    # --- (검색 필터링, 그룹 생성 루프 ... 동일) ---
    query = app_state.global_search_query_ai.get().lower()
    filtered_summary = ai_summary_json
    
    if query:
        print(f"  -> 'AI 요약' 탭 '{query}'로 필터링")
        filtered_summary = []
        for group in ai_summary_json:
            if (query in group.get('category', '').lower() or
                query in group.get('summary', '').lower() or
                any(query in item.lower() for item in group.get('items', []))):
                filtered_summary.append(group)

    if not filtered_summary:
        if query:
            ttk.Label(container, text=f"'{query}'에 대한 검색 결과가 없습니다.", font=("Arial", 12)).pack(pady=10)
        else:
            ttk.Label(container, text="요약할 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for category_group in filtered_summary:
            category_name = category_group.get('category', '알 수 없음')
            summary = category_group.get('summary', '요약 없음')
            items_titles_only = category_group.get('items', [])

            group_frame = ttk.Labelframe(
                master=container, text=category_name,
                style="Custom.TLabelframe", padding=10
            )
            group_frame.pack(fill=X, pady=5, padx=5)

            top_frame = ttk.Frame(group_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)
            
            toggle_btn = ttk.Button(
                top_frame, text="▼", bootstyle="light-outline", width=2
            )
            toggle_btn.pack(side=LEFT, padx=(0, 5), pady=(0, 10))
            
            summary_label = ttk.Label(
                top_frame, text=summary, 
                font=("Arial", 10, "italic"), wraplength=300
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            # (Hydration 로직)
            hydrated_group_data = json.loads(json.dumps(category_group))
            hydrated_items_list = [] 
            for title in items_titles_only:
                tab_info = tab_lookup.get(title) # [수정]
                if tab_info: # 탭인 경우
                    hydrated_items_list.append({
                        "type": "tab", 
                        "title": title, 
                        "url": tab_info.get('url'),
                        "browser": tab_info.get('browser', 'unknown') # [신규]
                    })
                elif title in raw_windows: # 창인 경우
                    hydrated_items_list.append({"type": "window", "title": title})
                else: # 알 수 없는 경우
                    hydrated_items_list.append({"type": "unknown", "title": title})
            hydrated_group_data['items'] = hydrated_items_list
            
            # (그룹 버튼)
            group_close_button = ttk.Button(
                top_frame, text="그룹 닫기", bootstyle="danger-outline", width=8,
                command=lambda current_items=items_titles_only: on_close_group_click(current_items)
            )
            group_close_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            group_save_button = ttk.Button(
                top_frame, text="그룹 저장", bootstyle="success-outline", width=8,
                command=lambda data=hydrated_group_data: on_save_group_click(data)
            )
            group_save_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            deselect_all_btn = ttk.Button(
                top_frame, text="그룹 해제", bootstyle="warning-outline", width=8,
                command=lambda items=items_titles_only: on_deselect_all_in_group(items)
            )
            deselect_all_btn.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            select_all_btn = ttk.Button(
                top_frame, text="그룹 선택", bootstyle="info-outline", width=8,
                command=lambda items=items_titles_only: on_select_all_in_group(items)
            )
            select_all_btn.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))

            inner_content_frame = ttk.Frame(group_frame)
            inner_content_frame.pack(fill=X, padx=0, pady=0) # 기본값 펼침

            if not items_titles_only:
                ttk.Label(inner_content_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item_title in items_titles_only:
                    
                    # --- [신규] 아이콘 및 스타일 결정 로직 ---
                    icon = "•"
                    icon_style = "Icon.TLabel" # 기본값
                    
                    if item_title in raw_windows: 
                        icon = "🖥️"
                    elif item_title in tab_lookup:
                        browser = tab_lookup[item_title].get('browser', 'unknown')
                        icon, icon_style = get_browser_icon_and_style(browser)
                    # --- [신규 끝] ---
                        
                    
                    # --- [수정] 헬퍼 함수로 항목 생성 ---
                    create_live_item_row(
                        inner_content_frame, 
                        item_title, 
                        icon,
                        icon_style, # [신규] 스타일 전달
                        raw_windows
                    )
                    # --- [수정 끝] ---
            
            toggle_btn.config(command=lambda f=inner_content_frame, b=toggle_btn: toggle_frame(f, b))
            all_toggles.append((inner_content_frame, toggle_btn))

    # (전체 접기/펴기 버튼 command 설정은 헬퍼 함수 내부로 이동됨)


def update_raw_list_tab(parent_frame, root, raw_tabs_data, raw_windows):
    """(탭 2) "전체 목록" 탭 UI 갱신"""
    print(f"[DEBUG] '전체 목록 탭' UI 재생성... (선택 {len(app_state.selected_items_set)}개 복원)")
    
    all_toggles = []
    
    for widget in parent_frame.winfo_children():
        widget.destroy()
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container

    # --- [수정] 헬퍼 함수로 상단 컨트롤 생성 ---
    create_tab_top_controls(
        container,
        root, # [수정] root 전달
        search_var=app_state.global_search_query_raw,
        search_tab_name='raw',
        all_toggles_list=all_toggles,
        on_select_all_cb=lambda tabs=raw_tabs_data, wins=raw_windows: on_select_all_in_raw_tab(tabs, wins),
        on_deselect_all_cb=lambda tabs=raw_tabs_data, wins=raw_windows: on_deselect_all_in_raw_tab(tabs, wins)
    )
    # --- [수정 끝] ---

    # --- (검색 필터링 동일) ---
    query = app_state.global_search_query_raw.get().lower()
    filtered_windows = raw_windows
    filtered_tabs = raw_tabs_data
    
    if query:
        print(f"  -> '전체 목록' 탭 '{query}'로 필터링")
        filtered_windows = [w for w in raw_windows if query in w.lower()]
        filtered_tabs = [
            t for t in raw_tabs_data 
            if query in t['title'].lower() or query in t['url'].lower()
        ]

    # (프로그램 창 부분)
    prog_frame = ttk.Labelframe(
        container, text="프로그램 창", style="Custom.TLabelframe", padding=10
    )
    prog_frame.pack(fill=X, pady=5, padx=5)
    
    prog_btn_frame = ttk.Frame(prog_frame)
    prog_btn_frame.pack(fill=X, padx=10, pady=(0, 5))
    
    prog_toggle_btn = ttk.Button(
        prog_btn_frame, text="▼", bootstyle="light-outline", width=2
    )
    prog_toggle_btn.pack(side=LEFT, padx=(0, 5))
    
    prog_deselect_all_btn = ttk.Button(
        prog_btn_frame, text="그룹 해제", bootstyle="warning-outline",
        command=lambda items=filtered_windows: on_deselect_all_in_group(items)
    )
    prog_deselect_all_btn.pack(side=RIGHT)
    
    prog_select_all_btn = ttk.Button(
        prog_btn_frame, text="그룹 선택", bootstyle="info-outline",
        command=lambda items=filtered_windows: on_select_all_in_group(items)
    )
    prog_select_all_btn.pack(side=RIGHT, padx=(0, 5))
    
    prog_items_frame = ttk.Frame(prog_frame)
    prog_items_frame.pack(fill=X, padx=0, pady=0) # 기본값 펼침
    
    if not filtered_windows:
        ttk.Label(prog_items_frame, text="- 열린 프로그램이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for item_title in filtered_windows:
            # --- [수정] 헬퍼 함수로 항목 생성 ---
            create_live_item_row(
                prog_items_frame,
                item_title,
                "🖥️",
                "Icon.TLabel", # [신규] 스타일 전달
                raw_windows
            )
            # --- [수정 끝] ---
            
    prog_toggle_btn.config(command=lambda f=prog_items_frame, b=prog_toggle_btn: toggle_frame(f, b))
    all_toggles.append((prog_items_frame, prog_toggle_btn))

    # (브라우저 탭 부분)
    tab_frame = ttk.Labelframe(
        container, text="브라우저 탭", style="Custom.TLabelframe", padding=10
    )
    tab_frame.pack(fill=X, pady=5, padx=5)
    
    tab_btn_frame = ttk.Frame(tab_frame)
    tab_btn_frame.pack(fill=X, padx=10, pady=(0, 5))
    
    tab_toggle_btn = ttk.Button(
        tab_btn_frame, text="▼", bootstyle="light-outline", width=2
    )
    tab_toggle_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_titles_only = [tab['title'] for tab in filtered_tabs]
    
    tab_deselect_all_btn = ttk.Button(
        tab_btn_frame, text="그룹 해제", bootstyle="warning-outline",
        command=lambda items=tab_titles_only: on_deselect_all_in_group(items)
    )
    tab_deselect_all_btn.pack(side=RIGHT)
    
    tab_select_all_btn = ttk.Button(
        tab_btn_frame, text="그룹 선택", bootstyle="info-outline",
        command=lambda items=tab_titles_only: on_select_all_in_group(items)
    )
    tab_select_all_btn.pack(side=RIGHT, padx=(0, 5))
    
    tab_items_frame = ttk.Frame(tab_frame)
    tab_items_frame.pack(fill=X, padx=0, pady=0) # 기본값 펼침
    
    if not filtered_tabs:
        ttk.Label(tab_items_frame, text="- 열린 탭이 없습니다 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
    else:
        for tab_dict in filtered_tabs:
            item_title = tab_dict['title']
            
            # --- [신규] 아이콘 및 스타일 결정 로직 ---
            browser = tab_dict.get('browser', 'unknown')
            icon, icon_style = get_browser_icon_and_style(browser)
            # --- [신규 끝] ---
            
            # --- [수정] 헬퍼 함수로 항목 생성 ---
            create_live_item_row(
                tab_items_frame,
                item_title,
                icon,
                icon_style, # [신규] 스타일 전달
                raw_windows
            )
            # --- [수정 끝] ---
            
    tab_toggle_btn.config(command=lambda f=tab_items_frame, b=tab_toggle_btn: toggle_frame(f, b))
    all_toggles.append((tab_items_frame, tab_toggle_btn))

    # (전체 접기/펴기 버튼 command 설정은 헬퍼 함수 내부로 이동됨)


def update_saved_sessions_tab(parent_frame, root):
    """
    (탭 3) "저장된 작업" 탭 UI 갱신 (기본값 접힘)
    [수정] 'root'를 인자로 받아 파일 다이얼로그의 부모로 사용
    """
    print(f"[DEBUG] '저장된 작업 탭' UI 재생성...")
    
    all_toggles = []

    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    # --- [수정] 헬퍼 함수로 상단 컨트롤 생성 ---
    create_tab_top_controls(
        container,
        root, # [수정] root 전달
        search_var=app_state.global_search_query_saved,
        search_tab_name='saved',
        all_toggles_list=all_toggles,
        # [신규] '가져오기' 콜백 전달
        on_import_cb=lambda: on_import_session_click(root)
    )
    # --- [수정 끝] ---

    # --- (검색 필터링 동일) ...
    saved_sessions = load_sessions()
    query = app_state.global_search_query_saved.get().lower()
    filtered_sessions = saved_sessions
    
    if query:
        print(f"  -> '저장된 작업' 탭 '{query}'로 필터링")
        filtered_sessions = []
        
        def item_matches(item, query):
            if isinstance(item, dict):
                title = item.get('title', '').lower()
                url = item.get('url', '').lower()
                return query in title or query in url
            else:
                return query in str(item).lower()
                
        for group in saved_sessions:
            if (query in group.get('category', '').lower() or
                query in group.get('summary', '').lower() or
                any(item_matches(item, query) for item in group.get('items', []))):
                filtered_sessions.append(group)

    if not filtered_sessions:
        if query:
            ttk.Label(container, text=f"'{query}'에 대한 검색 결과가 없습니다.", font=("Arial", 12)).pack(pady=10)
        else:
            ttk.Label(container, text="저장된 작업이 없습니다.", font=("Arial", 12)).pack(pady=10)
    else:
        for session_group in reversed(filtered_sessions): # 최근 항목이 위로
            category_name = session_group.get('category', '알 수 없음')
            summary = session_group.get('summary', '요약 없음')
            items_data = session_group.get('items', []) 
            saved_at_iso = session_group.get('saved_at')
            
            try:
                saved_at_dt = datetime.fromisoformat(saved_at_iso)
                saved_at_str = saved_at_dt.strftime('%Y-%m-%d %H:%M')
            except (ValueError, TypeError, AttributeError):
                saved_at_str = "시간 정보 없음"

            group_frame = ttk.Labelframe(
                master=container,
                text=f"{category_name} ({saved_at_str})",
                style="Custom.TLabelframe",
                padding=10
            )
            group_frame.pack(fill=X, pady=5, padx=5)

            top_frame = ttk.Frame(group_frame)
            top_frame.pack(fill=X, anchor="w", padx=0)

            toggle_btn = ttk.Button(
                top_frame, text="▶", bootstyle="light-outline", width=2
            )
            toggle_btn.pack(side=LEFT, padx=(0, 5), pady=(0, 10))

            summary_label = ttk.Label(
                top_frame, text=summary, 
                font=("Arial", 10, "italic"), wraplength=300 
            )
            summary_label.pack(side=LEFT, anchor="w", fill=X, expand=YES, pady=(0, 10), padx=5)
            
            # --- [신규] '내보내기' 버튼 추가 ---
            export_button = ttk.Button(
                top_frame,
                text="내보내기",
                bootstyle="info-outline",
                width=8,
                command=lambda group=session_group: on_export_group_click(group)
            )
            export_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            # --- [신규 끝] ---
            
            restore_button = ttk.Button(
                top_frame,
                text="그룹 복원",
                bootstyle="primary-outline",
                width=9, 
                command=lambda items=items_data: on_restore_group_click(items)
            )
            restore_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            group_delete_button = ttk.Button(
                top_frame,
                text="그룹 삭제",
                bootstyle="danger-outline",
                width=9,
                command=lambda group=session_group: on_delete_group_click(group)
            )
            group_delete_button.pack(side=RIGHT, padx=(5, 0), pady=(0, 10))
            
            items_frame = ttk.Frame(group_frame)
            # (기본값 닫힘 - pack()을 호출하지 않음)
            
            if not items_data:
                ttk.Label(items_frame, text="- 항목 없음 -", font=("Arial", 10, "italic")).pack(anchor="w", padx=10)
            else:
                for item_data in items_data:
                    item_list_frame = ttk.Frame(items_frame)
                    item_list_frame.pack(fill=X, padx=10) 
                    
                    icon = "•"
                    item_title = ""
                    item_url = None
                    is_restorable = False 
                    icon_style = "SavedIcon.TLabel" # [신규]

                    if isinstance(item_data, dict):
                        item_type = item_data.get('type', 'unknown')
                        item_title = item_data.get('title', '제목 없음')
                        
                        if item_type == 'tab':
                            # [신규] 저장된 탭의 브라우저 아이콘/스타일 결정
                            browser = item_data.get('browser', 'unknown')
                            icon, icon_style = get_browser_icon_and_style(browser)
                            
                            item_url = item_data.get('url')
                            if item_url: 
                                is_restorable = True 
                        elif item_type == 'window':
                            icon = "🖥️"
                            is_restorable = True 
                    else:
                        item_title = str(item_data) 
                        icon = "❓" 

                    # --- [수정] width 제거, style 적용 ---
                    icon_label = ttk.Label(
                        item_list_frame, 
                        text=icon, 
                        anchor="center",
                        style=icon_style
                    )
                    icon_label.pack(side=LEFT, padx=(10, 2))
                    # --- [수정 끝] ---
                    
                    text_label = ttk.Label(
                        item_list_frame, 
                        text=item_title,
                        font=("Arial", 10)
                    )
                    text_label.pack(side=LEFT, anchor="w", padx=(0, 5))
                    
                    if item_url: 
                        url_label = ttk.Label(
                            item_list_frame,
                            text=f"({item_url[:30]}...)", 
                            font=("Arial", 9, "italic"),
                            bootstyle="secondary"
                        )
                        url_label.pack(side=LEFT, anchor="w", padx=5)
                    
                    if is_restorable:
                        restore_item_btn = ttk.Button(
                            item_list_frame,
                            text="복원",
                            bootstyle="info-outline", 
                            width=4,
                            command=lambda item=item_data: on_restore_item_click(item, is_group_call=False)
                        )
                        restore_item_btn.pack(side=RIGHT, padx=5)

            toggle_btn.config(command=lambda f=items_frame, b=toggle_btn: toggle_frame(f, b))
            
            all_toggles.append((items_frame, toggle_btn))

    # (전체 접기/펴기 버튼 command 설정은 헬퍼 함수 내부로 이동됨)


# 
# --- [신규] 재사용 가능한 UI 빌더 헬퍼 함수 ---
# 

def create_tab_top_controls(
    parent_container, 
    root, # [신규] root 추가
    search_var, 
    search_tab_name, 
    all_toggles_list,
    on_select_all_cb=None,
    on_deselect_all_cb=None,
    on_force_refresh_cb=None,
    on_import_cb=None # [신규] 가져오기 콜백
):
    """
    각 탭의 상단 컨트롤 영역(선택, 접기, 검색)을 생성하는 
    재사용 가능한 헬퍼 함수
    """
    top_controls_frame = ttk.Frame(parent_container)
    top_controls_frame.pack(fill=X, padx=5, pady=(10, 10))

    button_frame = ttk.Frame(top_controls_frame)
    button_frame.pack(side=LEFT)

    # 1. (선택적) 전체 선택/해제 버튼
    if on_select_all_cb:
        tab_select_all_btn = ttk.Button(
            button_frame, text="탭 전체 선택", bootstyle="info",
            command=on_select_all_cb
        )
        tab_select_all_btn.pack(side=LEFT, padx=(0, 5))
    
    if on_deselect_all_cb:
        tab_deselect_all_btn = ttk.Button(
            button_frame, text="탭 전체 해제", bootstyle="warning",
            command=on_deselect_all_cb
        )
        tab_deselect_all_btn.pack(side=LEFT, padx=(0, 5))

    # 2. 전체 접기/열기 버튼 (all_toggles_list를 사용)
    tab_collapse_all_btn = ttk.Button(
        button_frame, text="전체 접기", bootstyle="light",
        command=lambda tl=all_toggles_list: on_collapse_all_groups(tl)
    )
    tab_collapse_all_btn.pack(side=LEFT, padx=(5, 5))
    
    tab_expand_all_btn = ttk.Button(
        button_frame, text="전체 열기", bootstyle="light",
        command=lambda tl=all_toggles_list: on_expand_all_groups(tl)
    )
    tab_expand_all_btn.pack(side=LEFT, padx=(0, 5))

    # [신규] 2.5 (선택적) '가져오기' 버튼
    if on_import_cb:
        import_btn = ttk.Button(
            button_frame,
            text="세션 가져오기",
            bootstyle="success-outline",
            command=on_import_cb
        )
        import_btn.pack(side=LEFT, padx=(5, 5))

    # 3. 검색창
    search_frame = ttk.Frame(top_controls_frame)
    search_frame.pack(side=RIGHT, fill=X, expand=True)

    search_label = ttk.Label(search_frame, text="검색:")
    search_label.pack(side=LEFT, padx=(5, 5)) 
    
    # 4. (선택적) 새로고침 버튼
    if on_force_refresh_cb:
        # --- [수정] font=... 대신 style=... 사용 ---
        refresh_btn = ttk.Button(
            search_frame, 
            text="↻", # [수정] 아이콘 변경
            width=2, 
            bootstyle="light-link", # [수정] 테두리 제거
            command=on_force_refresh_cb,
            style="Refresh.TButton" 
        )
        refresh_btn.pack(side=RIGHT, padx=(5, 0))
        # --- [수정 끝] ---
    
    search_entry = ttk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side=LEFT, fill=X, expand=True)
    
    # on_search_enter 콜백 바인딩
    search_entry.bind(
        "<Return>", 
        lambda e, name=search_tab_name: on_search_enter(e, name)
    )
    
    ttk.Separator(parent_container).pack(fill=X, padx=5, pady=5)


def create_live_item_row(parent_frame, item_title, item_icon, icon_style, raw_windows_list):
    """
    '라이브 탭'(AI 요약, 전체 목록)의 개별 항목(행)을 생성하는
    재사용 가능한 헬퍼 함수 (체크박스, 닫기, 클릭 기능 포함)
    [수정] icon_style 추가
    """
    item_frame = ttk.Frame(parent_frame) 
    item_frame.pack(fill=X, padx=10) 
    
    # 1. 체크박스
    var = tk.BooleanVar()
    if item_title in app_state.selected_items_set:
        var.set(True)
    chk = ttk.Checkbutton(
        item_frame,
        variable=var,
        command=lambda t=item_title, v=var: on_item_check(t, v)
    )
    chk.pack(side=LEFT, padx=(5,0))
    
    # 2. 닫기 버튼
    close_button = ttk.Button(
        item_frame, text="X", bootstyle="danger-outline", width=2,
        command=lambda title=item_title: on_close_item_click(title)
    )
    close_button.pack(side=RIGHT, padx=5)

    # 3. 아이콘
    # --- [수정] width 제거, style 적용 ---
    icon_label = ttk.Label(
        item_frame, 
        text=item_icon, 
        anchor="center",
        style=icon_style
        )
    icon_label.pack(side=LEFT, padx=(0, 2))
    # --- [수정 끝] ---
    
    # 4. 클릭 가능한 텍스트 레이블
    text_label = ttk.Label(
        item_frame, text=item_title, 
        font=("Arial", 10), cursor="hand2"
    )
    text_label.pack(side=LEFT, anchor="w", padx=(0, 5)) 
    text_label.bind(
        "<Button-1>", 
        lambda e, t=item_title, w=raw_windows_list: on_item_click(t, w)
    )

# --- [기존 기능] ---

def toggle_frame(frame, button):
    """(접기/펴기 콜백)"""
    if frame.winfo_ismapped():
        frame.pack_forget()
        button.config(text="▶") 
    else:
        frame.pack(fill=X, anchor="w", padx=0, pady=(5,0))
        button.config(text="▼")

def on_collapse_all_groups(toggle_list):
    """리스트에 있는 모든 그룹을 접습니다."""
    print(f"[UI] {len(toggle_list)}개 그룹 전체 접기")
    for frame, button in toggle_list:
        if frame.winfo_ismapped(): # 이미 열려있으면
            frame.pack_forget()
            button.config(text="▶")

def on_expand_all_groups(toggle_list):
    """리스트에 있는 모든 그룹을 엽니다."""
    print(f"[UI] {len(toggle_list)}개 그룹 전체 열기")
    for frame, button in toggle_list:
        if not frame.winfo_ismapped(): # 이미 닫혀있으면
            frame.pack(fill=X, anchor="w", padx=0, pady=(5,0))
            button.config(text="▼")