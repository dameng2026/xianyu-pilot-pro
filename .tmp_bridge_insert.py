async def proxy_get_about_content() -> dict[str, Any]:
    """从商业版后端获取关于页内容（含微信群二维码、赞助码等 communityCards）。

    桥接启用时调用商业版 GET /about 端点，获取后台配置的 communityCards。
    商业版返回的 imageUrl 为相对路径（如 /uploads/images/...），
    需拼接商业版后端 origin 后才能被开源版前端直接加载。
    桥接未配置或调用失败时降级到本地默认内容。
    """
    config = get_commercial_bridge_config()
    if not commercial_bridge_is_configured(config):
        return default_about_content()
    try:
        data = await _request_bridge(config, "GET", "/about")
        if isinstance(data, dict) and data:
            _rewrite_community_card_image_urls(data, config["baseUrl"])
            data["bridgeEnabled"] = True
            return data
    except CommercialBridgeError as exc:
        logger.warning("proxy_get_about_content fallback to local: %s", exc)
    return default_about_content()


def _rewrite_community_card_image_urls(content: dict[str, Any], base_url: str) -> None:
    """将 communityCards 中的相对 imageUrl 拼接为商业版后端的绝对 URL。"""
    origin = base_url.rstrip("/")
    cards = content.get("communityCards")
    if not isinstance(cards, list):
        return
    for card in cards:
        if not isinstance(card, dict):
            continue
        url = _as_text(card.get("imageUrl"))
        if url and url.startswith("/"):
            card["imageUrl"] = f"{origin}{url}"


