"""
Markdown 渲染工具
提供 Markdown 到 HTML 的转换功能，支持代码高亮和样式适配
"""

import os
import base64
import markdown
from PySide6.QtWidgets import QTextBrowser
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtCore import QUrl, Qt
from .themes import theme_manager, ThemeType

class MarkdownLabel(QTextBrowser):
    """能够渲染 Markdown 的标签组件"""
    
    # 图片扩展名列表
    IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg']
    
    def __init__(self, text: str = "", parent=None, role: str = "assistant"):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)  # 禁用内部链接处理，完全手动处理
        self.setReadOnly(True)
        # 移除边框和背景，使其看起来像 Label
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.viewport().setAutoFillBackground(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 图片缓存 - 用于预览
        self._image_cache = {}
        self._original_pixmaps = {}
        
        self._role = role
        self._original_text = ""  # 保存原始 Markdown 文本用于主题更新
        
        # 应用主题样式（设置默认文字颜色）
        self._apply_theme_style()
        
        self.set_markdown(text)
        
    def set_markdown(self, text: str):
        """设置 Markdown 文本"""
        self._original_text = text  # 保存原始文本
        html = MarkdownUtils.render(text, self._role)
        self.setHtml(html)
        # 调整高度以适应内容
        self.document().adjustSize()
        h = self.document().size().height()
        self.setFixedHeight(int(h) + 10)
        
    def update_theme(self):
        """更新主题 - 重新渲染内容以应用新主题颜色"""
        # 先更新组件的默认文字颜色样式
        self._apply_theme_style()
        
        if self._original_text:
            html = MarkdownUtils.render(self._original_text, self._role)
            self.setHtml(html)
            # 调整高度以适应内容
            self.document().adjustSize()
            h = self.document().size().height()
            self.setFixedHeight(int(h) + 10)
    
    def _apply_theme_style(self):
        """应用主题样式，设置默认文字颜色
        
        这是修复深色主题下文字颜色问题的关键：
        通过 Qt 样式表显式设置 QTextBrowser 的默认文字颜色，
        确保即使 HTML 渲染有问题，文字颜色也能正确显示。
        """
        theme = theme_manager.current_theme
        c = theme_manager.get_current_colors()  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        
        # 根据角色确定文字颜色
        if self._role == "user":
            text_color = c.bubble_user_text
        else:
            text_color = c.bubble_ai_text
        
        # 设置样式表，确保默认文字颜色与主题一致
        self.setStyleSheet(f"""
            QTextBrowser {{
                color: {text_color};
                background: transparent;
                border: none;
            }}
        """)
    
    def loadResource(self, resource_type, name):
        """重写资源加载，缓存图片用于预览"""
        # QTextDocument.ResourceType.ImageResource = 2
        if resource_type == 2:
            url_str = name.toString()
            pixmap = QPixmap()
            file_path = ""
            
            # 处理 data URI
            if url_str.startswith("data:image"):
                try:
                    header, data = url_str.split(",", 1)
                    image_data = base64.b64decode(data)
                    pixmap.loadFromData(image_data)
                    file_path = url_str
                except Exception:
                    return super().loadResource(resource_type, name)
            else:
                # 处理文件路径
                if name.isLocalFile():
                    file_path = name.toLocalFile()
                elif url_str.startswith("file:///"):
                    # Windows: file:///C:/path -> C:/path
                    file_path = url_str[8:] if len(url_str) > 10 and url_str[9] == ':' else url_str[7:]
                else:
                    file_path = url_str
                    
                if os.path.exists(file_path):
                    pixmap = QPixmap(file_path)
                else:
                    return super().loadResource(resource_type, name)
            
            if not pixmap.isNull():
                # 缓存原始图片路径和原始图片
                self._image_cache[url_str] = file_path
                self._original_pixmaps[url_str] = pixmap.copy()
                
                # 计算最大宽度
                max_width = 260
                
                if pixmap.width() > max_width:
                    scaled = pixmap.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
                    return scaled
                return pixmap
                
        return super().loadResource(resource_type, name)
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件，检测是否点击了图片"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 获取点击位置的锚点
            anchor = self.anchorAt(event.pos())
            if anchor:
                # 检查是否是图片链接
                if self._is_image_url(anchor):
                    self._handle_image_click(anchor)
                    event.accept()
                    return
                else:
                    # 普通链接，用浏览器打开
                    QDesktopServices.openUrl(QUrl(anchor))
                    event.accept()
                    return
        super().mousePressEvent(event)
    
    def _is_image_url(self, url_str: str) -> bool:
        """判断是否是图片 URL"""
        lower_url = url_str.lower()
        if url_str.startswith('data:image'):
            return True
        return any(lower_url.endswith(ext) for ext in self.IMAGE_EXTENSIONS)
    
    def _handle_image_click(self, url_str: str):
        """处理图片点击"""
        try:
            pixmap = None
            file_path = url_str
            
            # 首先尝试从缓存中获取原始图片
            if url_str in self._original_pixmaps:
                pixmap = self._original_pixmaps[url_str]
                file_path = self._image_cache.get(url_str, url_str)
            
            # 如果缓存中没有，则重新加载
            if pixmap is None or pixmap.isNull():
                pixmap = QPixmap()
                if url_str.startswith('data:image'):
                    header, data = url_str.split(",", 1)
                    image_data = base64.b64decode(data)
                    pixmap.loadFromData(image_data)
                else:
                    # 处理文件路径
                    if url_str.startswith("file:///"):
                        file_path = url_str[8:] if len(url_str) > 10 and url_str[9] == ':' else url_str[7:]
                    
                    if os.path.exists(file_path):
                        pixmap = QPixmap(file_path)
                    elif os.path.exists(url_str):
                        pixmap = QPixmap(url_str)
                        file_path = url_str
            
            if pixmap is not None and not pixmap.isNull():
                self._show_image_preview(pixmap, file_path)
        except Exception as e:
            print(f"Error handling image click: {e}")
        
    def _show_image_preview(self, pixmap: QPixmap, image_path: str):
        """显示图片预览对话框"""
        from .floating_ball import ImagePreviewDialog
        # 使用顶层窗口作为父窗口，确保对话框正确显示
        parent_window = self.window()
        dialog = ImagePreviewDialog(pixmap, image_path, parent_window)
        dialog.exec()


class MarkdownUtils:
    """Markdown 工具类"""
    
    @staticmethod
    def render(text: str, role: str = "assistant") -> str:
        """
        将 Markdown 文本转换为适合 Qt QTextBrowser 显示的 HTML
        
        Args:
            text: Markdown 文本
            role: 消息角色 ("user" 或 "assistant")
        """
        # 获取当前主题配置
        theme = theme_manager.current_theme
        c = theme_manager.get_current_colors()  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        
        # 确定基础颜色
        if role == "user":
            text_color = c.bubble_user_text
            link_color = c.bubble_user_text # 用户气泡通常背景深，链接也用浅色
            code_bg = "rgba(255, 255, 255, 0.2)" # 半透明白
            code_fg = c.bubble_user_text
            border_color = "rgba(255, 255, 255, 0.3)"
            blockquote_bg = "rgba(255, 255, 255, 0.1)"
        else:
            text_color = c.bubble_ai_text
            link_color = c.primary
            
            if theme.type == ThemeType.DARK:
                # 深色模式下，代码块背景要比气泡背景更深或更浅，以形成对比
                # 气泡背景通常是 bg_secondary 或 bubble_ai_bg
                code_bg = "rgba(0, 0, 0, 0.3)" # 半透明黑，叠加在任何深色背景上都会更深
                code_fg = "#f0f0f0"
                border_color = "rgba(255, 255, 255, 0.2)"
                blockquote_bg = "rgba(255, 255, 255, 0.1)" # 半透明白，提亮引用块
            else:
                code_bg = "#f6f8fa"
                code_fg = "#24292e"
                border_color = c.border_base
                blockquote_bg = "rgba(0, 0, 0, 0.05)" # 半透明黑

        # 配置 Markdown 扩展
        pygments_style = 'monokai' if theme.type == ThemeType.DARK and role != "user" else 'default'
        
        configs = {
            'codehilite': {
                'noclasses': True,
                'pygments_style': pygments_style,
                'use_pygments': True,
                'css_class': 'codehilite'
            }
        }
        
        try:
            # 预处理：保护一些不需要渲染的内容
            html_content = markdown.markdown(
                text,
                extensions=['fenced_code', 'codehilite', 'tables', 'nl2br', 'sane_lists'],
                extension_configs=configs
            )
            
            # 后处理：给图片添加链接，以便支持点击预览
            # 查找 <img src="..."> 并替换为 <a href="..."><img src="..."></a>
            import re
            def replace_img(match):
                img_tag = match.group(0)
                src_match = re.search(r'src="([^"]+)"', img_tag)
                if src_match:
                    src = src_match.group(1)
                    return f'<a href="{src}">{img_tag}</a>'
                return img_tag
                
            html_content = re.sub(r'<img[^>]+>', replace_img, html_content)
            
        except Exception:
            return f"<p>{text}</p>"

        # 构建 CSS 样式
        style = f"""
        <style>
            body {{
                font-family: {theme.font_family};
                font-size: {theme.font_size_base}px;
                color: {text_color};
                margin: 0;
            }}
            p {{
                margin-bottom: 6px;
                line-height: 1.4;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: {text_color};
                font-weight: bold;
                margin-top: 10px;
                margin-bottom: 6px;
            }}
            h1 {{ font-size: {theme.font_size_large + 6}px; border-bottom: 1px solid {border_color}; padding-bottom: 4px; }}
            h2 {{ font-size: {theme.font_size_large + 4}px; border-bottom: 1px solid {border_color}; padding-bottom: 4px; }}
            h3 {{ font-size: {theme.font_size_large + 2}px; }}
            
            pre {{
                background-color: {code_bg};
                color: {code_fg};
                padding: 10px;
                border-radius: 6px;
                border: 1px solid {border_color};
                font-family: Consolas, Monaco, "Courier New", monospace;
                margin: 8px 0;
                white-space: pre-wrap;
            }}
            
            code {{
                background-color: {code_bg};
                color: {code_fg};
                padding: 2px 5px;
                border-radius: 4px;
                font-family: Consolas, Monaco, "Courier New", monospace;
            }}
            
            a {{
                color: {link_color};
                text-decoration: underline;
                font-weight: bold;
            }}
            
            blockquote {{
                border-left: 4px solid {border_color};
                padding-left: 10px;
                margin: 4px 0 4px 4px;
                background-color: {blockquote_bg};
            }}
            
            ul, ol {{
                margin-left: 0;
                padding-left: 20px;
            }}
            li {{
                margin-bottom: 2px;
            }}
            
            table {{
                border-collapse: collapse;
                border: 1px solid {border_color};
                width: 100%;
                margin: 8px 0;
            }}
            th {{
                border: 1px solid {border_color};
                padding: 6px;
                font-weight: bold;
                background-color: {blockquote_bg};
            }}
            td {{
                border: 1px solid {border_color};
                padding: 6px;
            }}
            
            img {{
                max-width: 100%;
                height: auto;
                border-radius: 8px;
                cursor: pointer;
                display: block;
                margin: 4px 0;
            }}
        </style>
        """

        return f"{style}<div>{html_content}</div>"
