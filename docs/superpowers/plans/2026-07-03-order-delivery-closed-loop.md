# Order And Delivery Closed Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first closed loop from the reference project by enriching order data, enabling manual and scheduled delivery actions, syncing local delivery state, and exposing the same behavior in the user-facing Vue pages.

**Architecture:** Keep `apps/core-api` as the tenant-aware orchestration and read-model layer. Use Spring Boot + MyBatis/JdbcTemplate to project richer order and delivery data, and keep execution-heavy behavior in `apps/automation-service` behind `AutomationClient` internal routes. Frontend pages in `apps/user-web` should consume only the Java REST surface and stop depending on mismatched legacy payload shapes.

**Tech Stack:** Spring Boot 3.3, MyBatis/JdbcTemplate, Maven, JUnit 5, Mockito, Vue 3, Vite, Node assert-based contract scripts, FastAPI, pytest, Playwright/browser verification

---

## File Map

**Backend read-side files**

- Modify: `apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuTradeOrderVO.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuTradeOrderItemVO.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuTradeOrder.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuTradeOrderItem.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/entity/DeliveryRecord.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuTradeOrderMapper.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuTradeOrderItemMapper.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/XianyuTradeOrderService.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/XianyuTradeOrderServiceTest.java`

**Backend command-side files**

- Create: `apps/core-api/src/main/java/com/xianyu/admin/dto/OrderManualDeliveryRequest.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/dto/OrderSyncRequest.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/dto/ScheduleRedeliveryRequest.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/service/OrderDeliveryCommandService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/XianyuTradeOrderController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/AutoDeliveryRecordController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/DeliveryExecutionService.java`
- Create: `apps/core-api/src/main/resources/db/migration/V1.8__order_delivery_closed_loop.sql`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/OrderDeliveryCommandServiceTest.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/controller/XianyuTradeOrderControllerTest.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/controller/AutoDeliveryRecordControllerTest.java`

**Scheduled task and automation files**

- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/ScheduledTaskController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/AutomationClient.java`
- Modify: `apps/automation-service/app/api/v1/routes/internal.py`
- Modify: `apps/automation-service/app/api/v1/routes/order.py`
- Modify: `apps/automation-service/app/services/automation_runtime.py`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/controller/ScheduledTaskControllerTest.java`
- Test: `apps/automation-service/tests/test_runtime_order_delivery_tasks.py`

**Frontend files**

- Modify: `apps/user-web/src/api/orders.js`
- Modify: `apps/user-web/src/api/autoDelivery.js`
- Modify: `apps/user-web/src/api/scheduledTasks.js`
- Modify: `apps/user-web/src/pages/OrdersPage.vue`
- Modify: `apps/user-web/src/pages/AutoDeliveryPage.vue`
- Modify: `apps/user-web/src/pages/DeliveryRecordsPage.vue`
- Modify: `apps/user-web/src/pages/ScheduledTasksPage.vue`
- Create: `apps/user-web/scripts/orders-page-contract.test.mjs`
- Create: `apps/user-web/scripts/delivery-records-contract.test.mjs`
- Create: `apps/user-web/scripts/scheduled-tasks-contract.test.mjs`
- Modify: `apps/user-web/package.json`

**Verification artifacts**

- Create: `docs/superpowers/reports/2026-07-03-phase1-order-delivery-verification.md`

---

### Task 1: Enrich The Order Read Model

**Files:**

- Modify: `apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuTradeOrderVO.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuTradeOrderItemVO.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuTradeOrder.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuTradeOrderItem.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/entity/DeliveryRecord.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuTradeOrderMapper.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuTradeOrderItemMapper.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/XianyuTradeOrderService.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/XianyuTradeOrderServiceTest.java`

- [ ] **Step 1: Write the failing service tests**

```java
@ExtendWith(MockitoExtension.class)
class XianyuTradeOrderServiceTest {

    @Mock
    private XianyuTradeOrderMapper orderMapper;

    @Mock
    private XianyuTradeOrderItemMapper orderItemMapper;

    @Mock
    private JdbcTemplate jdbcTemplate;

    private XianyuTradeOrderService service;

    @BeforeEach
    void setUp() {
        service = new XianyuTradeOrderService(orderMapper, orderItemMapper, jdbcTemplate);
    }

    @Test
    void detailShouldIncludeMultiSpecQuantityAndLatestDeliverySnapshot() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(88L);
        order.setTenantId(1L);
        order.setAccountId(9L);
        order.setExternalOrderId("ORDER-88");
        order.setOrderStatus(2);
        order.setBuyerName("buyer-a");

