# ui_builders.py

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
# --- [main_app.py에서 이동된 UI 렌더링 함수들] ---
# 

def update_ai_summary_tab(parent_frame, ai_summary_json, raw_tabs_data, raw_windows):
    """(탭 1) "관련 작업" 탭 UI 갱신"""
    print(f"[DEBUG] 'AI 요약 탭' UI 재생성... (선택 {len(app_state.selected_items_set)}개 복원)")
    
    all_toggles = []
    
    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    url_lookup = {tab['title']: tab['url'] for tab in raw_tabs_data}
    current_tab_titles = list(url_lookup.keys())
    
    top_controls_frame = ttk.Frame(container)
    
    # --- [수정] ---
    # 상단 여백을 10으로 다시 설정
    top_controls_frame.pack(fill=X, padx=5, pady=(10, 10)) 
    # --- [수정 끝] ---

    button_frame = ttk.Frame(top_controls_frame)
    button_frame.pack(side=LEFT)

    tab_select_all_btn = ttk.Button(
        button_frame, text="탭 전체 선택", bootstyle="info",
        command=lambda js=ai_summary_json: on_select_all_in_ai_tab(js)
    )
    tab_select_all_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_deselect_all_btn = ttk.Button(
        button_frame, text="탭 전체 해제", bootstyle="warning",
        command=lambda js=ai_summary_json: on_deselect_all_in_ai_tab(js)
    )
    tab_deselect_all_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_collapse_all_btn = ttk.Button(
        button_frame, text="전체 접기", bootstyle="light",
    )
    tab_collapse_all_btn.pack(side=LEFT, padx=(5, 5))
    
    tab_expand_all_btn = ttk.Button(
        button_frame, text="전체 열기", bootstyle="light",
    )
    tab_expand_all_btn.pack(side=LEFT, padx=(0, 5))

    search_frame = ttk.Frame(top_controls_frame)
    search_frame.pack(side=RIGHT, fill=X, expand=True)

    search_label = ttk.Label(search_frame, text="검색:")
    search_label.pack(side=LEFT, padx=(5, 5)) 
    
    refresh_btn = ttk.Button(
        search_frame, 
        text="🔄", 
        width=2, 
        bootstyle="light",
        command=on_force_ai_refresh
    )
    refresh_btn.pack(side=RIGHT, padx=(5, 0))
    
    search_entry = ttk.Entry(search_frame, textvariable=app_state.global_search_query_ai)
    search_entry.pack(side=LEFT, fill=X, expand=True)
    
    search_entry.bind("<Return>", lambda e: on_search_enter(e, 'ai'))
    
    ttk.Separator(container).pack(fill=X, padx=5, pady=5)

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
            
            hydrated_group_data = json.loads(json.dumps(category_group))
            hydrated_items_list = [] 
            for title in items_titles_only:
                item_url = url_lookup.get(title) 
                if item_url:
                    hydrated_items_list.append({"type": "tab", "title": title, "url": item_url})
                elif title in raw_windows:
                    hydrated_items_list.append({"type": "window", "title": title})
                else:
                    hydrated_items_list.append({"type": "unknown", "title": title})
            hydrated_group_data['items'] = hydrated_items_list
            
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
                    icon = "•" 
                    if item_title in raw_windows: icon = "🖥️"
                    elif item_title in current_tab_titles: icon = "🌐"
                    
                    item_frame = ttk.Frame(inner_content_frame) 
                    item_frame.pack(fill=X, padx=10) 
                    
                    var = tk.BooleanVar()
                    if item_title in app_state.selected_items_set:
                        var.set(True)
                    chk = ttk.Checkbutton(
                        item_frame,
                        variable=var,
                        command=lambda t=item_title, v=var: on_item_check(t, v)
                    )
                    chk.pack(side=LEFT, padx=(5,0))
                    
                    close_button = ttk.Button(
                        item_frame, text="X", bootstyle="danger-outline", width=2,
                        command=lambda title=item_title: on_close_item_click(title)
                    )
                    close_button.pack(side=RIGHT, padx=5)

                    icon_label = ttk.Label(item_frame, text=icon, width=2, anchor="center")
                    icon_label.pack(side=LEFT, padx=(0, 2))
                    
                    text_label = ttk.Label(
                        item_frame, text=item_title, 
                        font=("Arial", 10), cursor="hand2"
                    )
                    text_label.pack(side=LEFT, anchor="w", padx=(0, 5)) 
                    text_label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))
            
            toggle_btn.config(command=lambda f=inner_content_frame, b=toggle_btn: toggle_frame(f, b))
            
            all_toggles.append((inner_content_frame, toggle_btn))

    tab_collapse_all_btn.config(command=lambda tl=all_toggles: on_collapse_all_groups(tl))
    tab_expand_all_btn.config(command=lambda tl=all_toggles: on_expand_all_groups(tl))


