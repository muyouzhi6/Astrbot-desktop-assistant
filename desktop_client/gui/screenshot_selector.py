"""
区域截图选择器

提供全屏半透明遮罩，用户可用鼠标拖拽选择截图区域。
"""

from typing import Optional, Callable

try:
    from PySide6.QtCore import Qt, QPoint, QRect, Signal, QTimer
    from PySide6.QtGui import (
        QPainter,
        QColor,
        QPen,
        QMouseEvent,
        QKeyEvent,
        QPaintEvent,
        QPixmap,
    )
    from PySide6.QtWidgets import QWidget, QApplication, QLabel

    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


if HAS_PYSIDE6:

    class ScreenshotSelectorWindow(QWidget):
        """区域截图选择器窗口"""

        # 信号：选择完成，发送选区坐标 (x, y, width, height)
        selection_completed = Signal(int, int, int, int)
        # 信号：选择取消
        selection_cancelled = Signal()

        def __init__(
            self,
            on_complete: Optional[Callable[[int, int, int, int], None]] = None,
            on_cancel: Optional[Callable[[], None]] = None,
            parent=None,
        ):
            super().__init__(parent)

            self.on_complete = on_complete
            self.on_cancel = on_cancel

            # 选区状态
            self._selecting = False
            self._start_pos: Optional[QPoint] = None
            self._current_pos: Optional[QPoint] = None
            self._selection_rect: Optional[QRect] = None

            # 截取的屏幕背景
            self._background_pixmap: Optional[QPixmap] = None

            # 遮罩颜色
            self._mask_color = QColor(0, 0, 0, 128)  # 半透明黑色
            self._border_color = QColor(0, 120, 215)  # 蓝色边框
            self._highlight_color = QColor(0, 120, 215, 50)  # 高亮填充

            # 设置窗口属性
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.setCursor(Qt.CursorShape.CrossCursor)

            # 尺寸提示标签
            self._size_label = QLabel(self)
            self._size_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 0, 0, 180);
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-family: Consolas, Monaco, monospace;
                }
            """)
            self._size_label.hide()

            # 提示标签
            self._tip_label = QLabel("拖拽选择区域，ESC 取消", self)
            self._tip_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 0, 0, 180);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 14px;
                }
            """)
            self._tip_label.adjustSize()

        def start(self):
            """开始截图选择"""
            # 捕获当前屏幕
            self._capture_screen()

            # 全屏显示
            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.geometry()
                self.setGeometry(geometry)

            # 将提示标签居中
            self._center_tip_label()

            self.showFullScreen()
            self.activateWindow()
            self.raise_()

        def _capture_screen(self):
            """捕获当前屏幕作为背景"""
            screen = QApplication.primaryScreen()
            if screen:
                self._background_pixmap = screen.grabWindow(0)

        def _center_tip_label(self):
            """将提示标签居中"""
            if self._tip_label:
                self._tip_label.move(
                    (self.width() - self._tip_label.width()) // 2,
                    (self.height() - self._tip_label.height()) // 2,
                )

        def paintEvent(self, event: QPaintEvent):
            """绘制事件"""
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 绘制背景截图
            if self._background_pixmap:
                painter.drawPixmap(0, 0, self._background_pixmap)
            else:
                painter.fillRect(self.rect(), QColor(0, 0, 0))

            # 绘制半透明遮罩
            painter.fillRect(self.rect(), self._mask_color)

            # 如果有选区，清除选区的遮罩并绘制边框
            if self._selection_rect and self._selection_rect.isValid():
                rect = self._selection_rect.normalized()

                # 清除选区的遮罩（显示原始截图）
                if self._background_pixmap:
                    painter.drawPixmap(rect, self._background_pixmap, rect)

                # 绘制选区高亮
                painter.fillRect(rect, self._highlight_color)

                # 绘制选区边框
                pen = QPen(self._border_color, 2, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawRect(rect)

                # 绘制四角控制点
                self._draw_corner_handles(painter, rect)

        def _draw_corner_handles(self, painter: QPainter, rect: QRect):
            """绘制四角控制点"""
            handle_size = 8
            handle_color = QColor(255, 255, 255)
            border_color = self._border_color

            corners = [
                rect.topLeft(),
                rect.topRight(),
                rect.bottomLeft(),
                rect.bottomRight(),
            ]

            for corner in corners:
                handle_rect = QRect(
                    corner.x() - handle_size // 2,
                    corner.y() - handle_size // 2,
                    handle_size,
                    handle_size,
                )
                painter.fillRect(handle_rect, handle_color)
                painter.setPen(QPen(border_color, 1))
                painter.drawRect(handle_rect)

        def mousePressEvent(self, event: QMouseEvent):
            """鼠标按下事件"""
            if event.button() == Qt.MouseButton.LeftButton:
                self._selecting = True
                self._start_pos = event.position().toPoint()
                self._current_pos = self._start_pos
                self._selection_rect = QRect(self._start_pos, self._start_pos)

                # 隐藏提示标签
                self._tip_label.hide()

                self.update()
                event.accept()

        def mouseMoveEvent(self, event: QMouseEvent):
            """鼠标移动事件"""
            if self._selecting and self._start_pos:
                self._current_pos = event.position().toPoint()
                self._selection_rect = QRect(self._start_pos, self._current_pos)

                # 更新尺寸标签
                self._update_size_label()

                self.update()
                event.accept()

        def mouseReleaseEvent(self, event: QMouseEvent):
            """鼠标释放事件"""
            if event.button() == Qt.MouseButton.LeftButton and self._selecting:
                self._selecting = False

                if self._selection_rect and self._selection_rect.isValid():
                    rect = self._selection_rect.normalized()

                    # 检查选区大小
                    if rect.width() > 5 and rect.height() > 5:
                        # 隐藏窗口
                        self.hide()

                        # 发送信号
                        self.selection_completed.emit(
                            rect.x(), rect.y(), rect.width(), rect.height()
                        )

                        # 回调
                        if self.on_complete:
                            self.on_complete(
                                rect.x(), rect.y(), rect.width(), rect.height()
                            )

                        # 延迟关闭窗口
                        QTimer.singleShot(100, self.close)
                    else:
                        # 选区太小，重置
                        self._reset_selection()

                event.accept()

        def keyPressEvent(self, event: QKeyEvent):
            """键盘按下事件"""
            if event.key() == Qt.Key.Key_Escape:
                # ESC 取消
                self._cancel_selection()
                event.accept()
            else:
                super().keyPressEvent(event)

        def _update_size_label(self):
            """更新尺寸标签"""
            if self._selection_rect:
                rect = self._selection_rect.normalized()
                text = f"{rect.width()} × {rect.height()}"
                self._size_label.setText(text)
                self._size_label.adjustSize()

                # 定位在选区右下角
                label_x = rect.right() + 5
                label_y = rect.bottom() + 5

                # 确保不超出屏幕
                if label_x + self._size_label.width() > self.width():
                    label_x = rect.right() - self._size_label.width() - 5
                if label_y + self._size_label.height() > self.height():
                    label_y = rect.bottom() - self._size_label.height() - 5

                self._size_label.move(label_x, label_y)
                self._size_label.show()

        def _reset_selection(self):
            """重置选区"""
            self._selecting = False
            self._start_pos = None
            self._current_pos = None
            self._selection_rect = None
            self._size_label.hide()
            self._tip_label.show()
            self._center_tip_label()
            self.update()

        def _cancel_selection(self):
            """取消选择"""
            self.hide()

            # 发送信号
            self.selection_cancelled.emit()

            # 回调
            if self.on_cancel:
                self.on_cancel()

            self.close()

        def showEvent(self, event):
            """显示事件"""
            super().showEvent(event)
            self._center_tip_label()

    class RegionScreenshotCapture:
        """区域截图捕获工具类"""

        def __init__(self, save_dir: str = "./temp/screenshots"):
            """
            初始化区域截图工具

            Args:
                save_dir: 截图保存目录
            """
            import os

            self.save_dir = save_dir
            os.makedirs(save_dir, exist_ok=True)

            self._selector: Optional[ScreenshotSelectorWindow] = None
            self._result_path: Optional[str] = None
            self._completed = False

        def capture_async(self, on_complete: Callable[[Optional[str]], None]):
            """
            异步启动区域截图选择

            Args:
                on_complete: 完成回调，参数为截图路径或 None（取消）
            """
            self._selector = ScreenshotSelectorWindow(
                on_complete=lambda x, y, w, h: self._on_async_complete(
                    x, y, w, h, on_complete
                ),
                on_cancel=lambda: on_complete(None),
            )
            self._selector.start()

        def _on_async_complete(
            self,
            x: int,
            y: int,
            width: int,
            height: int,
            callback: Callable[[Optional[str]], None],
        ):
            """异步完成回调"""
            path = self._capture_region(x, y, width, height)
            callback(path)

        def _capture_region(
            self, x: int, y: int, width: int, height: int
        ) -> Optional[str]:
            """捕获指定区域"""
            import os
            import time

            try:
                from ..services.screen_capture import ScreenCaptureService

                service = ScreenCaptureService(self.save_dir)
                image = service.capture_region(x, y, width, height)

                if image is None:
                    return None

                # 保存到文件
                filename = f"region_{int(time.time() * 1000)}.png"
                filepath = os.path.join(self.save_dir, filename)
                image.save(filepath, "PNG")

                return filepath
            except Exception as e:
                print(f"区域截图失败: {e}")
                return None

    # 别名，保持向后兼容
    ScreenshotSelector = ScreenshotSelectorWindow

else:
    # PySide6 未安装时的占位类
    class ScreenshotSelectorWindow:
        """占位类"""

        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 未安装")

        def start(self):
            pass

    class RegionScreenshotCapture:
        """占位类"""

        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 未安装")

        def capture_async(self, on_complete: Callable[[Optional[str]], None]):
            raise ImportError("PySide6 未安装")

    ScreenshotSelector = ScreenshotSelectorWindow
