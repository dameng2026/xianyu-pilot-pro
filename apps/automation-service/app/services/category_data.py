"""
闲鱼商品分类树数据服务
负责：
1. 加载/保存分类树 JSON 文件
2. 将自动分类返回的候选分类合并到分类树中
3. 确保分类树始终包含闲鱼最新分类
"""

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 分类树 JSON 文件路径
_CATEGORIES_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../data/categories.json")
)

# 写锁（线程安全）
_write_lock = threading.Lock()


def _get_tree(data: dict) -> list:
    """从加载的数据中提取分类树列表（兼容 'cation' key）。"""
    return data.get("cation", data.get("categories", []))


def load_categories() -> dict:
    """
    加载分类树 JSON 文件。
    返回完整的数据字典。
    """
    if not os.path.exists(_CATEGORIES_PATH):
        logger.warning("分类树文件不存在: %s", _CATEGORIES_PATH)
        return {"cation": []}
    try:
        with open(_CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("加载分类树文件失败 errorType=%s", type(e).__name__)
        return {"cation": []}


def save_categories(data: dict) -> bool:
    """
    保存分类树数据到 JSON 文件。
    使用线程锁防止并发写。
    """
    try:
        with _write_lock:
            # 先写临时文件再原子替换，防止写一半崩溃
            tmp_path = _CATEGORIES_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            os.replace(tmp_path, _CATEGORIES_PATH)
        logger.info("分类树文件已保存: %s", _CATEGORIES_PATH)
        return True
    except Exception as e:
        logger.error("保存分类树文件失败 errorType=%s", type(e).__name__)
        return False


def _get_global_max_id(tree: list) -> int:
    """递归获取整棵树中最大的节点 id，用于新增节点时分配唯一 id。"""
    max_id = 0

    def walk(nodes):
        nonlocal max_id
        for n in nodes:
            max_id = max(max_id, n.get("id", 0) or 0)
            children = n.get("children", [])
            if children:
                walk(children)

    walk(tree)
    return max_id


def _ensure_node(
    nodes_list: list,
    name: str,
    channel_cat_id: str,
    cat_id: str,
    parent_id: int,
    next_id_ref: list,
) -> tuple:
    """
    在节点列表中查找或创建一个分类节点。

    查找优先级：
    1. channelCatId 精确匹配（最可靠，闲鱼频道类目 ID）
    2. catId 精确匹配（淘宝类目 ID）
    3. label/title 名称匹配（兼容旧数据）

    若找到则补全缺失的 ID 字段；若未找到则创建新节点。

    Args:
        nodes_list: 当前层级的节点列表（会被原地修改）
        name: 分类名称
        channel_cat_id: 闲鱼频道类目 ID（channelCatId/channelCat1Id 等）
        cat_id: 淘宝类目 ID（catId）
        parent_id: 父节点 id
        next_id_ref: [下一个可用 id] 的单元素列表，用于分配新 id

    Returns:
        (node, was_created) 元组
    """
    for node in nodes_list:
        node_channel_id = str(node.get("channelCatId", ""))
        node_cat_id = str(node.get("catId", ""))
        node_label = (node.get("label") or node.get("title") or "").strip()

        # 优先按 channelCatId 匹配
        if channel_cat_id and node_channel_id == channel_cat_id:
            if cat_id and not node_cat_id:
                node["catId"] = cat_id
            if name and not node_label:
                node["label"] = name
                node["title"] = name
            return node, False
        # 按 catId 匹配
        if cat_id and node_cat_id == cat_id:
            if channel_cat_id and not node_channel_id:
                node["channelCatId"] = channel_cat_id
            if name and not node_label:
                node["label"] = name
                node["title"] = name
            return node, False
        # 按名称匹配（兼容旧数据，旧节点没有 channelCatId/catId）
        if name and node_label == name:
            if channel_cat_id and not node_channel_id:
                node["channelCatId"] = channel_cat_id
            if cat_id and not node_cat_id:
                node["catId"] = cat_id
            return node, False

    # 创建新节点
    new_id = next_id_ref[0]
    next_id_ref[0] += 1
    new_node = {
        "id": new_id,
        "value": new_id,
        "label": name,
        "title": name,
        "pid": parent_id,
    }
    if channel_cat_id:
        new_node["channelCatId"] = channel_cat_id
    if cat_id:
        new_node["catId"] = cat_id
    nodes_list.append(new_node)
    logger.info(
        "新增分类节点: id=%d, label=%s, channelCatId=%s, catId=%s, pid=%d",
        new_id, name, channel_cat_id, cat_id, parent_id,
    )
    return new_node, True


def merge_candidates(candidates: List[dict]) -> int:
    """
    将自动分类返回的候选分类列表合并到分类树中。

    闲鱼 API 返回的分类层级为 4 级：
        channelCat1Name (一级) → channelCat2Name (二级)
        → channelCat3Name (三级) → catName/channelCatName (叶子)

    本函数会沿完整父级链路逐级创建节点，避免出现"孤儿子分类"。
    若叶子名称与三级名称相同（闲鱼常见，如 "美发 > 美发"），
    则将叶子 ID 合并到三级节点上，不再额外创建叶子。

    若候选缺少 channelCat1/2/3 信息（如 "其他闲置" 兜底分类），
    则直接以叶子名称作为一级分类。

    Args:
        candidates: 自动分类返回的候选列表，每个候选可包含
            channelCat1Id/Name, channelCat2Id/Name, channelCat3Id/Name,
            catId, catName, channelCatId, channelCatName 等字段

    Returns:
        新增的分类节点数量
    """
    if not candidates:
        return 0

    data = load_categories()
    tree = _get_tree(data)
    if not isinstance(tree, list):
        tree = []

    # 全局只计算一次最大 id，避免新增多个节点时 id 冲突
    next_id_ref = [_get_global_max_id(tree) + 1]

    added_count = 0
    seen_paths = set()  # 去重：按完整层级 ID 链路

    for cand in candidates:
        if not isinstance(cand, dict):
            continue

        # 构建 4 级层级链路
        chain = []
        for level in (1, 2, 3):
            name = (cand.get(f"channelCat{level}Name") or "").strip()
            id_val = str(cand.get(f"channelCat{level}Id", "")).strip()
            if name:
                chain.append({"name": name, "channelCatId": id_val, "catId": ""})

        # 叶子分类：优先 catName，回退 channelCatName
        leaf_name = (cand.get("catName") or cand.get("channelCatName") or cand.get("name") or "").strip()
        leaf_cat_id = str(cand.get("catId", "")).strip()
        leaf_channel_cat_id = str(cand.get("channelCatId", "")).strip()

        if leaf_name:
            if chain and chain[-1]["name"] == leaf_name:
                # 叶子名称与最后一级相同（如 "美发 > 美发"），合并 ID 到最后一级
                if leaf_cat_id:
                    chain[-1]["catId"] = leaf_cat_id
                if leaf_channel_cat_id and not chain[-1]["channelCatId"]:
                    chain[-1]["channelCatId"] = leaf_channel_cat_id
            else:
                chain.append({
                    "name": leaf_name,
                    "channelCatId": leaf_channel_cat_id,
                    "catId": leaf_cat_id,
                })

        if not chain:
            continue

        # 按 ID 链路去重（优先 channelCatId，回退 catId，再回退 name）
        path_key = "::".join(
            item["channelCatId"] or item["catId"] or item["name"] for item in chain
        )
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)

        # 沿链路逐级查找/创建节点，确保父级完整
        current_list = tree
        parent_id = 0
        added = False
        for i, item in enumerate(chain):
            node, was_created = _ensure_node(
                current_list,
                item["name"],
                item["channelCatId"],
                item["catId"],
                parent_id,
                next_id_ref,
            )
            if was_created:
                added = True
            # 非叶子节点：下钻到 children；叶子节点：无需 children
            if i < len(chain) - 1:
                current_list = node.setdefault("children", [])
                parent_id = node.get("id", 0)

        if added:
            added_count += 1

    if added_count > 0:
        data["cation"] = tree
        save_categories(data)
        logger.info("分类树合并完成: 新增 %d 个分类节点", added_count)
    else:
        logger.debug("分类树合并完成: 无新增分类")

    return added_count
