#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据库操作模块 - 每个Agent独立数据库"""

import sqlite3
import json
import os

DB_DIR = "agent_databases"
CONFIG_DB = "app_config.db"

# 记录已经初始化的数据库，避免重复日志
_initialized_dbs = set()


def ensure_db_dir():
    """确保数据库目录存在"""
    os.makedirs(DB_DIR, exist_ok=True)


def get_agent_db_path(agent_id):
    """获取 Agent 数据库路径"""
    ensure_db_dir()
    safe_id = "".join(c for c in agent_id if c.isalnum() or c == '_')
    return os.path.join(DB_DIR, f"agent_{safe_id}.db")


def init_agent_db(agent_id):
    """初始化指定 Agent 的数据库（静默，不重复打印）"""
    db_path = get_agent_db_path(agent_id)
    
    # 已经初始化过就跳过
    if db_path in _initialized_dbs:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_me INTEGER NOT NULL,
            content TEXT NOT NULL,
            time TEXT NOT NULL,
            attachments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_info (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    
    _initialized_dbs.add(db_path)
    print(f"[数据库] 初始化: {db_path}")


def save_message(agent_id, is_me, content, time_str, attachments=None):
    """保存消息到 Agent 独立数据库"""
    try:
        init_agent_db(agent_id)  # 内部会跳过已初始化的
        db_path = get_agent_db_path(agent_id)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        att_json = json.dumps(attachments, ensure_ascii=False) if attachments else None
        cursor.execute(
            "INSERT INTO messages (is_me, content, time, attachments) VALUES (?, ?, ?, ?)",
            (1 if is_me else 0, content, time_str, att_json)
        )
        conn.commit()
        conn.close()
        # 不打印，安静保存
    except Exception as e:
        print(f"[数据库] 保存消息失败: {e}")


def load_messages(agent_id):
    """从 Agent 独立数据库加载历史消息"""
    messages = []
    try:
        init_agent_db(agent_id)
        db_path = get_agent_db_path(agent_id)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT is_me, content, time, attachments FROM messages ORDER BY id")
        rows = cursor.fetchall()
        
        for row in rows:
            is_me = bool(row[0])
            content = row[1]
            time_str = row[2]
            att_json = row[3]
            try:
                attachments = json.loads(att_json) if att_json else []
            except:
                attachments = []
            
            messages.append({
                "is_me": is_me,
                "content": content,
                "time": time_str,
                "attachments": attachments
            })
        
        conn.close()
    except Exception as e:
        print(f"[数据库:{agent_id}] 加载失败: {e}")
    
    return messages


# ========== 配置数据库 ==========

def init_config_db():
    """初始化配置数据库"""
    conn = sqlite3.connect(CONFIG_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_config_to_db(config):
    """保存配置到数据库"""
    init_config_db()
    conn = sqlite3.connect(CONFIG_DB)
    cursor = conn.cursor()
    
    config_copy = config.copy()
    if "auth_code" in config_copy:
        config_copy["auth_code"] = _simple_encrypt(config_copy["auth_code"])
    if "agents" in config_copy:
        config_copy["agents"] = json.dumps(config_copy["agents"], ensure_ascii=False)
    
    for key, value in config_copy.items():
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        cursor.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value)
        )
    
    conn.commit()
    conn.close()


def load_config_from_db():
    """从数据库加载配置"""
    init_config_db()
    conn = sqlite3.connect(CONFIG_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, value FROM config")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return None
    
    config = {}
    for key, value in rows:
        if key == "auth_code":
            value = _simple_decrypt(value)
        elif key in ["agents", "smtp_port", "imap_port", "check_interval"]:
            try:
                value = json.loads(value)
            except:
                pass
        config[key] = value
    
    return config


def _simple_encrypt(text):
    result = []
    for i, c in enumerate(text):
        result.append(chr(ord(c) ^ (42 + i % 10)))
    return "".join(result)


def _simple_decrypt(text):
    return _simple_encrypt(text)