        XianyuTradeOrderItem item = new XianyuTradeOrderItem();
        item.setId(1L);
        item.setOrderId(88L);
        item.setGoodsTitle("Digital Pack");
        item.setGoodsCount(3);
        item.setSpecName("版本");
        item.setSpecValue("标准版");

        when(orderMapper.findById(1L, 88L)).thenReturn(order);
        when(orderItemMapper.findByOrderId(1L, 88L)).thenReturn(List.of(item));
        when(jdbcTemplate.queryForList(contains("FROM delivery_record"), eq(1L), eq(88L)))
                .thenReturn(List.of(Map.of(
                        "delivery_method", "manual_text",
                        "delivery_status", "failed",
                        "delivery_fail_reason", "stock out",
                        "delivery_content", "link-1",
                        "quantity_requested", 3,
                        "quantity_sent", 1,
                        "platform_sync_time", Timestamp.valueOf("2026-07-03 10:00:00")
                )));

        XianyuTradeOrderVO detail = service.detail(1L, 88L);

        assertEquals("manual_text", detail.getDeliveryMethod());
        assertEquals("failed", detail.getDeliveryStatus());
        assertEquals("stock out", detail.getDeliveryFailReason());
        assertEquals(3, detail.getQuantityTotal());
        assertEquals("版本: 标准版", detail.getItems().get(0).getSpecSummary());
    }

    @Test
    void pageShouldExposeItemSummaryForOrdersWithoutEmbeddedItems() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(101L);
        order.setTenantId(1L);
        order.setAccountId(9L);
        order.setExternalOrderId("ORDER-101");
        order.setOrderStatus(3);

        when(orderMapper.count(1L, null, null, null)).thenReturn(1);
        when(orderMapper.list(1L, null, null, null, 0, 20)).thenReturn(List.of(order));
        when(jdbcTemplate.queryForList(contains("FROM xianyu_trade_order_item"), eq(1L), eq(101L)))
                .thenReturn(List.of(
                        Map.of("goods_title", "Pack A", "goods_count", 2),
                        Map.of("goods_title", "Pack B", "goods_count", 1)
                ));

        PageResult<XianyuTradeOrderVO> result = service.page(1L, null, null, null, 1, 20);

        assertEquals("Pack A x2 / Pack B x1", result.getRecords().get(0).getItemSummary());
        assertEquals(3, result.getRecords().get(0).getQuantityTotal());
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `mvn -Dtest=XianyuTradeOrderServiceTest test`

Expected: FAIL with constructor and getter/setter compilation errors for the new order projection fields such as `specName`, `specSummary`, `deliveryMethod`, and `quantityTotal`.

- [ ] **Step 3: Expand the DTO and entity fields**

```java
public class XianyuTradeOrderVO {
    private String itemSummary;
    private Integer quantityTotal;
    private String deliveryMethod;
    private String deliveryStatus;
    private String deliveryFailReason;
    private String deliveryContent;
    private Integer quantityRequested;
    private Integer quantitySent;
    private LocalDateTime platformSyncTime;
}

public class XianyuTradeOrderItemVO {
    private String specName;
    private String specValue;
    private String specSummary;
    private String externalGoodsId;
}

@Entity
@Table(name = "xianyu_trade_order_item")
public class XianyuTradeOrderItem extends BaseEntity {
    @Column(name = "spec_name")
    private String specName;

    @Column(name = "spec_value")
    private String specValue;
}
```

- [ ] **Step 4: Add read-side aggregation in `XianyuTradeOrderService`**

```java
public class XianyuTradeOrderService {
    private final JdbcTemplate jdbcTemplate;

    public XianyuTradeOrderService(
            XianyuTradeOrderMapper orderMapper,
            XianyuTradeOrderItemMapper orderItemMapper,
            JdbcTemplate jdbcTemplate
    ) {
        this.orderMapper = orderMapper;
        this.orderItemMapper = orderItemMapper;
        this.jdbcTemplate = jdbcTemplate;
    }

    private void enrichWithDeliverySnapshot(Long tenantId, XianyuTradeOrderVO vo) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT delivery_method, delivery_status, delivery_fail_reason, delivery_content, " +
                        "quantity_requested, quantity_sent, platform_sync_time " +
                        "FROM delivery_record WHERE tenant_id=? AND order_id=? AND deleted=0 " +
                        "ORDER BY created_time DESC LIMIT 1",
                tenantId, vo.getId()
        );
        if (!rows.isEmpty()) {
            Map<String, Object> row = rows.get(0);
            vo.setDeliveryMethod(asString(row.get("delivery_method")));
            vo.setDeliveryStatus(asString(row.get("delivery_status")));
            vo.setDeliveryFailReason(asString(row.get("delivery_fail_reason")));
            vo.setDeliveryContent(asString(row.get("delivery_content")));
            vo.setQuantityRequested(asInteger(row.get("quantity_requested")));
            vo.setQuantitySent(asInteger(row.get("quantity_sent")));
            vo.setPlatformSyncTime(asDateTime(row.get("platform_sync_time")));
        }
    }

    private String buildItemSummary(List<XianyuTradeOrderItemVO> items) {
        return items.stream()
                .map(item -> item.getGoodsTitle() + " x" + (item.getGoodsCount() == null ? 1 : item.getGoodsCount()))
                .limit(2)
                .collect(Collectors.joining(" / "));
    }
}
```

