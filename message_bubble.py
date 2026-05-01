#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""消息气泡组件（支持表格、LaTeX 公式渲染，改进 Unicode 降级方案）"""

import os
import re
import io
import base64
import subprocess
import platform
from io import BytesIO

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QWidget, QSizePolicy,
    QMenu, QAction, QApplication, QPushButton
)
from PyQt5.QtCore import Qt, QEvent, QTimer
from PyQt5.QtGui import (
    QFont, QFontMetrics, QTextDocument, QTextOption,
    QPalette, QColor, QImage
)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 设置数学字体集，避免缺字体导致的渲染失败
plt.rcParams['mathtext.fontset'] = 'stix'

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


def open_file(filepath):
    """用系统默认程序打开文件"""
    try:
        if platform.system() == "Windows":
            os.startfile(filepath)
        elif platform.system() == "Darwin":
            subprocess.run(["open", filepath])
        else:
            subprocess.run(["xdg-open", filepath])
    except Exception as e:
        print(f"打开文件失败: {e}")


# ===================== 公式处理工具 =====================

def latex_to_image(latex_str, dpi=150, fontsize=12):
    """将 LaTeX 公式渲染为 QImage，失败则抛出异常"""
    # 预处理：将 matplotlib 可能不支持的 LaTeX 命令转为标准形式
    processed = latex_str
    processed = processed.replace(r'\sin', r'\mathrm{sin}')
    processed = processed.replace(r'\cos', r'\mathrm{cos}')
    processed = processed.replace(r'\tan', r'\mathrm{tan}')
    processed = processed.replace(r'\cot', r'\mathrm{cot}')
    # 确保多字符下标/上标被花括号包裹
    processed = re.sub(r'(?<!\\)_(?!\{)([a-zA-Z0-9]{2,})', r'_{\1}', processed)
    processed = re.sub(r'(?<!\\)\^(?!\{)([a-zA-Z0-9]{2,})', r'^{\1}', processed)

    fig, ax = plt.subplots(figsize=(0.01, 0.01))
    text = ax.text(0, 0, f"${processed}$", fontsize=fontsize, ha='center', va='center')
    fig.canvas.draw()
    bbox = text.get_window_extent(renderer=fig.canvas.get_renderer())
    plt.close(fig)

    if bbox.width == 0 or bbox.height == 0:
        raise ValueError("公式渲染尺寸为0，可能是命令不支持")

    fig, ax = plt.subplots(figsize=(bbox.width/fig.dpi, bbox.height/fig.dpi), dpi=dpi)
    ax.axis('off')
    ax.text(0.5, 0.5, f"${processed}$", fontsize=fontsize, ha='center', va='center',
            transform=ax.transAxes)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0.1, transparent=True)
    plt.close(fig)
    buf.seek(0)
    img = QImage()
    img.loadFromData(buf.getvalue())
    return img


def latex_to_unicode(latex_str):
    """将 LaTeX 公式转为接近的 Unicode 文本，保留上下标等信息"""
    s = latex_str.strip('$')

    # 常见命令替换
    s = s.replace(r'\sin', 'sin')
    s = s.replace(r'\cos', 'cos')
    s = s.replace(r'\tan', 'tan')
    s = s.replace(r'\cot', 'cot')
    s = s.replace(r'\sqrt', '√')
    s = s.replace(r'\times', '×')
    s = s.replace(r'\cdot', '·')
    s = s.replace(r'\Delta', 'Δ')
    s = s.replace(r'\varphi', 'φ')
    s = s.replace(r'\pi', 'π')
    s = s.replace(r'\theta', 'θ')
    s = s.replace(r'\alpha', 'α')
    s = s.replace(r'\beta', 'β')
    s = s.replace(r'\infty', '∞')
    s = s.replace(r'\pm', '±')

    # 处理分数 \frac{num}{den} → (num)/(den)
    def frac_repl(match):
        num = match.group(1)
        den = match.group(2)
        return f"({num})/({den})"
    s = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', frac_repl, s)

    # Unicode 下标/上标映射（常用数字和字母）
    sub_map = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
        'a': 'ₐ', 'e': 'ₑ', 'i': 'ᵢ', 'j': 'ⱼ', 'o': 'ₒ',
        'u': 'ᵤ', 'v': 'ᵥ', 'x': 'ₓ',
        'C': 'C', 'N': 'N'  # 大写字母下标没有现成字符，保留
    }
    sup_map = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ',
        'i': 'ⁱ', 'n': 'ⁿ'
    }

    def sub_repl(match):
        sub = match.group(1)
        # 尝试逐字符转换
        uni_sub = ''.join(sub_map.get(c, c) for c in sub)
        return uni_sub

    def sup_repl(match):
        sup = match.group(1)
        uni_sup = ''.join(sup_map.get(c, c) for c in sup)
        return uni_sup

    # 替换 _{...} → Unicode 下标
    s = re.sub(r'_\{([^}]+)\}', sub_repl, s)
    # 替换 ^{...} → Unicode 上标
    s = re.sub(r'\^\{([^}]+)\}', sup_repl, s)

    # 去掉多余的花括号
    s = s.replace('{', '').replace('}', '')
    return s


