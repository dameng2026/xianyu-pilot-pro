"""
商品详情拉取与快照保存服务（用于售整自动上架）。

职责：
1. 给已有但缺少快照的商品补拉详情，生成 xianyu_goods_edit_snapshot 记录；
2. 同步冗余字段 has_snapshot / original_quantity 到 xianyu_goods 表，避免跨库查询。

设计要点：
- 鱼小铺与普通账号共用本模块，account_type 字段区分；
- 失败不影响同步主流程，仅记录警告；
- 通过 fetch_item_detail 复用既有 MTOP 详情接口与风控检测逻辑；
- 单账号串行拉取，每条间隔 3~5 秒，避免触发风控。
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Iterable, List, Optional

from sqlalchemy import select, update, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import XianyuGoods, XianyuGoodsEditSnapshot
from .xianyu_goods_sync import fetch_item_detail, XianyuRiskControlError

logger = logging.getLogger(__name__)


# 单次拉取详情的并发上限（实际为串行 + 延迟，此值保留扩展空间）
_DETAIL_FETCH_CONCURRENCY = 1

# 单条详情拉取失败后是否继续下一条（True=继续，False=风控立即停止）
_CONTINUE_ON_FAILURE = True


async def _build_snapshot_from_detail(
    db: AsyncSession,
    account_id: int,
    tenant_id: int,
    external_goods_id: str,
    detail_data: dict,
    is_fish_shop: bool,
) -> None:
    """根据详情 API 响应构建快照并写入数据库。

    detail_data 是 fetch_item_detail 返回的字典，通常包含 itemDO/desc/quantity 等。
    """
    if not detail_data:
        return

    # 兼容详情数据的不同结构：data.itemDO / data.item / 顶层
    item_info = (
        detail_data.get("itemDO")
        or detail_data.get("item")
        or detail_data
    )
    if not isinstance(item_info, dict):
        item_info = detail_data

    title = item_info.get("title") or ""
    desc = item_info.get("desc") or item_info.get("description") or ""
    image_urls = item_info.get("imageUrls") or item_info.get("picUrls") or []
    if isinstance(image_urls, dict):
        image_urls = [image_urls.get("url", "")]
    if not isinstance(image_urls, list):
        image_urls = []

    price = item_info.get("price") or item_info.get("reservePrice") or ""
    try:
        quantity = int(item_info.get("quantity", 0) or 0)
    except (ValueError, TypeError):
        quantity = 0
    if quantity <= 0:
        sku_list = item_info.get("skuList") or item_info.get("idleItemSkuList") or []
        if isinstance(sku_list, list):
            sku_sum = 0
            for sku in sku_list:
                if isinstance(sku, dict):
                    try:
                        sku_sum += int(sku.get("quantity", 0) or 0)
                    except (ValueError, TypeError):
                        pass
            if sku_sum > 0:
                quantity = sku_sum

    snapshot_data = {
        "title": title,
        "description": desc,
        "imageUrls": image_urls,
        "price": str(price) if price != "" else "",
        "stock": quantity,
        "category": item_info.get("category") or "",
        "location": item_info.get("location") or {},
        "shippingMode": item_info.get("shippingMode") or "free",
        "supportSelfPick": bool(item_info.get("supportSelfPick", False)),
    }

    if is_fish_shop:
        sku_list = item_info.get("skuList") or item_info.get("idleItemSkuList") or []
        if isinstance(sku_list, list) and sku_list:
            snapshot_data["itemSkuList"] = sku_list
        prop_list = item_info.get("itemProperties") or item_info.get("properties") or []
        if isinstance(prop_list, list) and prop_list:
            snapshot_data["itemProperties"] = prop_list

    account_type = "fish_shop" if is_fish_shop else "normal"
    source = "detail_api"

    snapshot = XianyuGoodsEditSnapshot(
        tenant_id=tenant_id,
        account_id=account_id,
        external_goods_id=str(external_goods_id),
        snapshot_json=snapshot_data,
        source=source,
        account_type=account_type,
    )
    db.add(snapshot)
    await db.flush()

    await db.execute(
        text(
            "UPDATE xianyu_goods SET has_snapshot = 1, "
            "original_quantity = :qty "
            "WHERE external_goods_id = :gid AND account_id = :aid"
        ),
        {"qty": int(quantity), "gid": str(external_goods_id), "aid": int(account_id)},
    )


async def async_fetch_details_for_missing_snapshots(
    db_factory,
    account_id: int,
    tenant_id: int,
    goods_list: Iterable,
    is_fish_shop: bool,
    cookie_str: str,
    *,
    max_items_per_run: int = 50,
) -> dict:
    """为缺少快照的商品补拉详情并生成快照。

    参数:
        db_factory: 异步会话工厂（async_session）
        account_id: 账号 ID
        tenant_id: 租户 ID
        goods_list: XianyuGoods 实例列表或字典列表（需含 external_goods_id）
        is_fish_shop: 是否鱼小铺账号
        cookie_str: 解密后的 Cookie
        max_items_per_run: 单次运行最多处理多少条，避免长时间阻塞同步

    返回:
        {"processed": int, "succeeded": int, "failed": int, "skipped": int}
    """
    processed = 0
    succeeded = 0
    failed = 0
    skipped = 0

    items_to_fetch: List[tuple] = []
    for g in goods_list:
        ext_id = getattr(g, "external_goods_id", None) or (g.get("external_goods_id") if isinstance(g, dict) else None)
        if not ext_id:
            skipped += 1
            continue
        items_to_fetch.append((str(ext_id), getattr(g, "id", None)))

        if len(items_to_fetch) >= max_items_per_run:
            break

    if not items_to_fetch:
        return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": skipped}

    logger.info(
        "快照补拉启动: account_id=%d, is_fish_shop=%s, items_count=%d",
        account_id, is_fish_shop, len(items_to_fetch),
    )

    for ext_id, _goods_id in items_to_fetch:
        processed += 1
        delay = 3.0 + random.uniform(0, 2.0)
        await asyncio.sleep(delay)

        try:
            detail_data = await asyncio.to_thread(fetch_item_detail, cookie_str, ext_id)
            if not detail_data:
                failed += 1
                logger.warning(
                    "快照补拉: itemId=%s 返回空数据 (account_id=%d)",
                    ext_id, account_id,
                )
                continue

            async with db_factory() as db:
                existing_snapshot = await db.execute(
                    select(XianyuGoodsEditSnapshot).where(
                        and_(
                            XianyuGoodsEditSnapshot.tenant_id == tenant_id,
                            XianyuGoodsEditSnapshot.account_id == account_id,
                            XianyuGoodsEditSnapshot.external_goods_id == ext_id,
                            XianyuGoodsEditSnapshot.deleted == 0,
                        )
                    )
                )
                if existing_snapshot.scalar_one_or_none():
                    await db.execute(
                        text(
                            "UPDATE xianyu_goods SET has_snapshot = 1 "
                            "WHERE external_goods_id = :gid AND account_id = :aid"
                        ),
                        {"gid": ext_id, "aid": int(account_id)},
                    )
                    await db.commit()
                    succeeded += 1
                    skipped += 1
                    continue

                await _build_snapshot_from_detail(
                    db,
                    account_id=account_id,
                    tenant_id=tenant_id,
                    external_goods_id=ext_id,
                    detail_data=detail_data,
                    is_fish_shop=is_fish_shop,
                )
                await db.commit()

            succeeded += 1
            logger.info(
                "快照补拉成功: itemId=%s (account_id=%d, %d/%d)",
                ext_id, account_id, processed, len(items_to_fetch),
            )

        except XianyuRiskControlError as e:
            logger.warning(
                "快照补拉触发风控，停止本次拉取: account_id=%d, processed=%d, err=%s",
                account_id, processed, str(e)[:200],
            )
            failed += 1
            break

        except Exception as e:
            failed += 1
            logger.warning(
                "快照补拉失败: itemId=%s, err=%s",
                ext_id, str(e)[:200],
            )
            if not _CONTINUE_ON_FAILURE:
                break

    logger.info(
        "快照补拉完成: account_id=%d, processed=%d, succeeded=%d, failed=%d, skipped=%d",
        account_id, processed, succeeded, failed, skipped,
    )
    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }


async def trigger_snapshot_fetch_for_account(
    account_id: int,
    tenant_id: int,
    cookie_str: str,
    is_fish_shop: bool,
    *,
    db_factory=None,
    max_items_per_run: int = 50,
) -> dict:
    """触发指定账号下无快照商品的详情补拉。

    供 xianyu_goods_sync / fish_shop_sync 在同步完成后调用。
    """
    try:
        if db_factory is None:
            from ..core.database import async_session
            db_factory = async_session

        async with db_factory() as db:
            result = await db.execute(
                select(XianyuGoods).where(
                    and_(
                        XianyuGoods.tenant_id == tenant_id,
                        XianyuGoods.account_id == account_id,
                        XianyuGoods.deleted == 0,
                        XianyuGoods.status == 1,
                        XianyuGoods.has_snapshot == 0,
                    )
                ).limit(max_items_per_run)
            )
            goods_list = result.scalars().all()

        if not goods_list:
            return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}

        return await async_fetch_details_for_missing_snapshots(
            db_factory=db_factory,
            account_id=account_id,
            tenant_id=tenant_id,
            goods_list=goods_list,
            is_fish_shop=is_fish_shop,
            cookie_str=cookie_str,
            max_items_per_run=max_items_per_run,
        )
    except Exception as e:
        logger.exception("触发快照补拉失败 account_id=%s: %s", account_id, e)
        return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "error": str(e)}
