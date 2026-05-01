#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置对话框模块"""

from copy import deepcopy

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton,
    QLabel, QFrame, QFileDialog, QMessageBox, QFormLayout, QLineEdit,
    QGroupBox, QListWidget, QListWidgetItem, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class AgentEditDialog(QDialog):
    """Agent 添加/编辑对话框"""
    
    def __init__(self, agent_config=None, parent=None):
        super().__init__(parent)
        self.agent_config = agent_config or {
            "id": "", "name": "", "email": "",
            "send_subject": "", "receive_subject": ""
        }
        self.is_new = agent_config is None
        self.setWindowTitle("添加 Agent" if self.is_new else "编辑 Agent")
        self.setMinimumSize(450, 350)
        self.setStyleSheet("""
            QDialog { background-color: #F7F7F7; }
            QLabel { color: #555555; font-size: 13px; }
            QLineEdit { border: 1px solid #D9D9D9; border-radius: 4px; padding: 8px 10px; background-color: white; color: #191919; font-size: 13px; }
            QLineEdit:focus { border-color: #7ECF8C; }
        """)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        group = QGroupBox("Agent 信息")
        group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 13px; border: 1px solid #D9D9D9; border-radius: 8px; margin-top: 14px; padding-top: 20px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; color: #191919; }
        """)
        form = QFormLayout(group)
        form.setContentsMargins(20, 24, 20, 16)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)
        
        self.name_input = QLineEdit(self.agent_config.get("name", ""))
        self.name_input.setPlaceholderText("Agent 显示名称")
        form.addRow("名称：", self.name_input)
        
        self.email_input = QLineEdit(self.agent_config.get("email", ""))
        self.email_input.setPlaceholderText("Agent 邮箱地址")
        form.addRow("邮箱：", self.email_input)
        
        self.send_subject_input = QLineEdit(self.agent_config.get("send_subject", ""))
        self.send_subject_input.setPlaceholderText("发送邮件的主题标识")
        form.addRow("发送主题：", self.send_subject_input)
        
        self.receive_subject_input = QLineEdit(self.agent_config.get("receive_subject", ""))
        self.receive_subject_input.setPlaceholderText("接收邮件的主题标识")
        form.addRow("接收主题：", self.receive_subject_input)
        
        layout.addWidget(group)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(QFont("Microsoft YaHei", 10))
        cancel_btn.setMinimumSize(90, 34)
        cancel_btn.setStyleSheet("""
            QPushButton { background-color: #F7F7F7; color: #555555; border: 1px solid #D9D9D9; border-radius: 6px; }
            QPushButton:hover { background-color: #EBEBEB; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setFont(QFont("Microsoft YaHei", 10))
        save_btn.setMinimumSize(90, 34)
        save_btn.setStyleSheet("""
            QPushButton { background-color: #7ECF8C; color: white; border: none; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #6BBF7A; }
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
    
    def _on_save(self):
        name = self.name_input.text().strip()
        email_addr = self.email_input.text().strip()
        if not name:
            QMessageBox.warning(self, "验证失败", "请输入 Agent 名称")
            return
        if not email_addr:
            QMessageBox.warning(self, "验证失败", "请输入 Agent 邮箱")
            return
        self.agent_config = {
            "id": self.agent_config.get("id", ""),
            "name": name,
            "email": email_addr,
            "send_subject": self.send_subject_input.text().strip(),
            "receive_subject": self.receive_subject_input.text().strip()
        }
        self.accept()
    
    def get_agent_config(self):
        return self.agent_config


class GlobalSettingsDialog(QDialog):
    """全局设置 + Agent 管理"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = deepcopy(config)
        self.setWindowTitle("设置")
        self.setMinimumSize(560, 500)
        self.resize(560, 600)
        self.setStyleSheet("""
            QDialog { background-color: #F7F7F7; }
            QGroupBox { font-weight: bold; font-size: 13px; border: 1px solid #D9D9D9; border-radius: 8px; margin-top: 14px; padding-top: 20px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; color: #191919; }
            QLabel { color: #555555; font-size: 13px; }
            QLineEdit { border: 1px solid #D9D9D9; border-radius: 4px; padding: 8px 10px; background-color: white; color: #191919; font-size: 13px; }
            QLineEdit:focus { border-color: #7ECF8C; }
        """)
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #F7F7F7; }")
        
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #F7F7F7;")
        layout = QVBoxLayout(scroll_widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        # ===== 邮箱设置 =====
        email_group = QGroupBox("📧 邮箱服务器设置")
        email_form = QFormLayout(email_group)
        email_form.setContentsMargins(20, 24, 20, 16)
        email_form.setSpacing(12)
        email_form.setLabelAlignment(Qt.AlignRight)
        
        self.email_input = QLineEdit(self.config.get("your_email", ""))
        self.email_input.setPlaceholderText("你的邮箱地址")
        email_form.addRow("邮箱地址：", self.email_input)
        
        self.auth_input = QLineEdit(self.config.get("auth_code", ""))
        self.auth_input.setPlaceholderText("邮箱授权码")
        self.auth_input.setEchoMode(QLineEdit.Password)
        email_form.addRow("授权码：", self.auth_input)
        
        self.smtp_server_input = QLineEdit(self.config.get("smtp_server", ""))
        self.smtp_server_input.setPlaceholderText("smtp.example.com")
        email_form.addRow("SMTP 服务器：", self.smtp_server_input)
        
        self.smtp_port_input = QLineEdit(str(self.config.get("smtp_port", 465)))
        self.smtp_port_input.setPlaceholderText("465")
        email_form.addRow("SMTP 端口：", self.smtp_port_input)
        
        self.imap_server_input = QLineEdit(self.config.get("imap_server", ""))
        self.imap_server_input.setPlaceholderText("imap.example.com")
        email_form.addRow("IMAP 服务器：", self.imap_server_input)
        
        self.imap_port_input = QLineEdit(str(self.config.get("imap_port", 993)))
        self.imap_port_input.setPlaceholderText("993")
        email_form.addRow("IMAP 端口：", self.imap_port_input)
        
        self.interval_input = QLineEdit(str(self.config.get("check_interval", 30)))
        self.interval_input.setPlaceholderText("30")
        email_form.addRow("检查间隔(秒)：", self.interval_input)
        
        self.attach_dir_input = QLineEdit(self.config.get("attachment_dir", "./downloads"))
        self.attach_dir_input.setPlaceholderText("./downloads")
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.attach_dir_input)
        browse_btn = QPushButton("浏览...")
        browse_btn.setStyleSheet("""
            QPushButton { background-color: #F7F7F7; color: #576B95; border: 1px solid #D9D9D9; border-radius: 4px; padding: 8px 14px; }
            QPushButton:hover { background-color: #EBEBEB; }
        """)
        browse_btn.clicked.connect(lambda: self._browse_dir(self.attach_dir_input))
        dir_layout.addWidget(browse_btn)
        dir_widget = QWidget()
        dir_widget.setLayout(dir_layout)
        email_form.addRow("附件目录：", dir_widget)
        
        layout.addWidget(email_group)
        
        # ===== Agent 管理 =====
        agent_group = QGroupBox("🤖 Agent 管理")
        agent_layout = QVBoxLayout(agent_group)
        agent_layout.setContentsMargins(20, 24, 20, 16)
        agent_layout.setSpacing(10)
        
        self.agent_list = QListWidget()
        self.agent_list.setStyleSheet("""
            QListWidget { border: 1px solid #D9D9D9; border-radius: 4px; background-color: white; font-size: 13px; }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #F0F0F0; }
            QListWidget::item:selected { background-color: #E8F8E8; color: #191919; }
            QListWidget::item:hover { background-color: #F5F5F5; }
        """)
        self.agent_list.setMinimumHeight(120)
        self._refresh_agent_list()
        agent_layout.addWidget(self.agent_list)
        
        agent_btn_layout = QHBoxLayout()
        agent_btn_layout.setSpacing(8)
        
        add_btn = QPushButton("＋ 添加 Agent")
        add_btn.setStyleSheet("""
            QPushButton { background-color: #7ECF8C; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #6BBF7A; }
        """)
        add_btn.clicked.connect(self._add_agent)
        agent_btn_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✎ 编辑")
        edit_btn.setStyleSheet("""
            QPushButton { background-color: #F7F7F7; color: #576B95; border: 1px solid #D9D9D9; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #EBEBEB; }
        """)
        edit_btn.clicked.connect(self._edit_agent)
        agent_btn_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("✕ 删除")
        delete_btn.setStyleSheet("""
            QPushButton { background-color: #F7F7F7; color: #FA5151; border: 1px solid #D9D9D9; border-radius: 4px; padding: 8px 16px; }
            QPushButton:hover { background-color: #FFF0F0; border-color: #FA5151; }
        """)
        delete_btn.clicked.connect(self._delete_agent)
        agent_btn_layout.addWidget(delete_btn)
        agent_btn_layout.addStretch()
        agent_layout.addLayout(agent_btn_layout)
        layout.addWidget(agent_group)
        
        layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area, stretch=1)
        
        # 底部按钮
        btn_frame = QFrame()
        btn_frame.setStyleSheet("QFrame { background-color: white; border-top: 1px solid #E0E0E0; }")
        btn_frame.setMinimumHeight(60)
        btn_layout2 = QHBoxLayout(btn_frame)
        btn_layout2.setContentsMargins(24, 12, 24, 12)
        btn_layout2.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(QFont("Microsoft YaHei", 10))
        cancel_btn.setMinimumSize(90, 34)
        cancel_btn.setStyleSheet("""
            QPushButton { background-color: #F7F7F7; color: #555555; border: 1px solid #D9D9D9; border-radius: 6px; }
            QPushButton:hover { background-color: #EBEBEB; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout2.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存设置")
        save_btn.setFont(QFont("Microsoft YaHei", 10))
        save_btn.setMinimumSize(100, 34)
        save_btn.setStyleSheet("""
            QPushButton { background-color: #7ECF8C; color: white; border: none; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #6BBF7A; }
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout2.addWidget(save_btn)
        
        main_layout.addWidget(btn_frame)
    
    def _browse_dir(self, line_edit):
        dir_path = QFileDialog.getExistingDirectory(self, "选择目录")
        if dir_path:
            line_edit.setText(dir_path)
    
    def _refresh_agent_list(self):
        self.agent_list.clear()
        for agent in self.config.get("agents", []):
            item = QListWidgetItem(f"{agent['name']}  ({agent['email']})")
            item.setData(Qt.UserRole, agent)
            self.agent_list.addItem(item)
    
    def _add_agent(self):
        dialog = AgentEditDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.config.setdefault("agents", []).append(dialog.get_agent_config())
            self._refresh_agent_list()
    
    def _edit_agent(self):
        current = self.agent_list.currentItem()
        if not current:
            QMessageBox.information(self, "提示", "请先选择一个 Agent")
            return
        agent = current.data(Qt.UserRole)
        dialog = AgentEditDialog(agent, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            index = self.agent_list.currentRow()
            self.config["agents"][index] = dialog.get_agent_config()
            self._refresh_agent_list()
    
    def _delete_agent(self):
        current = self.agent_list.currentItem()
        if not current:
            QMessageBox.information(self, "提示", "请先选择一个 Agent")
            return
        agent = current.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 Agent「{agent['name']}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            index = self.agent_list.currentRow()
            del self.config["agents"][index]
            self._refresh_agent_list()
    
    def _on_save(self):
        if not self.email_input.text().strip():
            QMessageBox.warning(self, "验证失败", "请输入邮箱地址")
            return
        for field, name in [
            (self.smtp_port_input, "SMTP 端口"),
            (self.imap_port_input, "IMAP 端口"),
            (self.interval_input, "检查间隔")
        ]:
            try:
                int(field.text().strip())
            except ValueError:
                QMessageBox.warning(self, "验证失败", f"{name}必须为数字")
                return
        if not self.config.get("agents"):
            QMessageBox.warning(self, "验证失败", "请至少添加一个 Agent")
            return
        
        self.config.update({
            "your_email": self.email_input.text().strip(),
            "auth_code": self.auth_input.text().strip(),
            "smtp_server": self.smtp_server_input.text().strip(),
            "smtp_port": int(self.smtp_port_input.text().strip()),
            "imap_server": self.imap_server_input.text().strip(),
            "imap_port": int(self.imap_port_input.text().strip()),
            "check_interval": int(self.interval_input.text().strip()),
            "attachment_dir": self.attach_dir_input.text().strip(),
        })
        self.accept()
    
    def get_config(self):
        return self.config