- [ ] **Step 5: Re-run the targeted tests and keep them green**

Run: `mvn -Dtest=XianyuTradeOrderServiceTest test`

Expected: PASS with both new tests green and no compilation errors.

- [ ] **Step 6: Commit the read-model slice**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuTradeOrderVO.java \
        apps/core-api/src/main/java/com/xianyu/admin/dto/XianyuTradeOrderItemVO.java \
        apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuTradeOrder.java \
        apps/core-api/src/main/java/com/xianyu/admin/entity/XianyuTradeOrderItem.java \
        apps/core-api/src/main/java/com/xianyu/admin/entity/DeliveryRecord.java \
        apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuTradeOrderMapper.java \
        apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuTradeOrderItemMapper.java \
        apps/core-api/src/main/java/com/xianyu/admin/service/XianyuTradeOrderService.java \
        apps/core-api/src/test/java/com/xianyu/admin/service/XianyuTradeOrderServiceTest.java
git commit -m "feat: enrich order read model with delivery snapshot"
```

### Task 2: Add Manual Delivery, Sync, And Redelivery Commands

**Files:**

- Create: `apps/core-api/src/main/java/com/xianyu/admin/dto/OrderManualDeliveryRequest.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/dto/OrderSyncRequest.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/dto/ScheduleRedeliveryRequest.java`
- Create: `apps/core-api/src/main/java/com/xianyu/admin/service/OrderDeliveryCommandService.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/XianyuTradeOrderController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/AutoDeliveryRecordController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/DeliveryExecutionService.java`
- Create: `apps/core-api/src/main/resources/db/migration/V1.8__order_delivery_closed_loop.sql`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/service/OrderDeliveryCommandServiceTest.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/controller/XianyuTradeOrderControllerTest.java`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/controller/AutoDeliveryRecordControllerTest.java`

- [ ] **Step 1: Write the failing command-side tests**

```java
@ExtendWith(MockitoExtension.class)
class OrderDeliveryCommandServiceTest {

    @Mock
    private XianyuTradeOrderMapper orderMapper;

    @Mock
    private XianyuTradeOrderItemMapper orderItemMapper;

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private AutomationClient automationClient;

    @Mock
    private DeliveryExecutionService deliveryExecutionService;

    private OrderDeliveryCommandService service;

    @BeforeEach
    void setUp() {
        service = new OrderDeliveryCommandService(orderMapper, orderItemMapper, jdbcTemplate, automationClient, deliveryExecutionService);
    }

    @Test
    void manualDeliveryShouldCreateRecordAndExecuteImmediately() {
        XianyuTradeOrder order = new XianyuTradeOrder();
        order.setId(55L);
        order.setTenantId(1L);
        order.setAccountId(8L);
        order.setExternalOrderId("ORDER-55");
        when(orderMapper.findById(1L, 55L)).thenReturn(order);

        OrderManualDeliveryRequest request = new OrderManualDeliveryRequest();
        request.setDeliveryMode("text");
        request.setDeliveryTiming("after_payment");
        request.setDeliveryContent("download-link");
        request.setQuantityRequested(2);

        service.manualDelivery(1L, 55L, request);

        verify(jdbcTemplate).update(contains("INSERT INTO delivery_record"), any(), any(), any(), any(), any(), any(), any(), any(), any());
        verify(deliveryExecutionService).retryDelivery(anyLong(), eq(1L));
    }

