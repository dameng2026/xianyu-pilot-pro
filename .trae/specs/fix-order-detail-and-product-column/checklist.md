# Checklist

- [x] DataInitializer.java 中 delivery_record 表已添加 delivery_method / quantity_requested / quantity_sent / platform_sync_time / delivery_fail_reason 五列的 addColumnIfMissing 迁移
- [x] 应用启动后日志无 SQL 异常（Unknown column）
- [x] 点击"查看详情"时 GET /api/orders/{id} 返回 code=200，不再出现"系统繁忙"
- [x] OrdersPage.vue 商品信息列展示为"封面图 + 商品名称（商品ID）"格式
- [x] 有 externalGoodsId 时商品ID 以括号内联显示在商品名称后
- [x] 无 externalGoodsId 时不显示括号
- [x] 无 goodsImage 时不渲染 img 标签
- [x] 前端 lint 无新增 error
