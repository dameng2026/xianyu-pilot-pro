package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 发货模板管理控制器
 * 对应前端 DeliveryTemplatesPage
 */
@RestController
@RequestMapping("/api/auto-delivery/templates")
public class DeliveryTemplateController {

    private final JdbcTemplate jdbcTemplate;

    public DeliveryTemplateController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /** 获取模板列表 */
    @GetMapping
    public Result<Map<String, Object>> list(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "100") int size,
            @RequestParam(required = false) String name) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Object[] countArgs = name != null ? new Object[]{tenantId, "%" + name + "%"} : new Object[]{tenantId};
        String countSql = "SELECT COUNT(*) FROM delivery_template WHERE tenant_id=? AND deleted=0" +
                (name != null ? " AND name LIKE ?" : "");
        Long total = jdbcTemplate.queryForObject(countSql, Long.class, countArgs);

        int offset = Math.max(0, (current - 1) * size);
        Object[] queryArgs;
        String querySql;
        if (name != null) {
            querySql = "SELECT * FROM delivery_template WHERE tenant_id=? AND deleted=0 AND name LIKE ? ORDER BY created_time DESC LIMIT ?,?";
            queryArgs = new Object[]{tenantId, "%" + name + "%", offset, size};
        } else {
            querySql = "SELECT * FROM delivery_template WHERE tenant_id=? AND deleted=0 ORDER BY created_time DESC LIMIT ?,?";
            queryArgs = new Object[]{tenantId, offset, size};
        }
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(querySql, queryArgs);
        return Result.ok(Map.of("records", rows, "total", total == null ? 0 : total, "current", current, "size", size));
    }

    /** 创建模板 */
    @PostMapping
    public Result<Void> create(@RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        String name = (String) body.get("name");
        Integer type = body.get("type") instanceof Number ? ((Number) body.get("type")).intValue() : 6;
        Integer status = body.get("status") instanceof Number ? ((Number) body.get("status")).intValue() : 1;
        String content = (String) body.getOrDefault("content", "");
        Object randomEnabled = body.getOrDefault("randomEnabled", false);

        jdbcTemplate.update(
                "INSERT INTO delivery_template(tenant_id, name, type, status, content, random_enabled, created_time, updated_time, deleted) VALUES(?,?,?,?,?,?,NOW(),NOW(),0)",
                tenantId, name, type, status, content, randomEnabled);
        return Result.ok(null);
    }

    /** 更新模板 */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        Long tenantId = TenantContext.getCurrentTenantId();
        String name = (String) body.get("name");
        Integer type = body.get("type") instanceof Number ? ((Number) body.get("type")).intValue() : null;
        Integer status = body.get("status") instanceof Number ? ((Number) body.get("status")).intValue() : null;
        String content = (String) body.get("content");
        Object randomEnabled = body.get("randomEnabled");

        StringBuilder sql = new StringBuilder("UPDATE delivery_template SET updated_time=NOW()");
        java.util.List<Object> args = new java.util.ArrayList<>();
        if (name != null) { sql.append(", name=?"); args.add(name); }
        if (type != null) { sql.append(", type=?"); args.add(type); }
        if (status != null) { sql.append(", status=?"); args.add(status); }
        if (content != null) { sql.append(", content=?"); args.add(content); }
        if (randomEnabled != null) { sql.append(", random_enabled=?"); args.add(randomEnabled); }

        sql.append(" WHERE id=? AND tenant_id=? AND deleted=0");
        args.add(id);
        args.add(tenantId);
        jdbcTemplate.update(sql.toString(), args.toArray());
        return Result.ok(null);
    }

    /** 删除模板 */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        jdbcTemplate.update("UPDATE delivery_template SET deleted=1, updated_time=NOW() WHERE id=? AND tenant_id=? AND deleted=0", id, tenantId);
        return Result.ok(null);
    }

    /** 复制模板 */
    @PostMapping("/{id}/copy")
    public Result<Void> copy(@PathVariable Long id) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Map<String, Object> src = jdbcTemplate.queryForMap(
                "SELECT * FROM delivery_template WHERE id=? AND tenant_id=? AND deleted=0", id, tenantId);
        if (src != null && !src.isEmpty()) {
            jdbcTemplate.update(
                    "INSERT INTO delivery_template(tenant_id, name, type, status, content, random_enabled, created_time, updated_time, deleted) VALUES(?,?,?,?,?,?,NOW(),NOW(),0)",
                    tenantId,
                    src.get("name") + " (副本)",
                    src.get("type"),
                    src.get("status"),
                    src.get("content"),
                    src.getOrDefault("random_enabled", false));
        }
        return Result.ok(null);
    }

    /** 获取可用变量列表 */
    @GetMapping("/variables")
    public Result<List<Map<String, String>>> variables() {
        List<Map<String, String>> vars = List.of(
                Map.of("key", "{买家昵称}", "desc", "买家在闲鱼的昵称"),
                Map.of("key", "{订单编号}", "desc", "订单编号"),
                Map.of("key", "{商品标题}", "desc", "商品标题"),
                Map.of("key", "{商品ID}", "desc", "商品ID"),
                Map.of("key", "{卡密}", "desc", "卡密内容"),
                Map.of("key", "{卡号}", "desc", "卡号（卡号+密码类型）"),
                Map.of("key", "{密码}", "desc", "密码（卡号+密码类型）"),
                Map.of("key", "{链接}", "desc", "链接/提取码"),
                Map.of("key", "{提取码}", "desc", "提取码"),
                Map.of("key", "{当前时间}", "desc", "发货时的系统时间"),
                Map.of("key", "{店铺名称}", "desc", "店铺名称"),
                Map.of("key", "{分段}", "desc", "将内容拆成多条消息依次发送")
        );
        return Result.ok(vars);
    }
}