def markdown_to_html(text, text_color="#000000"):
    """将 Markdown 转为 HTML，支持表格和 LaTeX 公式渲染"""
    if not HAS_MARKDOWN:
        return text.replace('\n', '<br>')

    formulas = []
    placeholder_pattern = "FORMULA_PLACEHOLDER_{}_"

    def replace_math(match):
        formulas.append(match.group(0))
        return placeholder_pattern.format(len(formulas) - 1)

    # 先提取公式
    text = re.sub(r'\$\$(.+?)\$\$', replace_math, text, flags=re.DOTALL)
    text = re.sub(r'\$(.+?)\$', replace_math, text)

    # 转换 Markdown 表格等
    md = markdown.Markdown(extensions=['tables'])
    html = md.convert(text)

    # 处理每个公式占位符
    for idx, formula in enumerate(formulas):
        placeholder = placeholder_pattern.format(idx)
        latex = formula.strip('$')
        try:
            img = latex_to_image(latex)
            ba = io.BytesIO()
            img.save(ba, format='PNG')
            b64 = base64.b64encode(ba.getvalue()).decode()
            img_tag = f'<img src="data:image/png;base64,{b64}" ' \
                      f'style="vertical-align:middle; max-width:100%;">'
        except Exception as e:
            # 渲染失败 → 使用 Unicode 近似文本（颜色与正文一致）
            unicode_version = latex_to_unicode(formula)
            img_tag = f'<span style="font-family:Times New Roman, serif;">{unicode_version}</span>'
        html = html.replace(placeholder, img_tag)

    return html


# ===================== 消息气泡组件 =====================

