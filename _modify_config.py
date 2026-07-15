# -*- coding: utf-8 -*-
"""修改 app/core/config.py - 添加安全配置项"""
import io

TARGET = r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\core\config.py"

with io.open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

OLD = """    # 自动分类置信度阈值
    # 注意：闲鱼官方 categoryPredictResult 已优先采用并跳过阈值检查，
    # 这里的阈值仅用于 score 排序回退场景。闲鱼实际返回的 score 普遍较低
    # （典型值 0.03~0.05），故降低阈值避免误判为低置信度。
    auto_category_min_score: float = 0.03
    auto_category_min_margin: float = 0.01"""

NEW = """    # 自动分类置信度阈值
    # 注意：闲鱼官方 categoryPredictResult 已优先采用并跳过阈值检查，
    # 这里的阈值仅用于 score 排序回退场景。闲鱼实际返回的 score 普遍较低
    # （典型值 0.03~0.05），故降低阈值避免误判为低置信度。
    auto_category_min_score: float = 0.03
    auto_category_min_margin: float = 0.01

    # 安全配置
    login_max_attempts: int = 5          # 登录失败最大尝试次数
    login_lock_minutes: int = 15         # 锁定时长（分钟）
    audit_log_retention_days: int = 90   # 审计日志保留天数
    docs_enabled: bool = True            # 是否开放 /docs /redoc"""

if OLD not in content:
    raise SystemExit("OLD block not found in config.py")

content = content.replace(OLD, NEW, 1)

with io.open(TARGET, "w", encoding="utf-8") as f:
    f.write(content)

print("config.py updated OK")