def update_raw_list_tab(parent_frame, raw_tabs_data, raw_windows):
    """(탭 2) "전체 목록" 탭 UI 갱신"""
    print(f"[DEBUG] '전체 목록 탭' UI 재생성... (선택 {len(app_state.selected_items_set)}개 복원)")
    
    all_toggles = []
    
    for widget in parent_frame.winfo_children():
        widget.destroy()
    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container

    top_controls_frame = ttk.Frame(container)
    
    # --- [수정] ---
    # 상단 여백을 10으로 다시 설정
    top_controls_frame.pack(fill=X, padx=5, pady=(10, 10))
    # --- [수정 끝] ---

    button_frame = ttk.Frame(top_controls_frame)
    button_frame.pack(side=LEFT)

    tab_select_all_btn = ttk.Button(
        button_frame, text="탭 전체 선택", bootstyle="info",
        command=lambda tabs=raw_tabs_data, wins=raw_windows: on_select_all_in_raw_tab(tabs, wins)
    )
    tab_select_all_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_deselect_all_btn = ttk.Button(
        button_frame, text="탭 전체 해제", bootstyle="warning",
        command=lambda tabs=raw_tabs_data, wins=raw_windows: on_deselect_all_in_raw_tab(tabs, wins)
    )
    tab_deselect_all_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_collapse_all_btn = ttk.Button(
        button_frame, text="전체 접기", bootstyle="light",
    )
    tab_collapse_all_btn.pack(side=LEFT, padx=(5, 5))
    
    tab_expand_all_btn = ttk.Button(
        button_frame, text="전체 열기", bootstyle="light",
    )
    tab_expand_all_btn.pack(side=LEFT, padx=(0, 5))

    search_frame = ttk.Frame(top_controls_frame)
    search_frame.pack(side=RIGHT, fill=X, expand=True)
    
    search_label = ttk.Label(search_frame, text="검색:")
    search_label.pack(side=LEFT, padx=(5, 5))
    
    search_entry = ttk.Entry(search_frame, textvariable=app_state.global_search_query_raw)
    search_entry.pack(side=LEFT, fill=X, expand=True)
    search_entry.bind("<Return>", lambda e: on_search_enter(e, 'raw'))
    
    ttk.Separator(container).pack(fill=X, padx=5, pady=5)

    # --- (검색 필터링 동일) ---
    query = app_state.global_search_query_raw.get().lower()
    filtered_windows = raw_windows
    filtered_tabs = raw_tabs_data
    
    if query:
        print(f"  -> '전체 목록' 탭 '{query}'로 필터링")
        filtered_windows = [w for w in raw_windows if query in w.lower()]
        filtered_tabs = [t for t in raw_tabs_data if query in t['title'].lower()]

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
            item_frame = ttk.Frame(prog_items_frame) 
            item_frame.pack(fill=X, padx=10)
            
            var = tk.BooleanVar()
            if item_title in app_state.selected_items_set:
                var.set(True)
            chk = ttk.Checkbutton(
                item_frame, 
                variable=var,
                command=lambda t=item_title, v=var: on_item_check(t, v)
            )
            chk.pack(side=LEFT, padx=(5,0))
            
            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item_title: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)

            icon_label = ttk.Label(item_frame, text="🖥️", width=2, anchor="center")
            icon_label.pack(side=LEFT, padx=(0, 2))
            
            text_label = ttk.Label(item_frame, text=item_title, font=("Arial", 10), cursor="hand2") 
            text_label.pack(side=LEFT, anchor="w", padx=(0, 5))
            text_label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))
            
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
            item_frame = ttk.Frame(tab_items_frame) 
            item_frame.pack(fill=X, padx=10)
            
            var = tk.BooleanVar()
            if item_title in app_state.selected_items_set:
                var.set(True)
            chk = ttk.Checkbutton(
                item_frame, 
                variable=var,
                command=lambda t=item_title, v=var: on_item_check(t, v)
            )
            chk.pack(side=LEFT, padx=(5,0))

            close_button = ttk.Button(
                item_frame, text="X", bootstyle="danger-outline", width=2,
                command=lambda title=item_title: on_close_item_click(title) 
            )
            close_button.pack(side=RIGHT, padx=5)

            icon_label = ttk.Label(item_frame, text="🌐", width=2, anchor="center")
            icon_label.pack(side=LEFT, padx=(0, 2))
            
            text_label = ttk.Label(item_frame, text=item_title, font=("Arial", 10), cursor="hand2")
            text_label.pack(side=LEFT, anchor="w", padx=(0, 5))
            text_label.bind("<Button-1>", lambda e, t=item_title: on_item_click(t, raw_windows))
            
    tab_toggle_btn.config(command=lambda f=tab_items_frame, b=tab_toggle_btn: toggle_frame(f, b))
    all_toggles.append((tab_items_frame, tab_toggle_btn))

    tab_collapse_all_btn.config(command=lambda tl=all_toggles: on_collapse_all_groups(tl))
    tab_expand_all_btn.config(command=lambda tl=all_toggles: on_expand_all_groups(tl))


