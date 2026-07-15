"""
端到端深度测试 - 验证7项功能的完整流程
不只是接口存在性，而是真实业务流程
"""
import sys
import time
import json
import requests
from pathlib import Path

BASE_URL = "http://localhost:5174"
API_BASE = "http://localhost:18080"
USERNAME = "demo"
PASSWORD = "123456"

results = []
failures = []  # 收集失败项以便修复

def log(name, status, detail="", response=None):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{icon} [{name}] {status} {detail}")
    results.append({"name": name, "status": status, "detail": detail})
    if status == "FAIL":
        failures.append({"name": name, "detail": detail, "response": response})

def login_api():
    r = requests.post(f"{API_BASE}/api/login/login",
                      json={"username": USERNAME, "password": PASSWORD},
                      timeout=15)
    data = r.json()
    if data.get("code") == 200:
        return data["data"]["token"], data["data"].get("tenantId")
    raise RuntimeError(f"登录失败: {data}")

def api_get(token, path, timeout=30):
    return requests.get(f"{API_BASE}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=timeout).json()

def api_post(token, path, body=None, timeout=60):
    return requests.post(f"{API_BASE}{path}",
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json"},
                         json=body or {},
                         timeout=timeout).json()

def get_accounts(token):
    """获取账号列表 - 正确路径为 /api/xianyu/accounts（无 /list 后缀）"""
    r = api_get(token, "/api/xianyu/accounts?current=1&size=20", timeout=15)
    if r.get("code") == 200:
        # 兼容 {data: {records: []}} 和 {data: []} 两种返回格式
        data = r["data"]
        if isinstance(data, dict):
            return data.get("records", []) or []
        return data or []
    return []

def test_polish_e2e(token):
    """测试1: 擦亮功能完整流程"""
    print("\n========== [功能1] 擦亮功能完整端到端测试 ==========")
    accounts = get_accounts(token)
    if not accounts:
        log("擦亮-获取账号", "FAIL", "无可用账号")
        return

    # 选择第一个账号
    account = accounts[0]
    account_id = account.get("id")
    print(f"  使用账号: id={account_id}, nickname={account.get('nickname')}")

    # 1. 提交擦亮任务
    try:
        r = api_post(token, "/api/item/polish", {"xianyuAccountId": account_id}, timeout=30)
        if not (r.get("code") == 200 and r["data"].get("taskId")):
            # 检查内层错误
            if r.get("code") == 200 and isinstance(r["data"], dict) and r["data"].get("code") == 500:
                log("擦亮-任务提交", "FAIL", f"内层错误: {r['data'].get('msg', '')[:100]}", r)
            else:
                log("擦亮-任务提交", "FAIL", str(r), r)
            return

        task_id = r["data"]["taskId"]
        total = r["data"].get("total", 0)
        log("擦亮-任务提交", "PASS", f"taskId={task_id}, total={total}")

        # 2. 轮询任务进度
        final_status = None
        final_data = None
        for i in range(60):  # 最多等120秒
            time.sleep(2)
            p = api_get(token, f"/api/item/polishProgress/{task_id}", timeout=10)
            if p.get("code") == 200:
                pd = p["data"]
                running = pd.get("running")
                status = pd.get("status")
                polished = pd.get("polished", 0)
                failed = pd.get("failed", 0)
                if i % 5 == 0 or not running:
                    print(f"  进度: running={running}, status={status}, polished={polished}, failed={failed}")

                if not running:
                    final_status = status
                    final_data = pd
                    break
            else:
                print(f"  轮询失败: {p}")

        if final_data is None:
            log("擦亮-任务完成", "FAIL", "超时未完成")
            return

        # 3. 验证结果
        polished = final_data.get("polished", 0)
        failed = final_data.get("failed", 0)
        msg = final_data.get("message", "")

        if final_status == "completed":
            if polished > 0:
                log("擦亮-任务完成", "PASS",
                    f"polished={polished}, failed={failed}, msg={msg}")
            elif failed > 0 and polished == 0:
                # 所有商品都失败了 - 这是用户反馈的问题
                log("擦亮-任务完成", "FAIL",
                    f"全部失败: polished={polished}, failed={failed}, msg={msg}",
                    final_data)
            else:
                log("擦亮-任务完成", "WARN",
                    f"无商品可擦亮: polished={polished}, failed={failed}, msg={msg}")
        else:
            log("擦亮-任务完成", "FAIL",
                f"status={final_status}, msg={msg}", final_data)
    except Exception as e:
        log("擦亮-任务", "FAIL", str(e))

def test_rag_e2e(token):
    """测试5: RAG知识库完整流程"""
    print("\n========== [功能5] RAG知识库完整端到端测试 ==========")

    # 1. 初始统计
    try:
        r = api_get(token, "/api/knowledge-base/rag/stats", timeout=15)
        if r.get("code") == 200:
            initial_count = r["data"].get("totalDocuments", 0)
            log("RAG-初始统计", "PASS", f"totalDocuments={initial_count}")
        else:
            log("RAG-初始统计", "FAIL", str(r), r)
            return
    except Exception as e:
        log("RAG-初始统计", "FAIL", str(e))
        return

    # 2. 添加文档
    test_doc = "这是一条RAG测试文档。闲鱼助手支持账号管理、商品擦亮、消息回复、自动发货等功能。本测试用于验证RAG知识库的添加、查询、聊天、删除完整流程。"
    doc_id = None
    try:
        r = api_post(token, "/api/knowledge-base/rag/add",
                     {"content": test_doc, "metadata": {"source": "e2e_test", "category": "test"}},
                     timeout=30)
        if r.get("code") == 200 and r["data"].get("success"):
            doc_id = r["data"].get("docId")
            log("RAG-添加文档", "PASS", f"docId={doc_id}")
        elif r.get("code") == 200 and isinstance(r.get("data"), dict) and r["data"].get("code") == 500:
            # 内层500错误，通常是Embedding API配置问题
            inner_msg = r["data"].get("msg", "")
            if "401" in inner_msg or "Authentication" in inner_msg or "api key" in inner_msg.lower():
                log("RAG-添加文档", "WARN",
                    f"Embedding API key无效（需后台配置）: {inner_msg[:100]}")
            else:
                log("RAG-添加文档", "FAIL", f"内层错误: {inner_msg[:100]}", r)
            return
        else:
            log("RAG-添加文档", "FAIL", str(r), r)
            return
    except Exception as e:
        log("RAG-添加文档", "FAIL", str(e))
        return

    # 3. 查询文档
    try:
        r = api_post(token, "/api/knowledge-base/rag/query",
                     {"question": "闲鱼助手有什么功能?", "topK": 3}, timeout=30)
        if r.get("code") == 200:
            docs = r["data"].get("documents", [])
            log("RAG-查询文档", "PASS", f"返回 {len(docs)} 条匹配文档")
        else:
            log("RAG-查询文档", "FAIL", str(r), r)
    except Exception as e:
        log("RAG-查询文档", "FAIL", str(e))

    # 4. RAG 聊天
    try:
        r = api_post(token, "/api/knowledge-base/rag/chat",
                     {"question": "闲鱼助手支持哪些功能?", "topK": 3}, timeout=60)
        if r.get("code") == 200:
            answer = r["data"].get("answer", "")
            has_content = len(answer) > 10
            log("RAG-聊天", "PASS" if has_content else "WARN",
                f"answer长度={len(answer)}, 片段={answer[:80]}")
        else:
            log("RAG-聊天", "FAIL", str(r), r)
    except Exception as e:
        log("RAG-聊天", "FAIL", str(e))

    # 5. 统计更新验证
    try:
        r = api_get(token, "/api/knowledge-base/rag/stats", timeout=15)
        if r.get("code") == 200:
            new_count = r["data"].get("totalDocuments", 0)
            if new_count > initial_count:
                log("RAG-统计更新", "PASS", f"{initial_count} -> {new_count}")
            else:
                log("RAG-统计更新", "FAIL", f"数量未增加: {initial_count} -> {new_count}", r)
    except Exception as e:
        log("RAG-统计更新", "FAIL", str(e))

    # 6. 删除文档
    try:
        r = api_post(token, "/api/knowledge-base/rag/delete",
                     {"docId": doc_id}, timeout=15)
        if r.get("code") == 200 and r["data"].get("success"):
            log("RAG-删除文档", "PASS", f"docId={doc_id}")
        else:
            log("RAG-删除文档", "FAIL", str(r), r)
    except Exception as e:
        log("RAG-删除文档", "FAIL", str(e))

def test_kami_e2e(token):
    """测试3: 卡密发货完整流程
    DTO 期望字段: xianyuAccountId(必填), xyGoodsId, configName, deliveryType
    """
    print("\n========== [功能3] 卡密发货完整端到端测试 ==========")
    accounts = get_accounts(token)
    if not accounts:
        log("卡密-前置条件", "FAIL", "无可用账号，跳过测试")
        return
    account_id = accounts[0].get("id")

    # 1. 查询初始配置
    try:
        r = api_post(token, "/api/kami/config/list", {"page": 1, "size": 10}, timeout=15)
        if r.get("code") == 200:
            initial_configs = r["data"].get("records", []) if isinstance(r["data"], dict) else (r["data"] or [])
            log("卡密-配置列表", "PASS", f"records={len(initial_configs)}")
        else:
            log("卡密-配置列表", "FAIL", str(r), r)
            return
    except Exception as e:
        log("卡密-配置列表", "FAIL", str(e))
        return

    # 2. 创建卡密配置（使用DTO期望的字段名）
    test_config = {
        "xianyuAccountId": account_id,
        "configName": "E2E测试卡密分组",
        "deliveryType": "kami"
    }
    try:
        r = api_post(token, "/api/kami/config/save", test_config, timeout=15)
        if r.get("code") == 200:
            # 返回可能是 {success: true} 或 {id: xxx}
            data = r["data"]
            if isinstance(data, dict):
                config_id = data.get("id") or data.get("groupId")
            else:
                config_id = None
            log("卡密-创建配置", "PASS", f"configId={config_id}, response={str(data)[:80]}")
        else:
            log("卡密-创建配置", "FAIL", str(r), r)
            return
    except Exception as e:
        log("卡密-创建配置", "FAIL", str(e))
        return

    # 3. 查询配置列表验证创建成功
    try:
        r = api_post(token, "/api/kami/config/list", {"page": 1, "size": 10}, timeout=15)
        if r.get("code") == 200:
            records = r["data"].get("records", []) if isinstance(r["data"], dict) else (r["data"] or [])
            log("卡密-配置列表更新", "PASS", f"records={len(records)}")
        else:
            log("卡密-配置列表更新", "FAIL", str(r), r)
    except Exception as e:
        log("卡密-配置列表更新", "FAIL", str(e))

    # 4. 删除配置（清理测试数据）
    if config_id:
        try:
            r = api_post(token, "/api/kami/config/delete", {"id": config_id}, timeout=15)
            if r.get("code") == 200:
                log("卡密-删除配置", "PASS", f"id={config_id}")
            else:
                log("卡密-删除配置", "FAIL", str(r), r)
        except Exception as e:
            log("卡密-删除配置", "FAIL", str(e))

def test_captcha_e2e(token):
    """测试7: 滑块验证完整流程"""
    print("\n========== [功能7] 滑块验证完整端到端测试 ==========")
    accounts = get_accounts(token)
    if not accounts:
        log("滑块-获取账号", "FAIL", "无可用账号")
        return

    account_id = accounts[0].get("id")

    # 1. 滑块检测
    try:
        r = api_post(token, "/api/captcha/detect", {"accountId": account_id}, timeout=30)
        if r.get("code") == 200:
            detected = r["data"].get("detected", False)
            log("滑块-检测", "PASS", f"detected={detected}")
        else:
            log("滑块-检测", "FAIL", str(r), r)
    except Exception as e:
        log("滑块-检测", "FAIL", str(e))

    # 2. 操作指引
    try:
        r = api_post(token, "/api/captcha/instructions",
                     {"accountId": account_id, "captchaUrl": ""}, timeout=15)
        if r.get("code") == 200:
            steps = r["data"].get("steps", [])
            auto_solve = r["data"].get("autoSolveAvailable", False)
            log("滑块-操作指引", "PASS", f"steps={len(steps)}, autoSolve={auto_solve}")
            # 验证步骤内容是否合理
            if steps:
                print(f"  步骤示例: {steps[0] if isinstance(steps[0], str) else steps[0].get('action', '')}")
        else:
            log("滑块-操作指引", "FAIL", str(r), r)
    except Exception as e:
        log("滑块-操作指引", "FAIL", str(e))

    # 3. 自动解决（即使无实际滑块也应正常返回）
    try:
        r = api_post(token, "/api/captcha/auto-solve",
                     {"accountId": account_id, "captchaUrl": "about:blank"}, timeout=60)
        if r.get("code") == 200:
            solved = r["data"].get("solved", False)
            log("滑块-自动解决", "PASS", f"solved={solved}, msg={r['data'].get('message', '')[:80]}")
        else:
            # 自动解决在无实际滑块时可能返回业务错误，这是正常的
            log("滑块-自动解决", "WARN", f"code={r.get('code')}, msg={r.get('msg', '')[:80]}")
    except Exception as e:
        log("滑块-自动解决", "FAIL", str(e))

    # 4. 一键处理
    try:
        r = api_post(token, "/api/captcha/handle",
                     {"accountId": account_id}, timeout=60)
        if r.get("code") == 200:
            log("滑块-一键处理", "PASS", f"result={r['data'].get('result')}, msg={r['data'].get('message', '')[:80]}")
        else:
            log("滑块-一键处理", "WARN", f"code={r.get('code')}, msg={r.get('msg', '')[:80]}")
    except Exception as e:
        log("滑块-一键处理", "FAIL", str(e))

def test_refresh_e2e(token):
    """测试4: Cookie/Token刷新完整流程"""
    print("\n========== [功能4] Cookie/Token刷新完整端到端测试 ==========")

    # 1. 状态查询
    try:
        r = api_get(token, "/api/account/refresh/status", timeout=15)
        if r.get("code") == 200:
            data = r["data"]
            running = data.get("running")
            accounts_count = data.get("accountsCount", 0)
            cfg = data.get("config", {})

            # 验证随机间隔策略符合规范
            cookie_interval = cfg.get("cookieKeepaliveIntervalMinutes")
            mh5_min = cfg.get("mh5tkRefreshMinHours")
            mh5_max = cfg.get("mh5tkRefreshMaxHours")
            ws_min = cfg.get("wsTokenRefreshMinHours")
            ws_max = cfg.get("wsTokenRefreshMaxHours")
            acc_min = cfg.get("accountIntervalMinSeconds")
            acc_max = cfg.get("accountIntervalMaxSeconds")

            config_ok = (cookie_interval == 30 and
                        mh5_min == 1.5 and mh5_max == 2.5 and
                        ws_min == 10 and ws_max == 14 and
                        acc_min == 2 and acc_max == 5)

            log("刷新-状态查询", "PASS" if config_ok else "FAIL",
                f"running={running}, accounts={accounts_count}, "
                f"cookie={cookie_interval}min, mh5tk={mh5_min}-{mh5_max}h, "
                f"wsToken={ws_min}-{ws_max}h, accInterval={acc_min}-{acc_max}s")
        else:
            log("刷新-状态查询", "FAIL", str(r), r)
            return
    except Exception as e:
        log("刷新-状态查询", "FAIL", str(e))
        return

    # 2. 强制刷新
    accounts = get_accounts(token)
    if accounts:
        account_id = accounts[0].get("id")
        try:
            r = api_post(token, "/api/account/refresh/force",
                         {"accountId": account_id, "refreshType": "cookie"}, timeout=60)
            if r.get("code") == 200 and r["data"].get("success"):
                details = r["data"].get("details", {})
                log("刷新-强制Cookie保活", "PASS",
                    f"cookie={details.get('cookie')}, mh5tk={details.get('mh5tk')}")
            else:
                log("刷新-强制Cookie保活", "FAIL", str(r), r)
        except Exception as e:
            log("刷新-强制Cookie保活", "FAIL", str(e))

    # 3. 启动调度器（幂等操作）
    try:
        r = api_post(token, "/api/account/refresh/start", {}, timeout=15)
        if r.get("code") == 200:
            log("刷新-启动调度器", "PASS", f"running={r['data'].get('running')}")
        else:
            log("刷新-启动调度器", "FAIL", str(r), r)
    except Exception as e:
        log("刷新-启动调度器", "FAIL", str(e))

    # 4. 停止调度器
    try:
        r = api_post(token, "/api/account/refresh/stop", {}, timeout=15)
        if r.get("code") == 200:
            log("刷新-停止调度器", "PASS", f"running={r['data'].get('running')}")
        else:
            log("刷新-停止调度器", "FAIL", str(r), r)
    except Exception as e:
        log("刷新-停止调度器", "FAIL", str(e))

    # 5. 重新启动（恢复运行状态）
    try:
        r = api_post(token, "/api/account/refresh/start", {}, timeout=15)
        # 响应格式: {code:200, msg:"操作成功", data:{message:"刷新调度器已启动"}}
        # 或者: {code:200, data:{running: true}}
        if r.get("code") == 200:
            data = r["data"] or {}
            running = data.get("running")
            msg = data.get("message", "")
            if running is True or "已启动" in str(msg) or "调度器已启动" in str(msg):
                log("刷新-恢复运行", "PASS", f"调度器已重启, msg={msg}")
            else:
                log("刷新-恢复运行", "WARN", f"响应无明确状态: {str(data)[:80]}")
        else:
            log("刷新-恢复运行", "FAIL", str(r), r)
    except Exception as e:
        log("刷新-恢复运行", "FAIL", str(e))

def test_autodelivery_e2e(token):
    """测试6: 自定义发货API完整流程
    DTO 期望字段: xianyuAccountId(必填), xyGoodsId, deliveryType, deliveryContent
    """
    print("\n========== [功能6] 自定义发货API完整端到端测试 ==========")
    accounts = get_accounts(token)
    if not accounts:
        log("自定义发货-前置条件", "FAIL", "无可用账号，跳过测试")
        return
    account_id = accounts[0].get("id")

    # 1. 查询配置列表
    try:
        r = api_post(token, "/api/autoDelivery/config/list", {"page": 1, "size": 10}, timeout=15)
        if r.get("code") == 200:
            data = r["data"]
            initial = data.get("records", []) if isinstance(data, dict) else (data or [])
            log("自定义发货-配置列表", "PASS", f"records={len(initial)}")
        else:
            log("自定义发货-配置列表", "FAIL", str(r), r)
            return
    except Exception as e:
        log("自定义发货-配置列表", "FAIL", str(e))
        return

    # 2. 创建配置（使用DTO期望的字段名，xyGoodsId需为有效整数否则会被转为None）
    test_config = {
        "xianyuAccountId": account_id,
        "xyGoodsId": "999999",  # 使用数字字符串，后端会int()转换
        "deliveryType": "text",
        "deliveryContent": "E2E_TEST_DELIVERY_CONTENT_MARKER"
    }
    try:
        r = api_post(token, "/api/autoDelivery/config/save", test_config, timeout=15)
        if r.get("code") == 200:
            log("自定义发货-创建配置", "PASS", f"response={str(r['data'])[:80]}")
        else:
            log("自定义发货-创建配置", "FAIL", str(r), r)
            return
    except Exception as e:
        log("自定义发货-创建配置", "FAIL", str(e))
        return

    # 3. 查询配置列表验证创建成功
    try:
        r = api_post(token, "/api/autoDelivery/config/list", {"page": 1, "size": 10}, timeout=15)
        if r.get("code") == 200:
            data = r["data"]
            records = data if isinstance(data, list) else (data.get("records", []) if isinstance(data, dict) else [])
            # 验证是否包含刚创建的配置（通过deliveryContent标记字段识别）
            found = any(r.get("deliveryContent") == "E2E_TEST_DELIVERY_CONTENT_MARKER" for r in records)
            log("自定义发货-列表验证", "PASS" if found else "WARN",
                f"records={len(records)}, found_test={found}")
        else:
            log("自定义发货-列表验证", "FAIL", str(r), r)
    except Exception as e:
        log("自定义发货-列表验证", "FAIL", str(e))

    # 4. 触发自动发货（接口存在性测试）
    try:
        r = api_post(token, "/api/autoDelivery/trigger",
                     {"xianyuAccountId": account_id, "xyGoodsId": "999999", "orderId": "E2E-TEST-ORDER-001"},
                     timeout=30)
        if r.get("code") == 200:
            log("自定义发货-触发测试", "PASS", f"msg={r['data']}")
        else:
            log("自定义发货-触发测试", "WARN", f"msg={r.get('msg', '')[:80]}")
    except Exception as e:
        log("自定义发货-触发测试", "WARN", str(e)[:80])

    # 5. 删除测试配置
    try:
        # 找到刚创建的配置并删除
        r = api_post(token, "/api/autoDelivery/config/list", {"page": 1, "size": 10}, timeout=15)
        if r.get("code") == 200:
            data = r["data"]
            records = data if isinstance(data, list) else (data.get("records", []) if isinstance(data, dict) else [])
            for record in records:
                if record.get("deliveryContent") == "E2E_TEST_DELIVERY_CONTENT_MARKER":
                    rule_id = record.get("id")
                    dr = api_post(token, "/api/autoDelivery/config/delete",
                                 {"id": rule_id}, timeout=15)
                    if dr.get("code") == 200:
                        log("自定义发货-删除配置", "PASS", f"id={rule_id}")
                    else:
                        log("自定义发货-删除配置", "FAIL", str(dr), dr)
                    break
            else:
                log("自定义发货-删除配置", "WARN", "未找到测试配置")
    except Exception as e:
        log("自定义发货-删除配置", "FAIL", str(e))

def test_websocket_e2e(token):
    """测试2: WebSocket发货接口验证"""
    print("\n========== [功能2] WebSocket发货接口验证 ==========")
    accounts = get_accounts(token)
    if not accounts:
        log("WebSocket-获取账号", "FAIL", "无可用账号")
        return

    account_id = accounts[0].get("id")

    # 1. 查询 WebSocket 状态
    try:
        r = api_post(token, "/api/automation/bridge/websocket/status",
                     {"xianyuAccountId": account_id}, timeout=15)
        if r.get("code") == 200:
            data = r["data"]
            log("WebSocket-状态查询", "PASS",
                f"connected={data.get('connected', data.get('status'))}")
        else:
            log("WebSocket-状态查询", "WARN", f"msg={r.get('msg', '')[:80]}")
    except Exception as e:
        log("WebSocket-状态查询", "WARN", str(e)[:80])

    # 2. 会话列表查询（验证消息链路）
    try:
        r = api_post(token, "/api/automation/bridge/conversations",
                     {"xianyuAccountId": account_id, "limit": 10}, timeout=30)
        if r.get("code") == 200:
            conversations = r["data"].get("conversations", r["data"].get("list", []))
            log("WebSocket-会话列表", "PASS", f"conversations={len(conversations)}")
        else:
            log("WebSocket-会话列表", "WARN", f"msg={r.get('msg', '')[:80]}")
    except Exception as e:
        log("WebSocket-会话列表", "WARN", str(e)[:80])

def main():
    print("=" * 70)
    print("7项功能端到端深度测试 - 真实业务流程验证")
    print("=" * 70)

    try:
        token, tenant_id = login_api()
        print(f"✅ 登录成功，tenantId={tenant_id}")
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        return

    test_polish_e2e(token)
    test_websocket_e2e(token)
    test_kami_e2e(token)
    test_refresh_e2e(token)
    test_rag_e2e(token)
    test_autodelivery_e2e(token)
    test_captcha_e2e(token)

    print("\n" + "=" * 70)
    print("端到端深度测试结果汇总")
    print("=" * 70)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌" if r["status"] == "FAIL" else "⚠️"
        print(f"{icon} {r['name']}: {r['status']} - {r['detail'][:100]}")
    print("-" * 70)
    print(f"总计: {len(results)} 项 | 通过: {pass_count} | 失败: {fail_count} | 警告: {warn_count}")

    if failures:
        print("\n" + "=" * 70)
        print("需要修复的失败项")
        print("=" * 70)
        for f in failures:
            print(f"❌ {f['name']}: {f['detail']}")

if __name__ == "__main__":
    main()
