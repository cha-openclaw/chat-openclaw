#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置管理模块"""

import os
import json
from database import load_config_from_db, save_config_to_db

CONFIG_FILE = "client_config.json"

DEFAULT_CONFIG = {
    "your_email": "",
    "auth_code": "",
    "imap_server": "",
    "imap_port": 993,
    "smtp_server": "",
    "smtp_port": 465,
    "check_interval": 30,
    "attachment_dir": "./downloads",
    "max_fetch_count": 100,
    "agents": []
}


def load_config():
    # 1. 先尝试数据库
    db_config = load_config_from_db()
    if db_config:
        return _ensure_defaults(db_config)
    
    # 2. 再尝试 JSON 文件
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        if config.get("your_email"):  # 有实际内容
            save_config_to_db(config)  # 迁移到数据库
            return _ensure_defaults(config)
    
    # 3. 都没找到，保存默认空配置（不覆盖已有）
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    
    return DEFAULT_CONFIG.copy()


def save_config(config):
    save_config_to_db(config)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except:
        pass


def _ensure_defaults(config):
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
    # 按顺序自动编号：第1个 agent_1，第2个 agent_2 ...
    for i, agent in enumerate(config.get("agents", [])):
        agent["id"] = f"agent_{i+1}"
    return config