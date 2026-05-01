#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主程序入口 - 多Agent统一接收"""

import sys
import os
import threading
import time

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStackedWidget, QPushButton, QLabel, QFrame,
    QListWidget, QListWidgetItem, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from config import load_config, save_config, _ensure_defaults
from agent_chat_panel import AgentChatPanel
from dialogs import GlobalSettingsDialog
from database import save_message
from email_utils import check_mail_connection, fetch_new_messages


class ResearchAgentClient(QMainWindow):
    
    new_message_for_agent = pyqtSignal(str, list)
    
    def __init__(self):
        super().__init__()
        # 加载配置并确保所有 Agent 都有 id
        self.config = _ensure_defaults(load_config())
        self.agent_panels = {}
        self.active_agent_id = None
        self.running = True
        
        os.makedirs(self.config.get("attachment_dir", "./downloads"), exist_ok=True)
        
        self.setWindowTitle("Research Agent")
        self.setGeometry(100, 100, 950, 700)
        self.setMinimumSize(700, 500)
        self._set_style()
        self.setup_ui()
        
        self.new_message_for_agent.connect(self._deliver_message)
        
        if self.config.get("agents"):
            self.agent_list_widget.setCurrentRow(0)
            self.switch_to_agent(0)
        
        self.start_global_receive_thread()
        
        if not self.config.get("auth_code") or len(self.config.get("auth_code", "")) < 8:
            QTimer.singleShot(500, lambda: QMessageBox.information(
                self, "欢迎使用", "请点击右上角「⚙ 设置」配置邮箱和 Agent。"
            ))
    
    def _set_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #EDEDED; }
            QScrollArea { border: none; background-color: #EDEDED; }
            QScrollBar:vertical { background: transparent; width: 5px; }
            QScrollBar::handle:vertical { background: #C0C0C0; border-radius: 2px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        title_frame = QFrame()
        title_frame.setFixedHeight(44)
        title_frame.setStyleSheet("background-color: #EDEDED; border-bottom: 1px solid #D9D9D9;")
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(16, 0, 16, 0)
        
        title_label = QLabel("Research Agent")
        title_label.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        title_label.setStyleSheet("color: #191919; border: none;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        self.settings_btn = QPushButton("⚙ 设置")
        self.settings_btn.setFont(QFont("Microsoft YaHei", 9))
        self.settings_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #576B95; border: 1px solid #D9D9D9; border-radius: 4px; padding: 4px 12px; }
            QPushButton:hover { background-color: #EBEBEB; }
        """)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)
        title_layout.addWidget(self.settings_btn)
        main_layout.addWidget(title_frame)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #D9D9D9; }")
        
        left_frame = QFrame()
        left_frame.setMinimumWidth(120)
        left_frame.setMaximumWidth(170)
        left_frame.setStyleSheet("background-color: #F0F0F0; border-right: 1px solid #D9D9D9;")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        list_header = QLabel("Agent")
        list_header.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        list_header.setFixedHeight(36)
        list_header.setAlignment(Qt.AlignCenter)
        list_header.setStyleSheet("color: #191919; background-color: #F0F0F0; border-bottom: 1px solid #E0E0E0;")
        left_layout.addWidget(list_header)
        
        self.agent_list_widget = QListWidget()
        self.agent_list_widget.setStyleSheet("""
            QListWidget { background-color: #F0F0F0; border: none; font-size: 12px; }
            QListWidget::item { padding: 10px 12px; border-bottom: 1px solid #E8E8E8; color: #191919; }
            QListWidget::item:selected { background-color: #D9D9D9; color: #191919; font-weight: bold; }
            QListWidget::item:hover { background-color: #E5E5E5; }
        """)
        self.agent_list_widget.currentRowChanged.connect(self.switch_to_agent)
        left_layout.addWidget(self.agent_list_widget)
        splitter.addWidget(left_frame)
        
        self.chat_stack = QStackedWidget()
        self.chat_stack.setStyleSheet("background-color: #EDEDED;")
        
        welcome_page = QWidget()
        welcome_layout = QVBoxLayout(welcome_page)
        welcome_layout.setAlignment(Qt.AlignCenter)
        welcome_label = QLabel("👈 选择一个 Agent 开始聊天")
        welcome_label.setFont(QFont("Microsoft YaHei", 14))
        welcome_label.setStyleSheet("color: #B0B0B0;")
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(welcome_label)
        self.chat_stack.addWidget(welcome_page)
        
        splitter.addWidget(self.chat_stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 5)
        main_layout.addWidget(splitter, stretch=1)
        
        self.refresh_agent_list()
    
    def refresh_agent_list(self):
        self.agent_list_widget.blockSignals(True)
        self.agent_list_widget.clear()
        for agent in self.config.get("agents", []):
            item = QListWidgetItem(agent["name"])
            item.setData(Qt.UserRole, agent)
            self.agent_list_widget.addItem(item)
        self.agent_list_widget.blockSignals(False)
        if self.config.get("agents"):
            self.agent_list_widget.setCurrentRow(0)
    
    def switch_to_agent(self, index):
        if index < 0 or index >= len(self.config.get("agents", [])):
            return
        agent_config = self.config["agents"][index]
        agent_id = agent_config.get("id", f"agent_{index}")
        self.active_agent_id = agent_id
        
        if agent_id not in self.agent_panels:
            panel = AgentChatPanel(agent_config, self.config)
            self.agent_panels[agent_id] = panel
            self.chat_stack.addWidget(panel)
            panel.load_history()
        
        self.chat_stack.setCurrentWidget(self.agent_panels[agent_id])
    
    def start_global_receive_thread(self):
        self.global_thread = threading.Thread(target=self._global_receive_loop, daemon=True)
        self.global_thread.start()
    
    def _global_receive_loop(self):
        processed_ids = {}
        time.sleep(2)
        
        while self.running:
            try:
                if not check_mail_connection(self.config):
                    time.sleep(self.config.get("check_interval", 30))
                    continue
                
                # 确保所有 Agent 有 id（运行中可能从设置添加了新 Agent）
                for i, agent in enumerate(self.config.get("agents", [])):
                    if not agent.get("id"):
                        agent["id"] = f"agent_{i+1}"
                
                agents = self.config.get("agents", [])
                
                for agent in agents:
                    agent_id = agent.get("id", "")
                    agent_name = agent.get("name", "?")
                    
                    if not agent_id:
                        continue
                    
                    if agent_id not in processed_ids:
                        processed_ids[agent_id] = set()
                    
                    try:
                        new_msgs, _ = fetch_new_messages(
                            self.config, agent, processed_ids[agent_id]
                        )
                        if new_msgs:
                            for msg in new_msgs:
                                att_names = [a.get("filename", "") if isinstance(a, dict) else a for a in msg.get("attachments", [])]
                                save_message(agent_id, False, msg["content"], msg["time"], att_names)
                            self.new_message_for_agent.emit(agent_id, list(new_msgs))
                    except Exception as e:
                        print(f"[接收:{agent_name}] {e}")
                
            except Exception as e:
                print(f"[全局] {e}")
            
            time.sleep(self.config.get("check_interval", 30))
    
    def _deliver_message(self, agent_id, new_msgs):
        if agent_id in self.agent_panels:
            self.agent_panels[agent_id].receive_messages(new_msgs)
    
    def open_settings(self):
        dialog = GlobalSettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            new_config = dialog.get_config()
            if new_config != self.config:
                # 确保所有 Agent 有 id（新添加的可能没有）
                new_config = _ensure_defaults(new_config)
                
                old_ids = {a.get("id") for a in self.config.get("agents", [])}
                new_ids = {a.get("id") for a in new_config.get("agents", [])}
                
                for aid in old_ids - new_ids:
                    if aid in self.agent_panels:
                        self.chat_stack.removeWidget(self.agent_panels[aid])
                        del self.agent_panels[aid]
                
                self.config = new_config
                save_config(self.config)
                self.refresh_agent_list()
                
                for aid, panel in self.agent_panels.items():
                    for a in self.config["agents"]:
                        if a["id"] == aid:
                            panel.update_config(a, self.config)
                            break
                
                QMessageBox.information(self, "已保存", "配置已更新。")
    
    def closeEvent(self, event):
        self.running = False
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    client = ResearchAgentClient()
    client.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()