class MessageBubble(QFrame):
    MAX_BUBBLE_RATIO = 0.6
    MIN_BUBBLE_WIDTH = 60
    FONT_SIZE = 10

    def __init__(self, content, time_str, is_me=True, attachments=None, parent=None):
        super().__init__(parent)
        self.content = content
        self.is_me = is_me
        self.attachments = attachments or []
        self.text_edit = None
        self.content_widget = None
        self._setup_ui(content, time_str)

    def _setup_ui(self, content, time_str):
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background: transparent;")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(15, 2, 15, 2)
        outer_layout.setSpacing(0)

        msg_layout = QHBoxLayout()
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(8)

        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        if self.is_me:
            avatar.setStyleSheet("""
                QLabel {
                    background-color: #1485EE;
                    border-radius: 4px;
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
            avatar.setText("我")
        else:
            avatar.setStyleSheet("""
                QLabel {
                    background-color: #07C160;
                    border-radius: 4px;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                }
            """)
            avatar.setText("🤖")

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(10, 5, 10, 5)
        content_layout.setSpacing(1)

        time_label = QLabel(time_str)
        time_label.setFont(QFont("Microsoft YaHei", 7))
        time_label.setStyleSheet("color: #B0B0B0; background: transparent;")
        time_label.setAlignment(Qt.AlignRight if self.is_me else Qt.AlignLeft)
        time_label.setFixedHeight(12)
        content_layout.addWidget(time_label)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Microsoft YaHei", self.FONT_SIZE))
        self.text_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)

        if self.is_me:
            bubble_bg = "#D7F0DB"
            text_color = "#0F3D1D"
            selection_bg = "#A8DFB5"
            selection_text = "#06401A"
            radius_side = "right"
        else:
            bubble_bg = "#FFFFFF"
            text_color = "#000000"
            selection_bg = "#B8D8F0"
            selection_text = "#0A1E33"
            radius_side = "left"

        self.content_widget.setStyleSheet(f"""
            background-color: {bubble_bg};
            border-radius: 6px;
            border-top-{radius_side}-radius: 2px;
        """)

        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                color: {text_color};
                selection-background-color: {selection_bg};
                selection-color: {selection_text};
                padding: 0px;
                margin: 0px;
            }}
            QTextEdit:focus {{
                border: none;
                background: transparent;
                color: {text_color};
                selection-background-color: {selection_bg};
                selection-color: {selection_text};
            }}
        """)

        palette = self.text_edit.palette()
        palette.setColor(QPalette.Highlight, QColor(selection_bg))
        palette.setColor(QPalette.HighlightedText, QColor(selection_text))
        palette.setColor(QPalette.Text, QColor(text_color))
        palette.setColor(QPalette.Inactive, QPalette.Highlight, QColor(selection_bg))
        palette.setColor(QPalette.Inactive, QPalette.HighlightedText, QColor(selection_text))
        self.text_edit.setPalette(palette)

        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setFrameShape(QFrame.NoFrame)
        self.text_edit.document().setDocumentMargin(0)

        # 将内容转为 HTML 并设置
        html_content = markdown_to_html(content, text_color=text_color)
        self.text_edit.setHtml(html_content)
        self.text_edit.document().contentsChanged.connect(self._adjust_size)

        content_layout.addWidget(self.text_edit)

        # 附件处理（省略与之前相同，未改动）
        for att in self.attachments:
            if isinstance(att, dict):
                filename = att.get("filename", "unknown")
                filepath = att.get("filepath", "")
                is_received = bool(filepath and os.path.exists(filepath))
            else:
                filename = att
                filepath = ""
                is_received = False

            if is_received:
                att_btn = QPushButton(f"📎 {filename}")
                att_btn.setFont(QFont("Microsoft YaHei", 8))
                att_btn.setCursor(Qt.PointingHandCursor)
                att_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #576B95;
                        border: none;
                        padding: 2px 0px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        color: #1485EE;
                        text-decoration: underline;
                    }
                """)
                att_btn.clicked.connect(lambda checked, p=filepath: open_file(p))
                content_layout.addWidget(att_btn)
            else:
                att_label = QLabel(f"📎 {filename}")
                att_label.setFont(QFont("Microsoft YaHei", 7))
                att_label.setStyleSheet("color: #576B95; background: transparent;")
                att_label.setFixedHeight(14)
                content_layout.addWidget(att_label)

        if self.is_me:
            msg_layout.addStretch()
            msg_layout.addWidget(self.content_widget)
            msg_layout.addWidget(avatar)
        else:
            msg_layout.addWidget(avatar)
            msg_layout.addWidget(self.content_widget)
            msg_layout.addStretch()

        outer_layout.addLayout(msg_layout)
        self._adjust_size()
        self.installEventFilter(self)

    # ===================== 右键菜单 =====================
    def _show_context_menu(self, pos):
        if self.is_me:
            hover_bg = "#A8DFB5"
            hover_text = "#06401A"
        else:
            hover_bg = "#A8D4F0"
            hover_text = "#0A2E4A"

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: white;
                border: 1px solid #C0C0C0;
                border-radius: 6px;
                padding: 6px 0px;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 9px 36px 9px 18px;
                color: #191919;
            }}
            QMenu::item:selected {{
                background-color: {hover_bg};
                color: {hover_text};
                font-weight: bold;
            }}
        """)

        copy_action = QAction("复制", menu)
        copy_action.triggered.connect(self._copy_selected)
        menu.addAction(copy_action)

        select_all_action = QAction("全选", menu)
        select_all_action.triggered.connect(self._select_all)
        menu.addAction(select_all_action)

        menu.exec_(self.text_edit.mapToGlobal(pos))

    def _copy_selected(self):
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())
        else:
            QApplication.clipboard().setText(self.content)

    def _select_all(self):
        self.text_edit.selectAll()

    # ===================== 自适应大小 =====================
    def _calculate_ideal_width(self):
        if not self.content:
            return self.MIN_BUBBLE_WIDTH
        font_metrics = QFontMetrics(QFont("Microsoft YaHei", self.FONT_SIZE))
        lines = self.content.split('\n')
        max_line_width = max((font_metrics.width(line) for line in lines), default=0)
        ideal_width = max_line_width + 20
        parent_width = self.parent().width() if self.parent() else 800
        max_width = int(parent_width * self.MAX_BUBBLE_RATIO)
        return max(self.MIN_BUBBLE_WIDTH, min(ideal_width, max_width))

    def _adjust_size(self):
        if not self.text_edit or not self.content_widget:
            return
        ideal_width = self._calculate_ideal_width()
        self.text_edit.setFixedWidth(ideal_width - 20)
        doc = self.text_edit.document()
        doc.setTextWidth(ideal_width - 20)
        QTimer.singleShot(50, self._finalize_height)

    def _finalize_height(self):
        doc = self.text_edit.document()
        height = int(doc.size().height()) + 10
        self.text_edit.setFixedHeight(height)

    def eventFilter(self, obj, event):
        if obj == self and event.type() == QEvent.Resize:
            self._adjust_size()
        return super().eventFilter(obj, event)