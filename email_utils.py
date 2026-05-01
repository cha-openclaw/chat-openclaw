#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""邮件收发工具模块 - 支持 SSL/TLS"""

import smtplib
import imaplib
import email
import os
import socket
from datetime import datetime
from email.header import decode_header, Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


def decode_subject(subject):
    """解码邮件标题"""
    if not subject:
        return ""
    decoded = decode_header(subject)
    parts = []
    for content, encoding in decoded:
        if isinstance(content, bytes):
            parts.append(content.decode(encoding or "utf-8", errors="ignore"))
        else:
            parts.append(str(content))
    return "".join(parts)


def get_email_content(msg, attachment_dir="./downloads"):
    """提取邮件正文和附件"""
    body = ""
    attachments = []
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="ignore")
                except:
                    body = str(part.get_payload())
            elif "attachment" in content_disposition or content_type.startswith("application/"):
                filename = part.get_filename()
                if filename:
                    decoded_filename = decode_subject(filename)
                    filepath = save_attachment_data(part, decoded_filename, attachment_dir)
                    if filepath:
                        attachments.append({
                            "filename": decoded_filename,
                            "filepath": filepath
                        })
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="ignore")
        except:
            body = str(msg.get_payload())
    
    return body.strip() if body else "", attachments


def save_attachment_data(part, filename, download_dir="./downloads"):
    """保存附件到本地"""
    try:
        os.makedirs(download_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        safe_filename = f"{name}_{timestamp}{ext}"
        filepath = os.path.join(download_dir, safe_filename)
        
        with open(filepath, "wb") as f:
            f.write(part.get_payload(decode=True))
        print(f"[附件] 保存: {filepath}")
        return filepath
    except Exception as e:
        print(f"[附件] 保存失败: {e}")
        return None


def clean_response(body):
    """清理邮件回复中的元信息"""
    if not body:
        return ""
    lines = body.split("\n")
    result = []
    in_content = False
    
    for line in lines:
        if line.startswith("-" * 10):
            in_content = True
            continue
        if in_content:
            result.append(line)
    
    return "\n".join(result).strip() if result else body.strip()


def check_mail_connection(config):
    """检测邮箱服务器连接状态"""
    try:
        # IMAP 收件
        imap_port = config.get("imap_port", 993)
        if imap_port == 993:
            mail = imaplib.IMAP4_SSL(config["imap_server"], imap_port)
        else:
            mail = imaplib.IMAP4(config["imap_server"], imap_port)
            mail.starttls()
        mail.login(config["your_email"], config["auth_code"])
        mail.logout()
        return True
    except:
        return False


def _connect_imap(config):
    """连接 IMAP 服务器，自动判断 SSL/TLS"""
    server = config["imap_server"]
    port = config.get("imap_port", 993)
    
    if port == 993:
        mail = imaplib.IMAP4_SSL(server, port)
    else:
        mail = imaplib.IMAP4(server, port)
        mail.starttls()
    
    # ===== 163 网易邮箱需要发送 ID 命令 =====
    if "163.com" in server or "126.com" in server or "yeah.net" in server:
        try:
            imap_id = ('name', 'ResearchAgent', 'version', '1.0', 'vendor', 'Client')
            mail.xatom('ID', '("' + '" "'.join(imap_id) + '")')
        except:
            pass  # 不支持的服务器就跳过
    
    return mail


def _connect_smtp(config):
    """连接 SMTP 服务器，自动判断 SSL/TLS"""
    server = config["smtp_server"]
    port = config.get("smtp_port", 465)
    
    if port == 465:
        # SSL 直连
        return smtplib.SMTP_SSL(server, port, timeout=30)
    else:
        # STARTTLS
        smtp = smtplib.SMTP(server, port, timeout=30)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        return smtp


def fetch_new_messages(config, agent_config, processed_ids):
    new_messages = []
    delete_list = []
    attachment_dir = config.get("attachment_dir", "./downloads")
    max_fetch = int(config.get("max_fetch_count", 100))
    
    try:
        mail = _connect_imap(config)
        mail.login(config["your_email"], config["auth_code"])
        mail.select("INBOX", readonly=False)
        
        status, data = mail.search(None, "ALL")
        if status != "OK" or not data[0]:
            mail.logout()
            return new_messages, delete_list
        
        all_nums = data[0].split()
        total = len(all_nums)
        recent_nums = all_nums[-max_fetch:] if total > max_fetch else all_nums
        
        # 两个条件都必须匹配
        agent_email = agent_config["email"].strip().lower()
        receive_subject = agent_config["receive_subject"].strip().lower()
        
        for num in recent_nums:
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    msg_id = msg.get("Message-ID", "")
                    
                    if msg_id and msg_id in processed_ids:
                        continue
                    
                    sender = email.utils.parseaddr(msg["From"] or "")[1].lower()
                    subject = (decode_subject(msg["Subject"]) or "").strip().lower()
                    
                    # 邮箱和 subject 同时匹配
                    if agent_email != sender:
                        continue
                    if receive_subject and receive_subject != subject:
                        continue
                    
                    body, attachments = get_email_content(msg, attachment_dir)
                    if not body and not attachments:
                        continue
                    
                    try:
                        t = email.utils.parsedate_to_datetime(msg.get("Date", ""))
                        time_str = t.strftime("%m-%d %H:%M")
                    except:
                        time_str = datetime.now().strftime("%m-%d %H:%M")
                    
                    new_messages.append({
                        "is_me": False,
                        "content": clean_response(body),
                        "time": time_str,
                        "attachments": attachments
                    })
                    
                    if msg_id:
                        processed_ids.add(msg_id)
                    delete_list.append(num)
        
        for num in delete_list:
            mail.store(num, "+FLAGS", "\\Deleted")
        if delete_list:
            mail.expunge()
        
        mail.logout()
        
    except Exception as e:
        print(f"[邮件] {e}")
    
    return new_messages, delete_list

def send_email(config, agent_config, content, attachments_to_send):
    """发送邮件"""
    msg = MIMEMultipart()
    msg["From"] = config["your_email"]
    msg["To"] = agent_config["email"]
    msg["Subject"] = agent_config["send_subject"]
    
    body = f"{content}\n\n-- \n发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    for filepath in attachments_to_send:
        if not os.path.exists(filepath):
            continue
        
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.gif': 'image/gif',
            '.txt': 'text/plain', '.csv': 'text/csv',
            '.json': 'application/json', '.zip': 'application/zip',
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')
        main_type, sub_type = mime_type.split('/', 1)
        
        with open(filepath, "rb") as f:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
            encoders.encode_base64(part)
            encoded_filename = Header(filename, 'utf-8').encode()
            part.add_header("Content-Disposition", "attachment", filename=encoded_filename)
            msg.attach(part)
    
    server = _connect_smtp(config)
    server.login(config["your_email"], config["auth_code"])
    server.send_message(msg)
    server.quit()