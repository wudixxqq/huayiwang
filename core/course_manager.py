"""
课件状态管理模块
"""
from typing import List, Optional
from dataclasses import dataclass
from core.page_monitor import CourseItem
from utils.logger import log


@dataclass
class CourseState:
    """课件学习状态快照"""
    title: str
    status: str
    progress_percent: float = 0.0
    watched_seconds: float = 0.0
    total_seconds: float = 0.0


class CourseManager:
    """课件列表与状态管理器"""

    def __init__(self):
        self.courses: List[CourseItem] = []
        self.current_index: int = -1
        self.current_title: str = ""
        self.history: List[str] = []  # 已完成的课件标题

    def update_courses(self, courses: List[CourseItem]):
        """更新课件列表"""
        self.courses = courses
        # 优先通过 id="top_play" 元素精确定位当前播放课件（最可靠）
        for i, c in enumerate(courses):
            if c.hasTopPlay:
                self.current_index = i
                self.current_title = c.title
                return
        # 回退1：通过"学习中"状态定位
        for i, c in enumerate(courses):
            if c.status == "学习中":
                self.current_index = i
                self.current_title = c.title
                return
        # 回退2：通过 className 中的 current-playing/active 定位
        for i, c in enumerate(courses):
            cls = str(c.className or '').lower()
            if 'current-playing' in cls or 'current_playing' in cls:
                self.current_index = i
                self.current_title = c.title
                return
        for i, c in enumerate(courses):
            cls = str(c.className or '').lower()
            import re
            if re.search(r'\b(active|playing|selected)\b', cls):
                self.current_index = i
                self.current_title = c.title
                return

    def get_current_course(self) -> Optional[CourseItem]:
        """获取当前课件"""
        if 0 <= self.current_index < len(self.courses):
            return self.courses[self.current_index]
        return None

    def get_next_unfinished(self) -> Optional[CourseItem]:
        """获取下一个未完成的课件（从 current_index 之后开始查找，避免重复从头遍历）"""
        start = max(0, self.current_index)
        # 优先从当前课件之后查找
        for i in range(start + 1, len(self.courses)):
            if self.courses[i].status in ("学习中", "未学习"):
                return self.courses[i]
        # 若后面没有，再从开头查找（兼容 current_index 在最后或异常情况）
        for i in range(0, min(start + 1, len(self.courses))):
            if self.courses[i].status in ("学习中", "未学习"):
                return self.courses[i]
        return None

    def get_stats(self) -> dict:
        """获取学习统计"""
        total = len(self.courses)
        done = sum(1 for c in self.courses if c.status == "待考试")
        learning = sum(1 for c in self.courses if c.status == "学习中")
        not_started = sum(1 for c in self.courses if c.status == "未学习")
        return {
            "total": total,
            "done": done,
            "learning": learning,
            "not_started": not_started,
            "progress": round(done / total * 100, 1) if total > 0 else 0
        }

    def mark_current_done(self, title: str = ""):
        """标记当前课件为已完成；若传入 title，优先匹配标题定位，避免 current_index 滞后导致误标"""
        if title:
            for c in self.courses:
                if title in c.title or c.title in title:
                    c.status = "待考试"
                    log.info(f"课件 '{c.title}' 已标记为完成")
                    return
        course = self.get_current_course()
        if course:
            course.status = "待考试"
            log.info(f"课件 '{course.title}' 已标记为完成")

    def format_course_list(self) -> List[str]:
        """格式化为GUI显示的字符串列表"""
        lines = []
        for c in self.courses:
            marker = "▶" if c.index == self.current_index else "  "
            lines.append(f"{marker} [{c.index+1}] {c.title} — {c.status}")
        return lines