def update_saved_sessions_tab(parent_frame):
    """(탭 3) "저장된 작업" 탭 UI 갱신 (기본값 접힘)"""
    print(f"[DEBUG] '저장된 작업 탭' UI 재생성...")
    
    all_toggles = []

    for widget in parent_frame.winfo_children():
        widget.destroy()

    scroll_tab = ScrollableTab(parent_frame, padding=0)
    scroll_tab.pack(fill=BOTH, expand=YES)
    container = scroll_tab.container 

    top_controls_frame = ttk.Frame(container)
    
    # --- [수정] ---
    # 상단 여백을 10으로 다시 설정
    top_controls_frame.pack(fill=X, padx=5, pady=(10, 10))
    # --- [수정 끝] ---

    button_frame = ttk.Frame(top_controls_frame)
    button_frame.pack(side=LEFT)

    tab_collapse_all_btn = ttk.Button(
        button_frame, text="전체 접기", bootstyle="light",
    )
    tab_collapse_all_btn.pack(side=LEFT, padx=(0, 5))
    
    tab_expand_all_btn = ttk.Button(
        button_frame, text="전체 열기", bootstyle="light",
    )
    tab_expand_all_btn.pack(side=LEFT, padx=(0, 5))

    search_frame = ttk.Frame(top_controls_frame)
    search_frame.pack(side=RIGHT, fill=X, expand=True)

    search_label = ttk.Label(search_frame, text="검색:")
    search_label.pack(side=LEFT, padx=(5, 5))
    
    search_entry = ttk.Entry(search_frame, textvariable=app_state.global_search_query_saved)
    search_entry.pack(side=LEFT, fill=X, expand=True)
    search_entry.bind("<Return>", lambda e: on_search_enter(e, 'saved'))
    
    ttk.Separator(container).pack(fill=X, padx=5, pady=5)

    # --- (검색 필터링 동일) ...
    saved_sessions = load_sessions()
    query = app_state.global_search_query_saved.get().lower()
    filtered_sessions = saved_sessions
    
    if query:
        print(f"  -> '저장된 작업' 탭 '{query}'로 필터링")
        filtered_sessions = []
        
        def item_matches(item, query):
            if isinstance(item, dict):
                return query in item.get('title', '').lower()
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
        for session_group in reversed(filtered_sessions):
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

                    if isinstance(item_data, dict):
                        item_type = item_data.get('type', 'unknown')
                        item_title = item_data.get('title', '제목 없음')
                        
                        if item_type == 'tab':
                            icon = "🌐"
                            item_url = item_data.get('url')
                            if item_url: 
                                is_restorable = True 
                        elif item_type == 'window':
                            icon = "🖥️"
                            is_restorable = True 
                    else:
                        item_title = str(item_data) 
                        icon = "❓" 

                    icon_label = ttk.Label(item_list_frame, text=icon, width=2, anchor="center")
                    icon_label.pack(side=LEFT, padx=(10, 2))
                    
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

    tab_collapse_all_btn.config(command=lambda tl=all_toggles: on_collapse_all_groups(tl))
    tab_expand_all_btn.config(command=lambda tl=all_toggles: on_expand_all_groups(tl))


def toggle_frame(frame, button):
    """(접기/펴기 콜백)"""
    if frame.winfo_ismapped():
        frame.pack_forget()
        button.config(text="▶") 
    else:
        frame.pack(fill=X, anchor="w", padx=0, pady=(5,0))
        button.config(text="▼")

# --- [신규 기능] ---
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
# --- [신규 기능 끝] ---