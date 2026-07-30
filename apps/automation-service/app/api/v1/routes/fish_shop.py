"""
鱼小铺多规格商品发布/编辑/详情路由。

仅用于鱼小铺账号 + 多规格商品。普通账号或未开启多规格的鱼小铺账号继续走 /api/item/publish。

路由：
- POST /api/fish-shop/publish  鱼小铺多规格发布
- POST /api/fish-shop/edit     鱼小铺多规格编辑
- POST /api/fish-shop/detail   获取完整商品详情（用于编辑回显）

后端权限校验：
- 调用前判断 fish_shop_user=1
- 编辑/详情场景校验商品归属于当前账号
- 不接受前端传入任意 Cookie
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.cookie_crypto import decrypt_cookie_if_needed
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....models.entities import (
    XianyuAccount,
    XianyuAccountAuth,
    XianyuGoods,
    XianyuGoodsEditSnapshot,
    XianyuGoodsProperty,
    XianyuGoodsPropertyValue,
    XianyuGoodsSku,
)
from ....services.fish_shop_publish import (
    FISH_SHOP_DETAIL_API,
    FISH_SHOP_DETAIL_VERSION,
    FISH_SHOP_EDIT_API,
    FISH_SHOP_EDIT_VERSION,
    FISH_SHOP_PUBLISH_API,
    FISH_SHOP_PUBLISH_VERSION,
    build_internal_item_object,
    call_fish_shop_api,
    cartesian_sku_combinations,
    double_layer_serialize,
    extract_response_item_id,
    extract_response_skus,
    match_response_skus,
    validate_multi_spec_payload,
    fetch_fish_shop_edit_detail,
    invalidate_edit_detail_cache,
)
from ....services.xianyu_goods_sync import (
    XianyuItemPublisher,
    extract_token_from_cookie,
)
from .internal import verify_internal_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fish-shop")


# ============================================================
# 共用辅助
# ============================================================

async def _get_account_auth_and_check_fish_shop(
    db: AsyncSession, account_id: int, tenant_id: int
) -> tuple[Optional[XianyuAccountAuth], bool]:
    """
    获取账号 auth 并校验是否为鱼小铺账号。
    返回 (auth, is_fish_shop)。
    auth 为 None 表示未登录或 Cookie 失效。
    """
    # 1) 查询账号
    result = await db.execute(
        select(XianyuAccount).where(
            and_(
                XianyuAccount.id == account_id,
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.deleted == 0,
            )
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        return None, False
    is_fish_shop = bool(account.fish_shop_user)
    if not is_fish_shop:
        return None, False

    # 2) 查询 auth
    result = await db.execute(
        select(XianyuAccountAuth).where(
            and_(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
            )
        )
    )
    auth = result.scalar_one_or_none()
    if not auth or not auth.encrypted_cookie:
        return None, True

    return auth, True


async def _verify_goods_belongs_to_account(
    db: AsyncSession, tenant_id: int, account_id: int, external_goods_id: str
) -> Optional[XianyuGoods]:
    """
    校验商品归属于当前账号。
    返回 XianyuGoods 实体，None 表示不存在或不归属。
    """
    result = await db.execute(
        select(XianyuGoods).where(
            and_(
                XianyuGoods.tenant_id == tenant_id,
                XianyuGoods.account_id == account_id,
                XianyuGoods.external_goods_id == str(external_goods_id),
                XianyuGoods.deleted == 0,
            )
        )
    )
    return result.scalar_one_or_none()


async def _persist_skus_and_properties(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    external_goods_id: str,
    property_groups: list,
    sku_list: list,
) -> None:
    """
    将 SKU 与规格数据写入本地表。
    幂等：先软删除旧的，再插入新的（同 external_goods_id）。
    """
    # 1) 软删除旧数据
    await db.execute(
        XianyuGoodsProperty.__table__.update()
        .where(
            and_(
                XianyuGoodsProperty.tenant_id == tenant_id,
                XianyuGoodsProperty.external_goods_id == external_goods_id,
                XianyuGoodsProperty.deleted == 0,
            )
        )
        .values(deleted=1)
    )
    await db.execute(
        XianyuGoodsSku.__table__.update()
        .where(
            and_(
                XianyuGoodsSku.tenant_id == tenant_id,
                XianyuGoodsSku.external_goods_id == external_goods_id,
                XianyuGoodsSku.deleted == 0,
            )
        )
        .values(deleted=1)
    )
    await db.flush()

    # 2) 插入规格类型
    property_id_map: dict = {}  # (property_name) → property_id
    for idx, g in enumerate(property_groups or []):
        name = (g.get("propertyName") or "").strip()
        if not name:
            continue
        prop = XianyuGoodsProperty(
            tenant_id=tenant_id,
            account_id=account_id,
            external_goods_id=external_goods_id,
            property_name=name,
            support_image=1 if g.get("supportImage") else 0,
            sort_order=idx,
        )
        db.add(prop)
        await db.flush()
        property_id_map[name] = prop.id

        # 插入规格值
        for v_idx, v in enumerate(g.get("propertyValues", []) or []):
            if not isinstance(v, dict):
                continue
            val = (v.get("propertyValue") or "").strip()
            if not val:
                continue
            db.add(XianyuGoodsPropertyValue(
                tenant_id=tenant_id,
                property_id=prop.id,
                external_goods_id=external_goods_id,
                property_value=val,
                property_value_img=v.get("propertyValueImg") or None,
                sort_order=v_idx,
            ))

    # 3) 插入 SKU
    for sku in sku_list:
        prop_list = sku.get("propertyList") or []
        # 构建 property_key
        from ....services.fish_shop_publish import build_property_key
        property_key = build_property_key(prop_list)

        # 提取价格库存
        try:
            price_cent = int(sku.get("priceInCent", 0))
        except (ValueError, TypeError):
            price_cent = 0
        try:
            qty = int(sku.get("quantity", 0))
        except (ValueError, TypeError):
            qty = 0

        db.add(XianyuGoodsSku(
            tenant_id=tenant_id,
            account_id=account_id,
            external_goods_id=external_goods_id,
            sku_id=str(sku.get("skuId") or "") or None,
            inventory_id=str(sku.get("inventoryId") or "") or None,
            property_list_json=prop_list,
            property_key=property_key,
            price_in_cent=price_cent,
            quantity=qty,
        ))

    await db.flush()


async def _save_edit_snapshot(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    external_goods_id: str,
    snapshot: dict,
    source: str,
) -> None:
    """保存编辑快照（用于编辑回显兜底）。"""
    db.add(XianyuGoodsEditSnapshot(
        tenant_id=tenant_id,
        account_id=account_id,
        external_goods_id=external_goods_id,
        snapshot_json=snapshot,
        source=source,
    ))
    await db.flush()


# ============================================================
# 路由：发布
# ============================================================

@router.post("/publish")
async def publish_fish_shop_item(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    鱼小铺多规格商品发布。

    请求体：
    {
        xianyuAccountId: int,
        title: str,
        description: str,
        imageUrls: list[str],
        itemProperties: [{propertyName, supportImage, propertyValues: [{propertyValue, propertyValueImg}]}],
        itemSkuList: [{price, quantity, propertyList: [{propertyText, valueText}]}],
        shippingMode: "free"|"fixed"|"none",
        supportSelfPick: bool,
        postFee: str|number,  # shippingMode=fixed 时必填
        location: {prov, city, area, divisionId, gps, poiId, poiName},
        category: {catId, catName, channelCatId, tbCatId}  # 可选，缺失则走类目推荐
    }
    """
    try:
        account_id = req.get("xianyuAccountId") or req.get("xianyu_account_id")
        if not account_id:
            return ResultObject.failed("缺少参数 xianyuAccountId")
        account_id = int(account_id)

        tenant_raw = req.get("tenantId") or req.get("tenant_id") or req.get("_tenantId")
        if not tenant_raw:
            return ResultObject.failed("缺少租户上下文")
        tenant_id = int(tenant_raw)

        # 1) 后端权限校验：必须是鱼小铺账号
        auth, is_fish_shop = await _get_account_auth_and_check_fish_shop(db, account_id, tenant_id)
        if not is_fish_shop:
            return ResultObject.failed("当前闲鱼账号不是鱼小铺，无法发布多规格商品", code=403)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效，请重新登录")

        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)
        token = extract_token_from_cookie(cookie_str)
        if not token:
            return ResultObject.failed("Cookie 中缺少 _m_h5_tk，请重新登录")

        # 2) 参数校验
        title = (req.get("title") or "").strip()
        if not title:
            return ResultObject.failed("宝贝标题不能为空")
        if len(title) > 30:
            return ResultObject.failed("宝贝标题不能超过30个字")

        description = (req.get("description") or "").strip()
        if not description:
            return ResultObject.failed("宝贝描述不能为空")

        image_urls = req.get("imageUrls", []) or []
        if not image_urls:
            return ResultObject.failed("请至少上传一张商品图片")

        property_groups = req.get("itemProperties", []) or []
        sku_list = req.get("itemSkuList", []) or []
        if not property_groups or not sku_list:
            return ResultObject.failed("多规格商品必须包含规格类型和 SKU")

        # 3) 多规格校验
        validation_error = validate_multi_spec_payload(req)
        if validation_error:
            return ResultObject.failed(validation_error)

        # 4) 类目推荐（复用现有能力）
        publisher = XianyuItemPublisher(cookie_str, tenant_id)
        recommend_result = await _sync_category_recommend(publisher, title, description, image_urls)
        if recommend_result.get("recommended"):
            category_info = recommend_result
        else:
            user_cat = req.get("category", {}) or {}
            category_info = {
                "recommended": False,
                "catId": user_cat.get("catId") or publisher.DEFAULT_CAT_ID,
                "catName": user_cat.get("catName") or publisher.DEFAULT_CAT_NAME,
                "channelCatId": user_cat.get("channelCatId") or publisher.DEFAULT_CHANNEL_CAT_ID,
                "tbCatId": user_cat.get("tbCatId") or publisher.DEFAULT_TB_CAT_ID,
                "cardList": [],
            }

        # 5) 图片上传到闲鱼 CDN（复用现有能力）
        xianyu_image_urls = publisher.upload_images_to_xianyu(image_urls)
        if not xianyu_image_urls:
            return ResultObject.failed("图片上传到闲鱼失败，请重试")

        # 6) 构造内部商品对象（发布场景，不带 itemId）
        internal_obj = build_internal_item_object(
            req, xianyu_image_urls, category_info, is_edit=False
        )

        # 7) 调用鱼小铺 publish API（双层序列化在 call_fish_shop_api 内完成）
        result = call_fish_shop_api(
            cookie_str, FISH_SHOP_PUBLISH_API, FISH_SHOP_PUBLISH_VERSION,
            internal_obj, is_edit=False,
        )

        # 8) 提取响应 itemId 与 SKU
        new_item_id = extract_response_item_id(result)
        if not new_item_id:
            return ResultObject.failed("发布成功但未返回 itemId，请稍后到商品列表同步")

        response_skus = extract_response_skus(result)
        matched_skus = match_response_skus(response_skus, internal_obj["itemSkuList"])

        # 9) 持久化 SKU 与规格数据
        await _persist_skus_and_properties(
            db, tenant_id, account_id, new_item_id,
            internal_obj["itemProperties"], matched_skus,
        )

        # 10) 保存编辑快照
        await _save_edit_snapshot(
            db, tenant_id, account_id, new_item_id,
            {"internalItem": internal_obj, "responseSkus": matched_skus},
            source="publish",
        )

        await db.commit()

        return ResultObject.success({
            "itemId": new_item_id,
            "skuList": matched_skus,
            "totalQuantity": internal_obj["quantity"],
            "minPriceInCent": internal_obj["itemPriceDTO"]["priceInCent"],
        })
    except Exception as exc:
        logger.warning("fish_shop_publish_failed account_id=%s err=%s", account_id, str(exc)[:200])
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="fish_shop_publish",
            user_message="鱼小铺多规格发布失败，请稍后重试",
        )


