"""Shared persistence for fish-shop multi-spec (property + SKU) data.

Used by:
- fish-shop publish/edit/detail routes
- goods detail snapshot backfill (goods_detail_fetcher)

The local tables (xianyu_goods_property / xianyu_goods_property_value /
xianyu_goods_sku) are the single source of truth for the product-edit page and
the auto-delivery SKU configuration panel.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import (
    XianyuGoodsProperty,
    XianyuGoodsPropertyValue,
    XianyuGoodsSku,
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_prop(prop: Any) -> Optional[dict]:
    if not isinstance(prop, dict):
        return None
    name = _safe_str(
        prop.get("propertyText")
        or prop.get("propertyName")
        or prop.get("name")
        or prop.get("key")
    )
    value = _safe_str(
        prop.get("valueText")
        or prop.get("propertyValue")
        or prop.get("value")
    )
    if not name or not value:
        return None
    return {"propertyText": name, "valueText": value}


def normalize_detail_sku_list(sku_list: Iterable[Any]) -> list[dict]:
    """Normalize raw xianyu detail-API SKU entries to publish-style entries.

    Handles both formats:
    - publish/edit: {skuId, inventoryId, priceInCent, quantity, propertyList:[{propertyText,valueText}]}
    - detail API:   {skuId, price/priceInCent, quantity, properties/propertyList:[{name,value}|{propertyText,valueText}]}
    """
    result: list[dict] = []
    for sku in sku_list:
        if not isinstance(sku, dict):
            continue
        raw_props = (
            sku.get("propertyList")
            or sku.get("properties")
            or sku.get("propertyValues")
            or []
        )
        prop_list = []
        if isinstance(raw_props, list):
            for prop in raw_props:
                normalized = _normalize_prop(prop)
                if normalized:
                    prop_list.append(normalized)

        price_cent = _safe_int(sku.get("priceInCent"))
        if price_cent <= 0:
            price = sku.get("price")
            if price not in (None, ""):
                try:
                    price_cent = int(round(float(price) * 100))
                except (TypeError, ValueError):
                    price_cent = 0

        result.append({
            "skuId": _safe_str(sku.get("skuId")),
            "inventoryId": _safe_str(sku.get("inventoryId")),
            "priceInCent": price_cent,
            "quantity": _safe_int(sku.get("quantity")),
            "propertyList": prop_list,
        })
    return result


def normalize_detail_properties(property_groups: Iterable[Any]) -> list[dict]:
    """Normalize raw detail-API property groups to publish-style groups."""
    result: list[dict] = []
    for group in property_groups:
        if not isinstance(group, dict):
            continue
        name = _safe_str(group.get("propertyName") or group.get("name"))
        if not name:
            continue
        raw_values = group.get("propertyValues") or group.get("values") or []
        values = []
        if isinstance(raw_values, list):
            for value in raw_values:
                if isinstance(value, str):
                    if value.strip():
                        values.append({"propertyValue": value.strip(), "propertyValueImg": ""})
                elif isinstance(value, dict):
                    v = _safe_str(
                        value.get("propertyValue")
                        or value.get("value")
                        or value.get("name")
                    )
                    if v:
                        values.append({
                            "propertyValue": v,
                            "propertyValueImg": _safe_str(
                                value.get("propertyValueImg") or value.get("img")
                            ),
                        })
        if values:
            result.append({
                "propertyName": name,
                "supportImage": bool(group.get("supportImage") or group.get("supportImageFlag")),
                "propertyValues": values,
            })
    return result


def derive_properties_from_skus(sku_list: Iterable[dict]) -> list[dict]:
    """Derive property groups from SKU propertyList when the detail API omits
    itemProperties (a common editdetail quirk)."""
    groups: dict[str, list[str]] = {}
    for sku in sku_list:
        if not isinstance(sku, dict):
            continue
        for prop in sku.get("propertyList") or []:
            if not isinstance(prop, dict):
                continue
            name = _safe_str(prop.get("propertyText"))
            value = _safe_str(prop.get("valueText"))
            if not name or not value:
                continue
            values = groups.setdefault(name, [])
            if value not in values:
                values.append(value)
    return [
        {
            "propertyName": name,
            "supportImage": False,
            "propertyValues": [
                {"propertyValue": value, "propertyValueImg": ""}
                for value in values
            ],
        }
        for name, values in groups.items()
    ]


def build_property_key(prop_list: list) -> str:
    """Build the deterministic property key used for SKU matching."""
    from .fish_shop_publish import build_property_key as _build
    return _build(prop_list)


async def persist_skus_and_properties(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    external_goods_id: str,
    property_groups: list,
    sku_list: list,
) -> None:
    """Idempotently replace local property + SKU rows for one goods."""
    external_goods_id = _safe_str(external_goods_id)
    if not external_goods_id:
        return

    # 1) soft-delete old rows
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

    # 2) insert property types
    property_id_map: dict[str, int] = {}
    for idx, group in enumerate(property_groups or []):
        name = _safe_str(group.get("propertyName"))
        if not name:
            continue
        prop = XianyuGoodsProperty(
            tenant_id=tenant_id,
            account_id=account_id,
            external_goods_id=external_goods_id,
            property_name=name,
            support_image=1 if group.get("supportImage") else 0,
            sort_order=idx,
        )
        db.add(prop)
        await db.flush()
        property_id_map[name] = prop.id

        for v_idx, value in enumerate(group.get("propertyValues", []) or []):
            if not isinstance(value, dict):
                continue
            val = _safe_str(value.get("propertyValue"))
            if not val:
                continue
            db.add(XianyuGoodsPropertyValue(
                tenant_id=tenant_id,
                property_id=prop.id,
                external_goods_id=external_goods_id,
                property_value=val,
                property_value_img=value.get("propertyValueImg") or None,
                sort_order=v_idx,
            ))

    # 3) insert SKUs
    for sku in sku_list or []:
        if not isinstance(sku, dict):
            continue
        prop_list = sku.get("propertyList") or []
        property_key = build_property_key(prop_list)
        db.add(XianyuGoodsSku(
            tenant_id=tenant_id,
            account_id=account_id,
            external_goods_id=external_goods_id,
            sku_id=_safe_str(sku.get("skuId")) or None,
            inventory_id=_safe_str(sku.get("inventoryId")) or None,
            property_list_json=prop_list,
            property_key=property_key,
            price_in_cent=_safe_int(sku.get("priceInCent")),
            quantity=_safe_int(sku.get("quantity")),
        ))

    await db.flush()