    @Test
    void scheduleRedeliveryShouldCreateScheduledTaskForFailedRecord() {
        when(jdbcTemplate.queryForMap(contains("FROM delivery_record"), eq(900L), eq(1L)))
                .thenReturn(Map.of("id", 900L, "order_id", 55L, "account_id", 8L, "delivery_timing", "after_payment"));

        ScheduleRedeliveryRequest request = new ScheduleRedeliveryRequest();
        request.setCronExpression("0 0/15 * * * ?");

        service.scheduleRedelivery(1L, 900L, request);

        verify(jdbcTemplate).update(contains("INSERT INTO scheduled_task"), eq(1L), eq(8L), eq("redelivery"), any(), eq("0 0/15 * * * ?"), contains("\"recordId\":900"), eq(1));
    }
}
```

```java
@WebMvcTest(XianyuTradeOrderController.class)
class XianyuTradeOrderControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private XianyuTradeOrderService orderService;

    @MockBean
    private OrderDeliveryCommandService orderDeliveryCommandService;

    @Test
    void manualDeliveryEndpointShouldReturnOk() throws Exception {
        mockMvc.perform(post("/api/orders/55/manual-delivery")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "deliveryMode":"text",
                                  "deliveryTiming":"after_payment",
                                  "deliveryContent":"download-link",
                                  "quantityRequested":2
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `mvn -Dtest=OrderDeliveryCommandServiceTest,XianyuTradeOrderControllerTest,AutoDeliveryRecordControllerTest test`

Expected: FAIL because `OrderDeliveryCommandService`, request DTOs, and new endpoints do not exist yet.

- [ ] **Step 3: Create the migration and request DTOs**

```sql
ALTER TABLE delivery_record
    ADD COLUMN quantity_requested INT DEFAULT NULL COMMENT '请求发货数量',
    ADD COLUMN quantity_sent INT DEFAULT NULL COMMENT '实际已发货数量',
    ADD COLUMN delivery_method VARCHAR(32) DEFAULT NULL COMMENT 'manual_text/manual_card/auto_text/auto_card',
    ADD COLUMN delivery_status VARCHAR(32) DEFAULT NULL COMMENT 'pending/running/success/failed/partial',
    ADD COLUMN delivery_fail_reason VARCHAR(255) DEFAULT NULL COMMENT '失败原因',
    ADD COLUMN platform_delivery_status VARCHAR(32) DEFAULT NULL COMMENT '平台发货状态',
    ADD COLUMN platform_sync_time DATETIME DEFAULT NULL COMMENT '平台状态同步时间',
    ADD COLUMN receiver_info JSON DEFAULT NULL COMMENT '买家会话信息';

ALTER TABLE xianyu_trade_order_item
    ADD COLUMN spec_name VARCHAR(128) DEFAULT NULL COMMENT '规格名',
    ADD COLUMN spec_value VARCHAR(255) DEFAULT NULL COMMENT '规格值';
```

```java
public class OrderManualDeliveryRequest {
    @NotBlank
    private String deliveryMode;

    @NotBlank
    private String deliveryTiming;

    @NotBlank
    private String deliveryContent;

    @Min(1)
    private Integer quantityRequested = 1;
}

public class OrderSyncRequest {
    private Long accountId;
    private String externalOrderId;
    private Boolean syncDeliveryStatus = Boolean.TRUE;
}
```

- [ ] **Step 4: Implement the new command service and wire the endpoints**

```java
@Service
public class OrderDeliveryCommandService {

    public void manualDelivery(Long tenantId, Long orderId, OrderManualDeliveryRequest request) {
        XianyuTradeOrder order = requireOrder(tenantId, orderId);
        jdbcTemplate.update(
                "INSERT INTO delivery_record(tenant_id, account_id, order_id, delivery_timing, delivery_mode, delivery_method, " +
                        "delivery_content, content, quantity_requested, quantity_sent, status, delivery_status, retry_count, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,NOW(),NOW(),0)",
                tenantId,
                order.getAccountId(),
                orderId,
                request.getDeliveryTiming(),
                request.getDeliveryMode(),
                "manual_" + request.getDeliveryMode(),
                request.getDeliveryContent(),
                request.getDeliveryContent(),
                request.getQuantityRequested(),
                0,
                0,
                "pending"
        );

        Long recordId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        deliveryExecutionService.retryDelivery(recordId, tenantId);
    }

    public void syncOrder(Long tenantId, Long orderId) {
        XianyuTradeOrder order = requireOrder(tenantId, orderId);
        automationClient.postInternalForData(
                "/api/internal/orders/sync-sold",
                Map.of("tenantId", tenantId, "accountId", order.getAccountId(), "externalOrderId", order.getExternalOrderId()),
                tenantId
        );
    }

    public void syncOrders(Long tenantId, OrderSyncRequest request) {
        automationClient.postInternalForData(
                "/api/internal/orders/sync-sold",
                Map.of(
                        "tenantId", tenantId,
                        "accountId", request.getAccountId(),
                        "externalOrderId", request.getExternalOrderId(),
                        "syncDeliveryStatus", request.getSyncDeliveryStatus()
                ),
                tenantId
        );
    }
}
```

```java
@PostMapping("/{id}/manual-delivery")
public Result<Void> manualDelivery(@PathVariable Long id, @Valid @RequestBody OrderManualDeliveryRequest request) {
    Long tenantId = TenantContext.getCurrentTenantId();
    orderDeliveryCommandService.manualDelivery(tenantId, id, request);
    return Result.ok(null);
}

@PostMapping("/{id}/sync")
public Result<Void> syncOne(@PathVariable Long id) {
    Long tenantId = TenantContext.getCurrentTenantId();
    orderDeliveryCommandService.syncOrder(tenantId, id);
    return Result.ok(null);
}

@PostMapping("/sync")
public Result<Void> syncList(@RequestBody OrderSyncRequest request) {
    Long tenantId = TenantContext.getCurrentTenantId();
    orderDeliveryCommandService.syncOrders(tenantId, request);
    return Result.ok(null);
}

@PostMapping("/{id}/schedule-redelivery")
public Result<Void> scheduleRedelivery(@PathVariable Long id, @Valid @RequestBody ScheduleRedeliveryRequest request) {
    Long tenantId = TenantContext.getCurrentTenantId();
    orderDeliveryCommandService.scheduleRedelivery(tenantId, id, request);
    return Result.ok(null);
}
```

- [ ] **Step 5: Re-run the targeted tests and keep them green**

Run: `mvn -Dtest=OrderDeliveryCommandServiceTest,XianyuTradeOrderControllerTest,AutoDeliveryRecordControllerTest test`

Expected: PASS with the new delivery and redelivery endpoints green.

- [ ] **Step 6: Commit the command slice**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/dto/OrderManualDeliveryRequest.java \
        apps/core-api/src/main/java/com/xianyu/admin/dto/OrderSyncRequest.java \
        apps/core-api/src/main/java/com/xianyu/admin/dto/ScheduleRedeliveryRequest.java \
        apps/core-api/src/main/java/com/xianyu/admin/service/OrderDeliveryCommandService.java \
        apps/core-api/src/main/java/com/xianyu/admin/controller/XianyuTradeOrderController.java \
        apps/core-api/src/main/java/com/xianyu/admin/controller/AutoDeliveryRecordController.java \
        apps/core-api/src/main/java/com/xianyu/admin/service/DeliveryExecutionService.java \
        apps/core-api/src/main/resources/db/migration/V1.8__order_delivery_closed_loop.sql \
        apps/core-api/src/test/java/com/xianyu/admin/service/OrderDeliveryCommandServiceTest.java \
        apps/core-api/src/test/java/com/xianyu/admin/controller/XianyuTradeOrderControllerTest.java \
        apps/core-api/src/test/java/com/xianyu/admin/controller/AutoDeliveryRecordControllerTest.java
git commit -m "feat: add delivery command endpoints and redelivery flow"
```

### Task 3: Expand Scheduled Tasks And Python Runtime Support

**Files:**

- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/ScheduledTaskController.java`
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/AutomationClient.java`
- Modify: `apps/automation-service/app/api/v1/routes/internal.py`
- Modify: `apps/automation-service/app/api/v1/routes/order.py`
- Modify: `apps/automation-service/app/services/automation_runtime.py`
- Test: `apps/core-api/src/test/java/com/xianyu/admin/controller/ScheduledTaskControllerTest.java`
- Test: `apps/automation-service/tests/test_runtime_order_delivery_tasks.py`

- [ ] **Step 1: Write the failing Java and Python tests**

```java
@WebMvcTest(ScheduledTaskController.class)
class ScheduledTaskControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private JdbcTemplate jdbcTemplate;

    @MockBean
    private AutomationClient automationClient;

    @Test
    void createShouldRejectUnsupportedTaskType() throws Exception {
        mockMvc.perform(post("/api/scheduled-tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "taskName":"补发货-900",
                                  "taskType":"not_supported",
                                  "cronExpression":"0 0/15 * * * ?",
                                  "configJson":"{\\"recordId\\":900}",
                                  "enabled":1
                                }
                                """))
                .andExpect(status().isBadRequest());
    }
}
```

```python
import pytest

from app.services.automation_runtime import execute_scheduled_task


class _FakeAsyncDB:
    async def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM scheduled_task" in sql:
            return _Rows.one({
                "id": 77,
                "tenant_id": 1,
                "account_id": 8,
                "task_type": "redelivery",
                "config_json": '{"recordId": 900}'
            })
        raise AssertionError(sql)

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_execute_scheduled_task_dispatches_redelivery(monkeypatch):
    called = {}

    async def fake_redelivery(db, tenant_id, task):
        called["tenant_id"] = tenant_id
        called["task_type"] = task["task_type"]
        return {"processed": 1}

    monkeypatch.setattr("app.services.automation_runtime._run_redelivery_task", fake_redelivery)
    result = await execute_scheduled_task(_FakeAsyncDB(), 77, 1)

    assert result["processed"] == 1
    assert called == {"tenant_id": 1, "task_type": "redelivery"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `mvn -Dtest=ScheduledTaskControllerTest test`

Expected: FAIL because the controller currently accepts unsupported task types instead of rejecting them.

Run: `pytest tests/test_runtime_order_delivery_tasks.py -q`

Expected: FAIL because `redelivery`, `sync_orders`, and `sync_delivery_status` handlers do not exist yet.

- [ ] **Step 3: Implement task-type support in Java and Python**

```java
private static final Set<String> SUPPORTED_TASK_TYPES = Set.of(
        "sync_goods",
        "sync_orders",
        "sync_delivery_status",
        "redelivery",
        "polish_goods",
        "workflow"
);

private void validateTaskType(String taskType) {
    if (!SUPPORTED_TASK_TYPES.contains(taskType)) {
        throw new BizException(400, "unsupported taskType: " + taskType);
    }
}
```

```python
async def _run_redelivery_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    config = _load_task_config(task)
    record_id = int(config["recordId"])
    return await _call_java_or_internal_delivery_retry(db, tenant_id, record_id)


async def _run_sync_orders_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    config = _load_task_config(task)
    return await sync_sold_orders_for_account(
        db,
        tenant_id=tenant_id,
        account_id=config.get("accountId"),
    )


async def _run_sync_delivery_status_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    config = _load_task_config(task)
    return await sync_delivery_status_for_account(
        db,
        tenant_id=tenant_id,
        account_id=config.get("accountId"),
    )
```

- [ ] **Step 4: Add the internal Python routes used by Java order sync commands**

```python
@router.post("/orders/sync-sold")
async def internal_sync_sold_orders(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    result = await sync_sold_orders_for_account(
        db,
        tenant_id=int(body["tenantId"]),
        account_id=body.get("accountId"),
        external_order_id=body.get("externalOrderId"),
    )
    return ResultObject.success(result)


@router.post("/orders/sync-delivery-status")
async def internal_sync_delivery_status(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    result = await sync_delivery_status_for_account(
        db,
        tenant_id=int(body["tenantId"]),
        account_id=body.get("accountId"),
        external_order_id=body.get("externalOrderId"),
    )
    return ResultObject.success(result)
```

- [ ] **Step 5: Re-run both test suites**

Run: `mvn -Dtest=ScheduledTaskControllerTest test`

Expected: PASS with unsupported task types rejected and phase-1 task types still accepted.

Run: `pytest tests/test_runtime_order_delivery_tasks.py tests/test_ws_delivery_handler.py -q`

Expected: PASS with the new runtime dispatch behavior and no regression in the websocket delivery path.

- [ ] **Step 6: Commit the scheduled-task slice**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/controller/ScheduledTaskController.java \
        apps/core-api/src/main/java/com/xianyu/admin/service/AutomationClient.java \
        apps/core-api/src/test/java/com/xianyu/admin/controller/ScheduledTaskControllerTest.java \
        apps/automation-service/app/api/v1/routes/internal.py \
        apps/automation-service/app/api/v1/routes/order.py \
        apps/automation-service/app/services/automation_runtime.py \
        apps/automation-service/tests/test_runtime_order_delivery_tasks.py
git commit -m "feat: support order and delivery scheduled tasks"
```

### Task 4: Update User-Web Pages And Contract Tests

**Files:**

- Modify: `apps/user-web/src/api/orders.js`
- Modify: `apps/user-web/src/api/autoDelivery.js`
- Modify: `apps/user-web/src/api/scheduledTasks.js`
- Modify: `apps/user-web/src/pages/OrdersPage.vue`
- Modify: `apps/user-web/src/pages/AutoDeliveryPage.vue`
- Modify: `apps/user-web/src/pages/DeliveryRecordsPage.vue`
- Modify: `apps/user-web/src/pages/ScheduledTasksPage.vue`
- Create: `apps/user-web/scripts/orders-page-contract.test.mjs`
- Create: `apps/user-web/scripts/delivery-records-contract.test.mjs`
- Create: `apps/user-web/scripts/scheduled-tasks-contract.test.mjs`
- Modify: `apps/user-web/package.json`

- [ ] **Step 1: Write the failing frontend contract tests**

```javascript
import assert from 'node:assert/strict'
import { buildOrderDetailViewModel } from '../src/utils/orderPageState.js'

const viewModel = buildOrderDetailViewModel({
  externalOrderId: 'ORDER-55',
  deliveryMethod: 'manual_text',
  deliveryStatus: 'partial',
  quantityRequested: 3,
  quantitySent: 1,
  items: [
    { goodsTitle: 'Digital Pack', goodsCount: 3, specName: '版本', specValue: '标准版' }
  ]
})

assert.equal(viewModel.deliveryProgressText, '1 / 3')
assert.equal(viewModel.itemLines[0], 'Digital Pack x3 · 版本: 标准版')
assert.equal(viewModel.deliveryBadge, 'orange')
```

```javascript
import assert from 'node:assert/strict'
import { normalizeScheduledTaskTypes } from '../src/utils/scheduledTaskState.js'

assert.deepEqual(
  normalizeScheduledTaskTypes(['sync_goods', 'sync_orders', 'sync_delivery_status', 'redelivery']),
  [
    { value: 'sync_goods', label: '同步商品' },
    { value: 'sync_orders', label: '同步订单' },
    { value: 'sync_delivery_status', label: '同步发货状态' },
    { value: 'redelivery', label: '补发货' }
  ]
)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node ./scripts/orders-page-contract.test.mjs`

Expected: FAIL because `orderPageState.js` and its view-model helpers do not exist yet.

Run: `node ./scripts/scheduled-tasks-contract.test.mjs`

Expected: FAIL because the scheduled-task normalization helpers do not exist yet.

- [ ] **Step 3: Add small UI state helpers and API wrappers**

```javascript
export function manualDeliverOrder(id, data) {
  return request({ url: `/orders/${id}/manual-delivery`, method: 'post', data })
}

export function syncOrder(id) {
  return request({ url: `/orders/${id}/sync`, method: 'post' })
}

export function scheduleRedelivery(id, data) {
  return request({ url: `/auto-delivery/records/${id}/schedule-redelivery`, method: 'post', data })
}
```

```javascript
export function buildOrderDetailViewModel(order) {
  const items = Array.isArray(order.items) ? order.items : []
  const itemLines = items.map(item => {
    const spec = item.specSummary || [item.specName, item.specValue].filter(Boolean).join(': ')
    return `${item.goodsTitle || '-'} x${item.goodsCount || 1}${spec ? ` · ${spec}` : ''}`
  })
  return {
    itemLines,
    deliveryProgressText: `${order.quantitySent ?? 0} / ${order.quantityRequested ?? order.quantityTotal ?? 0}`,
    deliveryBadge: order.deliveryStatus === 'failed' ? 'red' : order.deliveryStatus === 'partial' ? 'orange' : 'green'
  }
}
```

- [ ] **Step 4: Update the pages to use the new payload shape**

```vue
<template #op="{ row }">
  <button class="link" @click.stop="selectOrder(row)">详情</button>
  <button class="link" @click.stop="openManualDelivery(row)">手动发货</button>
  <button class="link" @click.stop="syncCurrentOrder(row)">同步状态</button>
</template>
```

```vue
<select v-model="form.taskType">
  <option value="sync_goods">同步商品</option>
  <option value="sync_orders">同步订单</option>
  <option value="sync_delivery_status">同步发货状态</option>
  <option value="redelivery">补发货</option>
  <option value="polish_goods">一键擦亮</option>
  <option value="workflow">工作流</option>
</select>
```

- [ ] **Step 5: Re-run the frontend contract suite and build**

Run: `npm test`

Expected: PASS with the existing scripts plus the three new phase-1 contract scripts green.

Run: `npm run build`

Expected: PASS with the user web bundle compiling cleanly.

- [ ] **Step 6: Commit the frontend slice**

```bash
git add apps/user-web/src/api/orders.js \
        apps/user-web/src/api/autoDelivery.js \
        apps/user-web/src/api/scheduledTasks.js \
        apps/user-web/src/pages/OrdersPage.vue \
        apps/user-web/src/pages/AutoDeliveryPage.vue \
        apps/user-web/src/pages/DeliveryRecordsPage.vue \
        apps/user-web/src/pages/ScheduledTasksPage.vue \
        apps/user-web/scripts/orders-page-contract.test.mjs \
        apps/user-web/scripts/delivery-records-contract.test.mjs \
        apps/user-web/scripts/scheduled-tasks-contract.test.mjs \
        apps/user-web/package.json
git commit -m "feat: expose phase1 order and delivery controls in user web"
```

### Task 5: Verify The Closed Loop In Browser And Capture Evidence

**Files:**

- Create: `docs/superpowers/reports/2026-07-03-phase1-order-delivery-verification.md`

- [ ] **Step 1: Run the full phase-1 backend and frontend verification commands**

Run: `mvn test`

Expected: PASS with the new order, delivery, and scheduled-task tests included.

Run: `pytest tests/test_runtime_order_delivery_tasks.py tests/test_ws_delivery_handler.py -q`

Expected: PASS with zero failures.

Run: `npm test && npm run build`

Expected: PASS with zero contract failures and a successful Vite build.

- [ ] **Step 2: Start the local stack for browser verification**

Run: `powershell -ExecutionPolicy Bypass -File .\dev-start.ps1`

Expected: `core-api` on `http://localhost:18080`, `automation-service` on `http://localhost:12401`, and `user-web` on `http://localhost:5174`.

- [ ] **Step 3: Verify the phase-1 browser checklist**

```text
1. 打开 http://localhost:5174/#/orders，确认订单列表能看到真实订单号、买家、数量汇总、发货状态。
2. 打开某个包含多规格和多数量的订单详情，确认规格行显示“规格名: 规格值”，并能看到 quantitySent / quantityRequested。
3. 在订单详情里执行一次手动文本发货，确认页面出现成功提示，详情里的 deliveryStatus 和 deliveryMethod 实时更新。
4. 打开 http://localhost:5174/#/delivery-records，确认刚才的记录能看到 deliveryMode、deliveryTiming、失败原因或完成时间。
5. 对一条失败记录执行“重试”，确认记录状态发生变化而不是只弹提示。
6. 对一条失败记录创建“补发货”定时任务，确认 http://localhost:5174/#/scheduled-tasks 出现 redelivery 任务。
7. 创建 sync_orders 与 sync_delivery_status 任务并执行，确认任务结果会更新 lastRunTime，且订单页状态随之变化。
8. 打开 http://localhost:5174/#/auto-delivery，确认商品配置页能保存文本发货与卡密发货配置，并且扫描待发货订单后能生成新的 delivery_record。
```

- [ ] **Step 4: Write the verification evidence report**

```markdown
# Phase 1 Order And Delivery Verification

## Commands
- `mvn test`
- `pytest tests/test_runtime_order_delivery_tasks.py tests/test_ws_delivery_handler.py -q`
- `npm test`
- `npm run build`

## Browser Results
- Orders page:
- Delivery records page:
- Scheduled tasks page:
- Auto delivery page:

## Data Reality Check
- Real order data loaded:
- Real delivery record created:
- Real scheduled task executed:

## Remaining Gaps
- If any browser step fails, record the exact page route, API request path, response body, and whether the gap belongs to Java, Python, or Vue.
- If a feature only works with mock data, mark it as `部分完成` instead of `已完成`.
- If a task passes unit tests but does not update the browser state, add the missing page-state bug to the report before leaving phase 1.
```

- [ ] **Step 5: Commit the verification report**

```bash
git add docs/superpowers/reports/2026-07-03-phase1-order-delivery-verification.md
git commit -m "docs: capture phase1 order delivery verification evidence"
```

## Self-Review

**Spec coverage:** This plan covers the first-stage scope from the design spec: order management, manual delivery, automatic delivery, delivery-state sync, multi-spec display, multi-quantity delivery, delivery records, and scheduled redelivery/task support.

**Placeholder scan:** The plan intentionally avoids `TODO`, `TBD`, and “implement later” wording. Each task names concrete files, commands, and expected outcomes.

**Type consistency:** The naming is consistent across Java, Python, and frontend work:

- `deliveryTiming` / `delivery_timing`
- `deliveryMode` / `delivery_mode`
- `quantityRequested` / `quantity_requested`
- `quantitySent` / `quantity_sent`
- `sync_orders`, `sync_delivery_status`, `redelivery`

**Execution order:** Do not reorder these tasks. Task 1 establishes the read model, Task 2 adds command endpoints, Task 3 connects scheduled execution, Task 4 exposes the UI, and Task 5 proves the closed loop with fresh evidence.
