# Tasks

- [x] Task 1: 修复 delivery_record 表缺失列导致的详情接口报错
  - [x] SubTask 1.1: 在 `DataInitializer.java` 中为 `delivery_record` 表添加 `delivery_method`、`quantity_requested`、`quantity_sent`、`platform_sync_time`、`delivery_fail_reason` 五列的 `addColumnIfMissing` 迁移
  - [x] SubTask 1.2: 添加 `delivery_fail_reason` 数据回填（从 `fail_reason` 列复制）
- [x] Task 2: 优化订单列表商品信息列展示格式
  - [x] SubTask 2.1: 修改 `OrdersPage.vue` 商品信息列模板，将商品ID 从单独一行改为括号内联在商品名称后
  - [x] SubTask 2.2: 添加 `.goods-id-inline` CSS 样式类
- [x] Task 3: 重新构建 core-api 并重启验证
  - [x] SubTask 3.1: `mvn package -DskipTests` 构建成功
  - [x] SubTask 3.2: 启动后端口 18080 监听正常，启动日志无 SQL 异常

# Task Dependencies
- Task 2 独立于 Task 1，可并行
- Task 3 依赖 Task 1 完成后重新构建