# ============================================================
# 路由：编辑
# ============================================================

@router.post("/edit")
async def edit_fish_shop_item(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    鱼小铺多规格商品编辑。

    请求体：
    {
        xianyuAccountId: int,
        itemId: str,  # 必填，目标闲鱼商品 itemId
        title, description, imageUrls, itemProperties, itemSkuList,
        shippingMode, supportSelfPick, postFee, location, category
    }
    """
    try:
        account_id = int(req.get("xianyuAccountId") or req.get("xianyu_account_id") or 0)
        if not account_id:
            return ResultObject.failed("缺少参数 xianyuAccountId")
        tenant_id = int(req.get("tenantId") or req.get("tenant_id") or req.get("_tenantId") or 0)
        if not tenant_id:
            return ResultObject.failed("缺少租户上下文")

        item_id = (req.get("itemId") or "").strip()
        if not item_id:
            return ResultObject.failed("编辑请求必须携带 itemId")

        # 1) 后端权限校验：必须是鱼小铺账号
        auth, is_fish_shop = await _get_account_auth_and_check_fish_shop(db, account_id, tenant_id)
        if not is_fish_shop:
            return ResultObject.failed("当前闲鱼账号不是鱼小铺，无法编辑多规格商品", code=403)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效，请重新登录")

        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)
        token = extract_token_from_cookie(cookie_str)
        if not token:
            return ResultObject.failed("Cookie 中缺少 _m_h5_tk，请重新登录")

        # 2) 校验商品归属
        goods = await _verify_goods_belongs_to_account(db, tenant_id, account_id, item_id)
        if not goods:
            return ResultObject.failed("商品不存在或不归属当前账号", code=403)

        # 3) 参数校验
        title = (req.get("title") or "").strip()
        if not title:
            return ResultObject.failed("宝贝标题不能为空")

        description = (req.get("description") or "").strip()
        if not description:
            return ResultObject.failed("宝贝描述不能为空")

        image_urls = req.get("imageUrls", []) or []
        if not image_urls:
            return ResultObject.failed("请至少上传一张商品图片")

        property_groups = req.get("itemProperties", []) or []
        sku_list = req.get("itemSkuList", []) or []
        if not property_groups or not sku_list:
            return ResultObject.failed("多规格商品必须包含规格类型和 SKU")

        validation_error = validate_multi_spec_payload(req)
        if validation_error:
            return ResultObject.failed(validation_error)

        # 4) 类目推荐
        publisher = XianyuItemPublisher(cookie_str, tenant_id)
        recommend_result = await _sync_category_recommend(publisher, title, description, image_urls)
        if recommend_result.get("recommended"):
            category_info = recommend_result
        else:
            user_cat = req.get("category", {}) or {}
            category_info = {
                "recommended": False,
                "catId": user_cat.get("catId") or publisher.DEFAULT_CAT_ID,
                "catName": user_cat.get("catName") or publisher.DEFAULT_CAT_NAME,
                "channelCatId": user_cat.get("channelCatId") or publisher.DEFAULT_CHANNEL_CAT_ID,
                "tbCatId": user_cat.get("tbCatId") or publisher.DEFAULT_TB_CAT_ID,
                "cardList": [],
            }

        # 5) 图片上传
        xianyu_image_urls = publisher.upload_images_to_xianyu(image_urls)
        if not xianyu_image_urls:
            return ResultObject.failed("图片上传到闲鱼失败，请重试")

        # 6) 构造内部对象（编辑场景，携带 itemId）
        internal_obj = build_internal_item_object(
            req, xianyu_image_urls, category_info, is_edit=True
        )

        # 7) 调用 edit API
        result = call_fish_shop_api(
            cookie_str, FISH_SHOP_EDIT_API, FISH_SHOP_EDIT_VERSION,
            internal_obj, is_edit=True,
        )

        # 8) 校验响应 itemId 与目标 itemId 一致
        response_item_id = extract_response_item_id(result)
        if response_item_id and response_item_id != str(item_id):
            logger.warning(
                "fish_shop_edit_item_id_mismatch expected=%s got=%s",
                item_id, response_item_id,
            )
            return ResultObject.failed("编辑响应的 itemId 与目标不一致，已拒绝写入")

        # 9) 匹配响应 SKU
        response_skus = extract_response_skus(result)
        matched_skus = match_response_skus(response_skus, internal_obj["itemSkuList"])

        # 10) 持久化
        await _persist_skus_and_properties(
            db, tenant_id, account_id, str(item_id),
            internal_obj["itemProperties"], matched_skus,
        )
        await _save_edit_snapshot(
            db, tenant_id, account_id, str(item_id),
            {"internalItem": internal_obj, "responseSkus": matched_skus},
            source="edit",
        )

        # 11) 更新 xianyu_goods 主表的标题/价格/库存（仅更新这些安全字段）
        total_qty = sum(int(s.get("quantity", 0)) for s in matched_skus)
        min_price_cent = min(
            (int(s.get("priceInCent", 0)) for s in matched_skus),
            default=0,
        )
        from decimal import Decimal
        price_yuan = Decimal(min_price_cent) / Decimal(100)
        goods.title = title
        goods.price = str(price_yuan.quantize(Decimal("0.01")))
        goods.stock = str(total_qty)
        goods.quantity = total_qty
        await db.flush()

        await db.commit()

        # 12) 失效 editdetail 缓存，避免编辑成功后仍展示陈旧数据
        try:
            invalidate_edit_detail_cache(account_id, str(item_id))
        except Exception:
            # 缓存失效失败不影响编辑成功结果
            pass

        return ResultObject.success({
            "itemId": str(item_id),
            "skuList": matched_skus,
            "totalQuantity": str(total_qty),
            "minPriceInCent": str(min_price_cent),
        })
    except Exception as exc:
        logger.warning("fish_shop_edit_failed item_id=%s err=%s", item_id, str(exc)[:200])
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="fish_shop_edit",
            user_message="鱼小铺多规格编辑失败，请稍后重试",
        )


# ============================================================
# 路由：详情（用于编辑回显）
# ============================================================

@router.post("/detail")
async def get_fish_shop_detail(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    获取完整商品详情，用于编辑回显。

    请求体：
    {
        xianyuAccountId: int,
        itemId: str,
        bypassCache: bool  # 可选，True 时强制刷新缓存
    }

    优先级：
    1. 调用闲鱼 editdetail 接口获取完整编辑详情（标题、正文、图片、规格、SKU、运费、地址等）
    2. 本地编辑快照表（最新一条 source=publish/edit/detail_api）作为补充
    3. 本地 SKU/规格表（若快照缺失）
    4. 本地 xianyu_goods 简略数据（兜底，仅在 editdetail 接口失败时使用）

    权限校验：
    1. 必须是鱼小铺账号
    2. 商品必须归属当前账号
    3. 商品 can_edit 字段必须为 1（V1.21，来自 itemExtendList.itemEdit）
       - can_edit=0 时返回 edit_note 提示文案
    4. 不接受前端传入的 Cookie，由服务端从账号凭证解密取得

    安全：
    - 不打印 Cookie/token/sign
    - 异常消息只暴露脱敏信息
    """
    item_id = ""
    try:
        account_id = int(req.get("xianyuAccountId") or req.get("xianyu_account_id") or 0)
        if not account_id:
            return ResultObject.failed("缺少参数 xianyuAccountId")
        tenant_id = int(req.get("tenantId") or req.get("tenant_id") or req.get("_tenantId") or 0)
        if not tenant_id:
            return ResultObject.failed("缺少租户上下文")

        item_id = (req.get("itemId") or "").strip()
        if not item_id:
            return ResultObject.failed("缺少参数 itemId")

        # 1) 后端权限校验：必须是鱼小铺账号
        auth, is_fish_shop = await _get_account_auth_and_check_fish_shop(db, account_id, tenant_id)
        if not is_fish_shop:
            return ResultObject.failed("当前闲鱼账号不是鱼小铺，无法查看编辑详情", code=403)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效，请重新登录")

        # 2) 校验商品归属
        goods = await _verify_goods_belongs_to_account(db, tenant_id, account_id, item_id)
        if not goods:
            return ResultObject.failed("商品不存在或不归属当前账号", code=403)

        # 3) 商品级编辑能力校验（V1.21，来自 itemExtendList.itemEdit / itemOperationInfo）
        #    can_edit=0 表示闲鱼标记此商品不可编辑，需返回 edit_note 提示
        #    can_edit 字段默认值为 1（旧数据或未同步时按可编辑处理，由后端再次校验）
        can_edit = goods.can_edit if goods.can_edit is not None else 1
        edit_note = goods.edit_note or ""
        if can_edit == 0:
            note_msg = edit_note or "当前商品暂不支持编辑"
            logger.info(
                "fish_shop_detail_blocked item_id=%s reason=itemEdit_false note=%s",
                str(item_id)[:32], str(edit_note)[:80],
            )
            return ResultObject.failed(note_msg, code=403)

        # 4) 调用闲鱼 editdetail 接口获取完整编辑详情
        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)
        bypass_cache = bool(req.get("bypassCache") or req.get("bypass_cache") or False)

        # 在线程池中执行同步 HTTP 请求，避免阻塞事件循环
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            edit_detail = await loop.run_in_executor(
                None,
                lambda: fetch_fish_shop_edit_detail(
                    cookie_str=cookie_str,
                    account_id=account_id,
                    item_id=str(item_id),
                    bypass_cache=bypass_cache,
                )
            )
        except Exception as api_exc:
            # editdetail 接口失败时，记录脱敏日志，降级到本地数据
            logger.warning(
                "fish_shop_detail_api_failed item_id=%s err=%s",
                str(item_id)[:32], str(api_exc)[:200],
            )
            edit_detail = None

        # 5) 读取本地编辑快照与 SKU/规格（作为补充/兜底）
        result = await db.execute(
            select(XianyuGoodsEditSnapshot).where(
                and_(
                    XianyuGoodsEditSnapshot.tenant_id == tenant_id,
                    XianyuGoodsEditSnapshot.external_goods_id == str(item_id),
                    XianyuGoodsEditSnapshot.deleted == 0,
                )
            ).order_by(XianyuGoodsEditSnapshot.id.desc()).limit(1)
        )
        snapshot = result.scalar_one_or_none()

        result = await db.execute(
            select(XianyuGoodsProperty).where(
                and_(
                    XianyuGoodsProperty.tenant_id == tenant_id,
                    XianyuGoodsProperty.external_goods_id == str(item_id),
                    XianyuGoodsProperty.deleted == 0,
                )
            ).order_by(XianyuGoodsProperty.sort_order)
        )
        properties = result.scalars().all()

        result = await db.execute(
            select(XianyuGoodsSku).where(
                and_(
                    XianyuGoodsSku.tenant_id == tenant_id,
                    XianyuGoodsSku.external_goods_id == str(item_id),
                    XianyuGoodsSku.deleted == 0,
                )
            )
        )
        skus = result.scalars().all()

        # 构造本地规格数据
        item_properties: list = []
        for p in properties:
            result = await db.execute(
                select(XianyuGoodsPropertyValue).where(
                    and_(
                        XianyuGoodsPropertyValue.tenant_id == tenant_id,
                        XianyuGoodsPropertyValue.property_id == p.id,
                        XianyuGoodsPropertyValue.deleted == 0,
                    )
                ).order_by(XianyuGoodsPropertyValue.sort_order)
            )
            values = result.scalars().all()
            item_properties.append({
                "propertyName": p.property_name,
                "supportImage": bool(p.support_image),
                "propertyValues": [
                    {
                        "propertyValue": v.property_value,
                        "propertyValueImg": v.property_value_img or "",
                    }
                    for v in values
                ],
            })

        item_sku_list: list = []
        for s in skus:
            item_sku_list.append({
                "priceInCent": str(s.price_in_cent),
                "quantity": str(s.quantity),
                "propertyList": s.property_list_json or [],
                "skuId": s.sku_id or "",
                "inventoryId": s.inventory_id or "",
            })

        # 6) 优先使用 editdetail 接口返回的完整数据，本地数据作为补充
        if edit_detail is not None:
            # editdetail 接口成功：返回完整详情
            # 同时附带本地 SKU/规格数据，用于编辑提交时携带 skuId/inventoryId
            detail = {
                # 完整编辑详情（来自 editdetail 接口）
                "itemId": edit_detail.get("itemId", str(item_id)),
                "itemStatus": edit_detail.get("itemStatus", ""),
                "itemTypeStr": edit_detail.get("itemTypeStr", ""),
                "simpleItem": edit_detail.get("simpleItem", False),
                # 标题与正文（来自 itemTextDTO.title / itemTextDTO.desc）
                "title": edit_detail.get("title", ""),
                "description": edit_detail.get("description", ""),
                "wlDescription": edit_detail.get("wlDescription", ""),
                # 图片（完整列表 + 主图）
                "imageUrls": edit_detail.get("imageUrls", []),
                "majorImageUrl": edit_detail.get("majorImageUrl", ""),
                "imageList": edit_detail.get("imageList", []),
                # 价格与库存
                "priceInCent": edit_detail.get("priceInCent", 0),
                "quantity": edit_detail.get("quantity", 0),
                # 分类
                "catId": edit_detail.get("catId", ""),
                "catName": edit_detail.get("catName", ""),
                "tbCatId": edit_detail.get("tbCatId", ""),
                "channelCatId": edit_detail.get("channelCatId", ""),
                "itemLabelExtList": edit_detail.get("itemLabelExtList", []),
                # 地址
                "prov": edit_detail.get("prov", ""),
                "city": edit_detail.get("city", ""),
                "area": edit_detail.get("area", ""),
                "poiName": edit_detail.get("poiName", ""),
                "divisionId": edit_detail.get("divisionId", ""),
                "gps": edit_detail.get("gps", ""),
                "poiId": edit_detail.get("poiId", ""),
                # 运费
                "canFreeShipping": edit_detail.get("canFreeShipping", False),
                "onlyTakeSelf": edit_detail.get("onlyTakeSelf", False),
                "supportFreight": edit_detail.get("supportFreight", False),
                "idleTemplateId": edit_detail.get("idleTemplateId", ""),
                "templateId": edit_detail.get("templateId", ""),
                "postPriceInCent": edit_detail.get("postPriceInCent", 0),
                # 服务协议
                "userRightsProtocols": edit_detail.get("userRightsProtocols", []),
                # 多规格（简单商品为空列表）
                "itemProperties": edit_detail.get("itemProperties", []) or item_properties,
                "itemSkuList": edit_detail.get("itemSkuList", []) or item_sku_list,
                "propertyImageList": edit_detail.get("propertyImageList", []),
                "isMultiSpec": edit_detail.get("isMultiSpec", False),
                # 本地编辑快照（用于编辑提交时携带 skuId/inventoryId 等本地状态）
                "snapshot": snapshot.snapshot_json if snapshot else None,
                "canEdit": can_edit,
                "editNote": edit_note,
                "source": "editdetail",
            }
        else:
            # editdetail 接口失败：降级到本地数据
            # 此时仍允许用户查看，但提示数据可能不是最新
            detail = {
                "itemId": str(item_id),
                "title": goods.title or "",
                "description": goods.detail_info or goods.description or "",
                "imageUrls": (goods.image_url or "").split(",") if goods.image_url else [],
                "price": goods.price or "",
                "stock": goods.stock or "",
                "itemProperties": item_properties,
                "itemSkuList": item_sku_list,
                "snapshot": snapshot.snapshot_json if snapshot else None,
                "canEdit": can_edit,
                "editNote": edit_note,
                "source": "local_fallback",
                "warning": "未能从闲鱼获取最新编辑详情，当前展示为本地缓存数据",
            }

        return ResultObject.success(detail)
    except Exception as exc:
        logger.warning("fish_shop_detail_failed item_id=%s err=%s", item_id, str(exc)[:200])
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="fish_shop_detail",
            user_message="获取鱼小铺商品详情失败，请稍后重试",
        )


# ============================================================
# 辅助：类目推荐（异步包装）
# ============================================================

async def _sync_category_recommend(
    publisher: XianyuItemPublisher, title: str, desc: str, image_urls: list
) -> dict:
    """同步调用类目推荐，包装为异步。"""
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None, publisher.category_recommend, title, desc, image_urls
        )
    except Exception as exc:
        logger.warning("category_recommend_failed err=%s", str(exc)[:200])
        return {"recommended": False}
