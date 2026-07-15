"""快速搜索测试：直调闲鱼 MTOP 搜索 API（不刷新 _m_h5_tk）。

根据项目记忆：使用原始 Cookie 直调，不刷新 token，避免搜索 API 兼容性问题。
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import async_session
from app.services.xianyu_goods_sync import (
    _make_api_request,
    _resolve_account_cookie,
    _normalize_mtop_search_item,
    SEARCH_MTOP_API,
)


async def test_fast_search(keyword: str = "ddr4", page: int = 1, rows_per_page: int = 30):
    async with async_session() as db:
        cookie_str, err = await _resolve_account_cookie(db, tenant_id=1, account_id=1, current_user={})
        if err:
            print(f"[FAIL] 解析 Cookie 失败: {err}")
            return
        print(f"[OK] Cookie 解析成功, len={len(cookie_str)}")

        # 根据闲鱼搜索接口.md 的 data 字段格式
        data = {
            "pageNumber": page,
            "keyword": keyword,
            "fromFilter": False,
            "rowsPerPage": rows_per_page,
            "sortValue": "",
            "sortField": "",
            "customDistance": "",
            "gps": "",
            "propValueStr": {},
            "customGps": "",
            "searchReqFromPage": "pcSearch",
            "extraFilterValue": "{}",
            "userPositionJson": "{}",
        }

        # 文档中额外的表单字段
        import time as _time
        log_id = f"{_time.time():.0f}XF6kjV"
        extra_form = {
            "spm_cnt": "a21ybx.search.0.0",
            "spm_pre": f"a21ybx.search.searchActivate.8.{log_id}",
            "log_id": log_id,
        }

        t0 = time.time()
        try:
            resp = _make_api_request(cookie_str, SEARCH_MTOP_API, data, timeout=15, extra_form=extra_form)
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[FAIL] MTOP 调用失败 (耗时 {elapsed:.2f}s): {type(e).__name__}: {e}")
            return
        elapsed = time.time() - t0
        print(f"[OK] MTOP 调用成功, 耗时 {elapsed:.2f}s")

        ret = resp.get("ret", [])
        ret_msg = ret[0] if isinstance(ret, list) and ret else str(ret)
        print(f"  ret = {ret_msg}")
        # 打印完整响应前 500 字符，便于调试
        print(f"  resp preview = {str(resp)[:500]}")

        data_body = resp.get("data", {})
        result_list = data_body.get("resultList", []) if isinstance(data_body, dict) else []
        print(f"  resultList.length = {len(result_list)}")

        items = []
        for entry in result_list:
            if not isinstance(entry, dict):
                continue
            main = (entry.get("data") or {}).get("item", {}).get("main", {})
            if not main:
                continue
            normalized = _normalize_mtop_search_item(entry)
            if normalized.get("itemId") or normalized.get("title"):
                items.append(normalized)

        print(f"  解析商品数 = {len(items)}")
        for i, it in enumerate(items[:3]):
            print(f"  [{i}] title={it.get('title','')[:40]} price={it.get('price')} itemId={it.get('itemId')} seller={it.get('seller')} area={it.get('area')}")


if __name__ == "__main__":
    asyncio.run(test_fast_search())
