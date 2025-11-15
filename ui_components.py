# ui_components.py

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class ScrollableTab(ttk.Frame):
    """
    Canvas, Scrollbar, Mousewheel 바인딩이 모두 포함된
    재사용 가능한 스크롤 탭 클래스입니다.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # 1. 스크롤바 생성
        vscroll = ttk.Scrollbar(self, orient=VERTICAL)
        vscroll.pack(side=RIGHT, fill=Y)

        # 2. 캔버스 생성
        self.canvas = tk.Canvas(self, yscrollcommand=vscroll.set, highlightthickness=0)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=YES)

        # 3. 캔버스와 스크롤바 연결
        vscroll.config(command=self.canvas.yview)

        # 4. 캔버스 내부에 '실제 내용이 들어갈' 프레임 생성
        # 이 container가 ai_summary_container 또는 raw_list_container가 됩니다.
        self.container = ttk.Frame(self.canvas, padding=0)
        self.canvas.create_window((0, 0), window=self.container, anchor="nw")

        # 5. 스크롤 영역 및 너비 자동 업데이트 바인딩
        self.container.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # 6. 마우스 휠 바인딩 (전역 바인딩으로 변경하여 더 안정적임)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add=True)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel, add=True)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel, add=True)

    def _on_frame_configure(self, event):
        """내부 프레임 크기 변경 시 캔버스 스크롤 영역 업데이트"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """캔버스 크기 변경 시 내부 프레임 너비 업데이트"""
        self.canvas.itemconfig(1, width=event.width)

    def _on_mousewheel(self, event):
        """마우스 휠 스크롤 이벤트 처리 (전역)"""
        # 현재 마우스 커서 아래의 위젯이 이 캔버스 소속인지 확인
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is None or not str(widget).startswith(str(self.canvas)):
            return # 이 캔버스 관련 스크롤이 아니면 무시
            
        try:
            # Windows/macOS
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except AttributeError:
            # Linux
            try:
                if event.num == 4:
                    self.canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(1, "units")
            except tk.TclError:
                pass # 위젯 파괴 중
        except tk.TclError:
            pass # 위젯 파괴 중