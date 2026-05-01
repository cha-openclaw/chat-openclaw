# -*- coding: utf-8 -*-
"""
Created on Fri May  1 11:49:15 2026

@author: hasee
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Agent 邮件网关（简化可跑版）"""

import sys
import imaplib
import email as email_lib
from email.header import decode_header
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import subprocess
import time
import json
import os
import threading
from datetime import datetime
from copy import deepcopy

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QPushButton, QLabel, QFrame, QFileDialog, QMessageBox,
    QFormLayout, QLineEdit, QGroupBox, QListWidget, QListWidgetItem,
    QDialog, QTabWidget, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont, QTextCursor

CONFIG_FILE = "gateway_config.json"

DEFAULT_CONFIG = {"agents": []}

DEFAULT_AGENT = {
    "name": "", "email": "", "auth_code": "",
    "imap_server": "", "imap_port": 993,
    "smtp_server": "", "smtp_port": 465,
    "check_interval": 30,
    "trigger_subject": "", "response_subject": "",
    "attachment_dir": "./attachments"
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # 兼容旧格式
            if "agents" not in config:
                old = {
                    "name": config.get("agent_name", "research"),
                    "email": config.get("agent_email", ""),
                    "auth_code": config.get("auth_code", ""),
                    "imap_server": config.get("imap_server", ""),
                    "imap_port": config.get("imap_port", 993),
                    "smtp_server": config.get("smtp_server", ""),
                    "smtp_port": config.get("smtp_port", 465),
                    "check_interval": config.get("check_interval", 30),
                    "trigger_subject": config.get("trigger_subject", ""),
                    "response_subject": config.get("response_subject", ""),
                    "attachment_dir": config.get("attachment_dir", "./attachments"),
                }
                config["agents"] = [old]
            return config
    return deepcopy(DEFAULT_CONFIG)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


class AgentSignals(QObject):
    log_signal = pyqtSignal(str, str)
    stats_signal = pyqtSignal(str, int)


class AgentWorker(threading.Thread):
    def __init__(self, config, signals):
        super().__init__(daemon=True)
        self.config = config
        self.signals = signals
        self.processed_ids = set()
        self.running = True
        self.name_str = config.get("name", "unknown")
        self.attachment_dir = config.get("attachment_dir", "./attachments")
        self.processed_count = 0
        os.makedirs(self.attachment_dir, exist_ok=True)

    def log(self, msg):
        self.signals.log_signal.emit(self.name_str, msg)

    def decode_subject(self, subject):
        if not subject: return ""
        decoded = decode_header(subject)
        parts = []
        for c, enc in decoded:
            parts.append(c.decode(enc or "utf-8", errors="ignore") if isinstance(c, bytes) else str(c))
        return "".join(parts)

    def get_email_content(self, msg):
        body = ""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                cd = str(part.get("Content-Disposition", ""))
                if ct == "text/plain" and "attachment" not in cd:
                    try:
                        p = part.get_payload(decode=True)
                        if p: body = p.decode("utf-8", errors="ignore")
                    except: body = str(part.get_payload())
                elif "attachment" in cd:
                    fn = part.get_filename()
                    if fn:
                        dfn = self.decode_subject(fn)
                        fp = self.save_attachment(part, dfn)
                        if fp: attachments.append({"filename": dfn, "filepath": fp})
        else:
            try:
                p = msg.get_payload(decode=True)
                if p: body = p.decode("utf-8", errors="ignore")
            except: body = str(msg.get_payload())
        return body.strip() if body else "", attachments

    def save_attachment(self, part, filename):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(filename)
            sp = os.path.join(self.attachment_dir, f"{name}_{ts}{ext}")
            with open(sp, "wb") as f: f.write(part.get_payload(decode=True))
            return sp
        except: return None

    def ask_openclaw(self, question, attachments=None):
        if attachments:
            info = "\n\n附件:\n" + "\n".join(f"- {a['filename']} ({a['filepath']})" for a in attachments)
            question += info
        self.log("调用 OpenClaw...")
        try:
            r = subprocess.run(["openclaw", "agent", "--agent", self.name_str, "--message", question],
                               capture_output=True, text=True, timeout=300, encoding="utf-8", errors="ignore")
            if r.returncode == 0:
                out = r.stdout.strip()
                text, files = out, []
                if "---FILES---" in out:
                    a, b = out.split("---FILES---", 1)
                    text = a.strip()
                    if "---END---" in b:
                        for line in b.split("---END---")[0].strip().split("\n"):
                            if line.strip() and os.path.exists(line.strip()):
                                files.append(line.strip())
                return text or "(空)", files
            return f"[错误] {r.stderr.strip() or '未知'}", []
        except subprocess.TimeoutExpired: return "(超时)", []
        except FileNotFoundError: return "(openclaw未安装)", []
        except Exception as e: return f"(异常:{e})", []

    def send_response(self, to_email, question, answer, files=None):
        try:
            msg = MIMEMultipart()
            msg["From"] = self.config["email"]
            msg["To"] = to_email
            msg["Subject"] = self.config["response_subject"]
            body = f"回复: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'-'*40}\n{answer}"
            msg.attach(MIMEText(body, "plain", "utf-8"))
            if files:
                for fp in files:
                    if os.path.exists(fp):
                        with open(fp, "rb") as f:
                            p = MIMEBase("application", "octet-stream")
                            p.set_payload(f.read())
                            encoders.encode_base64(p)
                            p.add_header("Content-Disposition", f"attachment; filename={os.path.basename(fp)}")
                            msg.attach(p)
            with smtplib.SMTP_SSL(self.config["smtp_server"], self.config["smtp_port"]) as s:
                s.login(self.config["email"], self.config["auth_code"])
                s.send_message(msg)
            self.log(f"回复已发送至 {to_email}")
            self.processed_count += 1
            self.signals.stats_signal.emit(self.name_str, self.processed_count)
            return True
        except Exception as e:
            self.log(f"发送失败: {e}")
            return False

    def process_inbox(self):
        try:
            mail = imaplib.IMAP4_SSL(self.config["imap_server"], self.config["imap_port"])
            mail.login(self.config["email"], self.config["auth_code"])
            mail.select("INBOX", readonly=False)
            status, data = mail.search(None, "UNSEEN")
            if status == "OK" and data[0]:
                for num in data[0].split():
                    status, msg_data = mail.fetch(num, "(RFC822)")
                    if status != "OK": continue
                    for part in msg_data:
                        if isinstance(part, tuple):
                            msg = email_lib.message_from_bytes(part[1])
                            mid = msg.get("Message-ID", "")
                            if mid in self.processed_ids: continue
                            sender = email_lib.utils.parseaddr(msg["From"] or "")[1]
                            subject = self.decode_subject(msg["Subject"])
                            if subject != self.config["trigger_subject"]: continue
                            body, atts = self.get_email_content(msg)
                            if not body and not atts: continue
                            self.log(f"收到来自 {sender} 的请求")
                            answer, files = self.ask_openclaw(body if body else "请查看附件", atts)
                            self.send_response(sender, body, answer, files)
                            if mid: self.processed_ids.add(mid)
                    mail.store(num, "+FLAGS", "\\Seen")
            mail.logout()
        except Exception as e:
            self.log(f"检查出错: {e}")

    def run(self):
        self.log("已启动")
        while self.running:
            try: self.process_inbox()
            except Exception as e: self.log(f"异常: {e}")
            for _ in range(self.config.get("check_interval", 30)):
                if not self.running: break
                time.sleep(1)
        self.log("已停止")

    def stop(self):
        self.running = False


# ========== 界面 ==========
class AgentEditDialog(QDialog):
    def __init__(self, agent_config=None, parent=None):
        super().__init__(parent)
        self.cfg = agent_config or deepcopy(DEFAULT_AGENT)
        self.setWindowTitle("添加 Agent" if agent_config is None else "编辑 Agent")
        self.setMinimumSize(500, 450)
        self.setStyleSheet("QDialog{background:#F7F7F7} QLabel{color:#555;font-size:13px} QLineEdit{border:1px solid #D9D9D9;border-radius:4px;padding:8px 10px;background:#fff;color:#191919;font-size:13px} QLineEdit:focus{border-color:#7ECF8C}")
        self._ui()

    def _ui(self):
        lo = QVBoxLayout(self); lo.setContentsMargins(24,20,24,20); lo.setSpacing(12)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet("QScrollArea{border:none}")
        w = QWidget(); fl = QVBoxLayout(w); fl.setSpacing(14)
        gs = "QGroupBox{font-weight:bold;font-size:13px;border:1px solid #D9D9D9;border-radius:8px;margin-top:10px;padding-top:20px;background:#fff} QGroupBox::title{subcontrol-origin:margin;left:16px;padding:0 8px}"

        g1 = QGroupBox("基本信息"); g1.setStyleSheet(gs); f1 = QFormLayout(g1); f1.setSpacing(10)
        self.ne = QLineEdit(self.cfg.get("name","")); self.ne.setPlaceholderText("Agent名称"); f1.addRow("名称：",self.ne)
        self.ee = QLineEdit(self.cfg.get("email","")); self.ee.setPlaceholderText("邮箱"); f1.addRow("邮箱：",self.ee)
        self.ae = QLineEdit(self.cfg.get("auth_code","")); self.ae.setEchoMode(QLineEdit.Password); f1.addRow("授权码：",self.ae)
        fl.addWidget(g1)

        g2 = QGroupBox("服务器"); g2.setStyleSheet(gs); f2 = QFormLayout(g2); f2.setSpacing(10)
        self.ie = QLineEdit(self.cfg.get("imap_server","")); f2.addRow("IMAP：",self.ie)
        self.ip = QLineEdit(str(self.cfg.get("imap_port",993))); f2.addRow("IMAP端口：",self.ip)
        self.se = QLineEdit(self.cfg.get("smtp_server","")); f2.addRow("SMTP：",self.se)
        self.sp = QLineEdit(str(self.cfg.get("smtp_port",465))); f2.addRow("SMTP端口：",self.sp)
        fl.addWidget(g2)

        g3 = QGroupBox("通信"); g3.setStyleSheet(gs); f3 = QFormLayout(g3); f3.setSpacing(10)
        self.te = QLineEdit(self.cfg.get("trigger_subject","")); f3.addRow("触发主题：",self.te)
        self.re = QLineEdit(self.cfg.get("response_subject","")); f3.addRow("回复主题：",self.re)
        self.ci = QLineEdit(str(self.cfg.get("check_interval",30))); f3.addRow("间隔(秒)：",self.ci)
        self.ad = QLineEdit(self.cfg.get("attachment_dir","./attachments"))
        dl = QHBoxLayout(); dl.addWidget(self.ad)
        bb = QPushButton("浏览"); bb.setStyleSheet("QPushButton{background:#F7F7F7;color:#576B95;border:1px solid #D9D9D9;border-radius:4px;padding:8px 14px} QPushButton:hover{background:#EBEBEB}")
        bb.clicked.connect(lambda: QFileDialog.getExistingDirectory(self,"选择目录") and self.ad.setText(QFileDialog.getExistingDirectory(self,"选择目录")))
        dl.addWidget(bb); dw = QWidget(); dw.setLayout(dl); f3.addRow("附件目录：",dw)
        fl.addWidget(g3)

        sc.setWidget(w); lo.addWidget(sc)
        bl = QHBoxLayout(); bl.addStretch()
        cb = QPushButton("取消"); cb.setMinimumSize(90,34); cb.setStyleSheet("QPushButton{background:#F7F7F7;color:#555;border:1px solid #D9D9D9;border-radius:6px} QPushButton:hover{background:#EBEBEB}")
        cb.clicked.connect(self.reject); bl.addWidget(cb)
        sb = QPushButton("保存"); sb.setMinimumSize(90,34); sb.setStyleSheet("QPushButton{background:#7ECF8C;color:#fff;border:none;border-radius:6px;font-weight:bold} QPushButton:hover{background:#6BBF7A}")
        sb.clicked.connect(self._save); bl.addWidget(sb)
        lo.addLayout(bl)

    def _save(self):
        if not self.ne.text().strip(): return QMessageBox.warning(self,"提示","请输入名称")
        if not self.ee.text().strip(): return QMessageBox.warning(self,"提示","请输入邮箱")
        self.cfg = {"name":self.ne.text().strip(),"email":self.ee.text().strip(),"auth_code":self.ae.text().strip(),
                     "imap_server":self.ie.text().strip(),"imap_port":int(self.ip.text().strip() or "993"),
                     "smtp_server":self.se.text().strip(),"smtp_port":int(self.sp.text().strip() or "465"),
                     "check_interval":int(self.ci.text().strip() or "30"),
                     "trigger_subject":self.te.text().strip(),"response_subject":self.re.text().strip(),
                     "attachment_dir":self.ad.text().strip()}
        self.accept()
    def get_config(self): return self.cfg


class GatewayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.workers = {}
        self.signals = AgentSignals()
        self.running = False
        self.signals.log_signal.connect(self._append_log)
        self.signals.stats_signal.connect(self._update_stats)

        self.setWindowTitle("AI Agent 邮件网关")
        self.setMinimumSize(800, 650); self.resize(850, 700)
        self.setStyleSheet("QMainWindow{background:#F7F7F7}")
        self._ui()
        self._refresh_list()

    def _ui(self):
        c = QWidget(); self.setCentralWidget(c)
        lo = QVBoxLayout(c); lo.setContentsMargins(16,12,16,12); lo.setSpacing(10)

        h = QHBoxLayout()
        t = QLabel("🤖 AI Agent 邮件网关"); t.setFont(QFont("Microsoft YaHei",16,QFont.Bold)); t.setStyleSheet("color:#191919")
        h.addWidget(t); h.addStretch()
        self.sb = QPushButton("▶ 启动网关"); self.sb.setFont(QFont("Microsoft YaHei",10)); self.sb.setMinimumSize(120,36)
        self.sb.setStyleSheet("QPushButton{background:#2FA84D;color:#fff;border:none;border-radius:6px;font-weight:bold} QPushButton:hover{background:#269140}")
        self.sb.clicked.connect(self._toggle); h.addWidget(self.sb)
        lo.addLayout(h)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane{border:1px solid #D9D9D9;border-radius:6px;background:#fff}")

        # 日志
        lt = QWidget(); ll = QVBoxLayout(lt); ll.setContentsMargins(8,8,8,8)
        self.log_txt = QTextEdit(); self.log_txt.setReadOnly(True); self.log_txt.setFont(QFont("Consolas",9))
        self.log_txt.setStyleSheet("QTextEdit{border:none;background:#FAFAFA;color:#333}")
        ll.addWidget(self.log_txt); self.tabs.addTab(lt,"📋 实时日志")

        # 统计
        st = QWidget(); sl = QVBoxLayout(st); sl.setContentsMargins(16,16,16,16)
        self.stats_lbl = QLabel("暂无数据"); self.stats_lbl.setFont(QFont("Microsoft YaHei",11))
        self.stats_lbl.setStyleSheet("color:#555"); self.stats_lbl.setAlignment(Qt.AlignTop)
        sl.addWidget(self.stats_lbl); sl.addStretch(); self.tabs.addTab(st,"📊 统计")

        # 配置
        ct = QWidget(); cl = QVBoxLayout(ct); cl.setContentsMargins(8,8,8,8)
        self.alist = QListWidget()
        self.alist.setStyleSheet("QListWidget{border:1px solid #D9D9D9;border-radius:4px;background:#fff;font-size:13px} QListWidget::item{padding:8px 12px;border-bottom:1px solid #F0F0F0} QListWidget::item:selected{background:#E8F8E8}")
        cl.addWidget(self.alist)
        bl = QHBoxLayout(); bl.setSpacing(8)
        ab = QPushButton("＋ 添加"); ab.setStyleSheet("QPushButton{background:#7ECF8C;color:#fff;border:none;border-radius:4px;padding:8px 20px;font-weight:bold} QPushButton:hover{background:#6BBF7A}")
        ab.clicked.connect(self._add); bl.addWidget(ab)
        eb = QPushButton("✎ 编辑"); eb.setStyleSheet("QPushButton{background:#F7F7F7;color:#576B95;border:1px solid #D9D9D9;border-radius:4px;padding:8px 20px} QPushButton:hover{background:#EBEBEB}")
        eb.clicked.connect(self._edit); bl.addWidget(eb)
        db = QPushButton("✕ 删除"); db.setStyleSheet("QPushButton{background:#F7F7F7;color:#FA5151;border:1px solid #D9D9D9;border-radius:4px;padding:8px 20px} QPushButton:hover{background:#FFF0F0}")
        db.clicked.connect(self._delete); bl.addWidget(db); bl.addStretch()
        cl.addLayout(bl); self.tabs.addTab(ct,"⚙ 配置")

        lo.addWidget(self.tabs)

    def _refresh_list(self):
        self.alist.clear()
        for a in self.config.get("agents",[]):
            self.alist.addItem(f"{a['name']} → {a['email']} | 触发:{a['trigger_subject']}")

    def _append_log(self, name, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        color = "#2FA84D" if "成功" in msg or "已发送" in msg else "#333"
        if "错误" in msg or "失败" in msg: color = "#FA5151"
        elif "收到" in msg: color = "#1485EE"
        self.log_txt.append(f'<span style="color:#888">[{ts}]</span> <b>[{name}]</b> <span style="color:{color}">{msg}</span>')
        self.log_txt.moveCursor(QTextCursor.End)

    def _update_stats(self, name, count):
        txt = ""
        for n, w in self.workers.items():
            txt += f"{'🟢' if w.running else '🔴'} <b>{n}</b>: 处理 {w.processed_count} 封 | {w.config['email']} | {w.config['trigger_subject']}\n"
        self.stats_lbl.setText(txt or "暂无运行中的 Agent")

    def _toggle(self):
        if self.running: self._stop()
        else: self._start()

    def _start(self):
        agents = self.config.get("agents", [])
        if not agents: return QMessageBox.warning(self,"提示","请先添加 Agent")
        self.running = True
        self.sb.setText("⏹ 停止网关"); self.sb.setStyleSheet("QPushButton{background:#FA5151;color:#fff;border:none;border-radius:6px;font-weight:bold} QPushButton:hover{background:#D32F2F}")
        for a in agents:
            w = AgentWorker(a, self.signals)
            w.start()
            self.workers[a["name"]] = w
        self._append_log("SYSTEM", f"网关已启动，共 {len(agents)} 个 Agent")

    def _stop(self):
        self.running = False
        self.sb.setText("▶ 启动网关"); self.sb.setStyleSheet("QPushButton{background:#2FA84D;color:#fff;border:none;border-radius:6px;font-weight:bold} QPushButton:hover{background:#269140}")
        for w in self.workers.values(): w.stop()
        self.workers.clear()
        self._append_log("SYSTEM", "网关已停止")

    def _add(self):
        d = AgentEditDialog(parent=self)
        if d.exec_() == QDialog.Accepted:
            self.config.setdefault("agents",[]).append(d.get_config())
            self._refresh_list(); save_config(self.config)

    def _edit(self):
        i = self.alist.currentRow()
        if i < 0: return QMessageBox.information(self,"提示","请先选一个 Agent")
        d = AgentEditDialog(self.config["agents"][i], self)
        if d.exec_() == QDialog.Accepted:
            self.config["agents"][i] = d.get_config()
            self._refresh_list(); save_config(self.config)

    def _delete(self):
        i = self.alist.currentRow()
        if i < 0: return QMessageBox.information(self,"提示","请先选一个 Agent")
        if QMessageBox.question(self,"确认","确定删除？",QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            del self.config["agents"][i]
            self._refresh_list(); save_config(self.config)

    def closeEvent(self, e):
        if self.running: self._stop()
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    win = GatewayWindow()
    win.show()
    sys.exit(app.exec_())