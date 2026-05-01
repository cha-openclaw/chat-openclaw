# -*- coding: utf-8 -*-
"""
Created on Thu Apr 30 19:33:11 2026

@author: hasee
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent 聊天面板模块"""

import os
import threading
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QTextEdit,
    QPushButton, QLabel, QFrame, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QFont

from database import save_message, load_messages
from email_utils import check_mail_connection, send_email
from message_bubble import MessageBubble


class AgentChatPanel(QWidget):
    """单个 Agent 的聊天面板"""

    def __init__(self, agent_config, main_config, parent=None):
        super().__init__(parent)
        self.agent_config = agent_config
        self.main_config = main_config
        self.agent_id = agent_config.get("id", "unknown")
        self.messages = []
        self.current_attachments = []
        self.is_connected = False
        self._history_loaded = False

        self._setup_ui()
        self._check_connection()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 聊天区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background-color: #EDEDED; border: none;")

        self.messages_widget = QWidget()
        self.messages_widget.setStyleSheet("background-color: #EDEDED;")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 10, 0, 10)
        self.messages_layout.setSpacing(0)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_widget)
        layout.addWidget(self.scroll_area, stretch=1)

        # 输入区域
        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: #F7F7F7; border-top: 1px solid #D9D9D9;")
        input_frame.setMinimumHeight(160)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 10, 16, 10)
        input_layout.setSpacing(8)

        # 附件栏
        attach_layout = QHBoxLayout()
        self.attach_btn = QPushButton("📎 文件")
        self.attach_btn.setFont(QFont("Microsoft YaHei", 9))
        self.attach_btn.setStyleSheet("""
            QPushButton { background-color: #F7F7F7; color: #576B95; border: 1px solid #D9D9D9; border-radius: 4px; padding: 5px 12px; }
            QPushButton:hover { background-color: #EBEBEB; }
        """)
        self.attach_btn.setCursor(Qt.PointingHandCursor)
        self.attach_btn.clicked.connect(self.attach_files)
        attach_layout.addWidget(self.attach_btn)

        self.attach_label = QLabel("")
        self.attach_label.setFont(QFont("Microsoft YaHei", 9))
        self.attach_label.setStyleSheet("color: #888888; border: none;")
        attach_layout.addWidget(self.attach_label)

        self.clear_attach_btn = QPushButton("✕")
        self.clear_attach_btn.setFont(QFont("Microsoft YaHei", 9))
        self.clear_attach_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888888; border: none; padding: 4px 8px; }
            QPushButton:hover { color: #FA5151; }
        """)
        self.clear_attach_btn.setCursor(Qt.PointingHandCursor)
        self.clear_attach_btn.clicked.connect(self.clear_attachments)
        self.clear_attach_btn.hide()
        attach_layout.addWidget(self.clear_attach_btn)
        attach_layout.addStretch()
        input_layout.addLayout(attach_layout)

        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("输入消息...")
        self.input_text.setFont(QFont("Microsoft YaHei", 10))
        self.input_text.setStyleSheet("""
            QTextEdit { border: none; background-color: #F7F7F7; color: #191919; padding: 4px; }
            QTextEdit:focus { border: none; background-color: #F7F7F7; }
        """)
        self.input_text.setMaximumHeight(80)
        self.input_text.setMinimumHeight(50)
        self.input_text.installEventFilter(self)
        self.input_text.textChanged.connect(self._on_input_changed)
        input_layout.addWidget(self.input_text)

        # 底部按钮栏
        btn_layout = QHBoxLayout()
        self.status_label = QLabel("● 检测中...")
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #888888; border: none;")
        btn_layout.addWidget(self.status_label)
        btn_layout.addStretch()

        self.send_btn = QPushButton("发送")
        self.send_btn.setFont(QFont("Microsoft YaHei", 9))
        self.send_btn.setFixedSize(60, 30)
        self.send_btn.setStyleSheet("""
            QPushButton { background-color: #F7F7F7; color: #B0B0B0; border: 1px solid #E0E0E0; border-radius: 4px; }
            QPushButton:hover { background-color: #F0F0F0; }
        """)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_message)
        btn_layout.addWidget(self.send_btn)

        input_layout.addLayout(btn_layout)
        layout.addWidget(input_frame)

    def _on_input_changed(self):
        has_text = bool(self.input_text.toPlainText().strip())
        if has_text:
            self.send_btn.setStyleSheet("""
                QPushButton { background-color: #2FA84D; color: white; border: none; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #269140; }
            """)
        else:
            self.send_btn.setStyleSheet("""
                QPushButton { background-color: #F7F7F7; color: #B0B0B0; border: 1px solid #E0E0E0; border-radius: 4px; }
                QPushButton:hover { background-color: #F0F0F0; }
            """)

    def eventFilter(self, obj, event):
        if obj == self.input_text and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_S and event.modifiers() == Qt.AltModifier:
                self.send_message()
                return True
            if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    # ===== 公开方法 =====
    def load_history(self):
        """从数据库加载历史消息"""
        if self._history_loaded:
            return
        self._history_loaded = True

        loaded = load_messages(self.agent_id)
        if loaded:
            self.messages = loaded
            self._rebuild_messages()
            QTimer.singleShot(100, self._scroll_to_bottom)

    def receive_messages(self, new_msgs):
        """接收来自主窗口的消息（其他 Agent 发来的新邮件）"""
        self.messages.extend(new_msgs)
        self._rebuild_messages()
        QTimer.singleShot(150, self._scroll_to_bottom)

    def _rebuild_messages(self):
        """重建所有消息气泡"""
        while self.messages_layout.count() > 0:
            item = self.messages_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        for msg in self.messages:
            bubble = MessageBubble(
                msg.get("content", ""),
                msg.get("time", ""),
                msg.get("is_me", False),
                msg.get("attachments", [])
            )
            self.messages_layout.addWidget(bubble)

        self.messages_layout.addStretch()

    def _scroll_to_bottom(self):
        vb = self.scroll_area.verticalScrollBar()
        vb.setValue(vb.maximum())

    def attach_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择附件")
        for f in files:
            if f not in self.current_attachments:
                self.current_attachments.append(f)
        self._update_attach_label()

    def clear_attachments(self):
        self.current_attachments = []
        self._update_attach_label()

    def _update_attach_label(self):
        if self.current_attachments:
            names = [os.path.basename(f) for f in self.current_attachments[:3]]
            self.attach_label.setText(f"已选择 {len(self.current_attachments)} 个: " + ", ".join(names))
            self.clear_attach_btn.show()
        else:
            self.attach_label.setText("")
            self.clear_attach_btn.hide()

    def send_message(self):
        content = self.input_text.toPlainText().strip()
        if not content and not self.current_attachments:
            return

        time_str = datetime.now().strftime("%m-%d %H:%M")
        att_names = [os.path.basename(f) for f in self.current_attachments]
        display_content = content if content else "(发送了附件)"

        msg_obj = {
            "is_me": True,
            "content": display_content,
            "time": time_str,
            "attachments": att_names
        }
        self.messages.append(msg_obj)
        save_message(self.agent_id, True, display_content, time_str, att_names)

        self._rebuild_messages()
        QTimer.singleShot(100, self._scroll_to_bottom)
        self.input_text.clear()
        self._update_status("● 发送中...", "#576B95")

        attachments_to_send = self.current_attachments.copy()
        self.current_attachments = []
        self._update_attach_label()

        threading.Thread(
            target=self._do_send, args=(content, attachments_to_send), daemon=True
        ).start()

    def _do_send(self, content, attachments):
        try:
            send_email(self.main_config, self.agent_config, content, attachments)
            self._update_status("● 在线", "#2FA84D")
        except Exception as e:
            self._update_status("● 失败", "#FA5151")

    def _check_connection(self):
        def _do():
            connected = check_mail_connection(self.main_config)
            self.is_connected = connected
            self._update_status("● 在线" if connected else "● 离线",
                                "#2FA84D" if connected else "#FA5151")
        threading.Thread(target=_do, daemon=True).start()

    def _update_status(self, text, color):
        try:
            self.status_label.setText(text)
            self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
        except:
            pass

    def update_config(self, agent_config, main_config):
        self.agent_config = agent_config
        self.main_config = main_config

    def stop(self):
        pass  # 接收线程已移到主窗口统一管理