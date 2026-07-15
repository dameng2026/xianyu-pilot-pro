package com.xianyu.admin.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.security.TenantContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 全店默认发货配置
 * 对应前端批量操作中的"全店统一配置"
 */
@RestController
@RequestMapping("/api/auto-delivery/global-config")
public class DeliveryGlobalConfigController {
    private static final Logger log = LoggerFactory.getLogger(DeliveryGlobalConfigController.class);

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    public DeliveryGlobalConfigController(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @GetMapping
    public Result<Map<String, Object>> get() {
        Long tenantId = requireTenant();
        try {
            Map<String, Object> row = jdbcTemplate.queryForMap(
                    "SELECT * FROM delivery_global_config WHERE tenant_id=? AND deleted=0 LIMIT 1", tenantId);
            return Result.ok(row);
        } catch (EmptyResultDataAccessException e) {
            return Result.ok(Map.of());
        } catch (Exception e) {
            log.error("查询全店发货配置失败, tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName());
            throw new BizException(503, "全店发货配置暂时无法加载，请稍后重试");
        }
    }

    @PutMapping
    public Result<Void> save(@RequestBody Map<String, Object> body) {
        Long tenantId = requireTenant();
        if (body == null) {
            throw new BizException(400, "配置内容不能为空");
        }

        String sql = "SELECT id FROM delivery_global_config WHERE tenant_id=? AND deleted=0 LIMIT 1";
        String configJson;
        try {
            configJson = objectMapper.writeValueAsString(body);
        } catch (JsonProcessingException | IllegalArgumentException e) {
            throw new BizException(400, "配置内容格式不正确");
        }

        Long id;
        try {
            id = jdbcTemplate.queryForObject(sql, Long.class, tenantId);
        } catch (EmptyResultDataAccessException e) {
            id = null;
        } catch (Exception e) {
            log.error("查询全店发货配置失败, tenantId={}, errorType={}", tenantId, e.getClass().getSimpleName());
            throw new BizException(503, "全店发货配置暂时无法保存，请稍后重试");
        }

        try {
            int affected;
            if (id == null) {
                affected = jdbcTemplate.update(
                        "INSERT INTO delivery_global_config(tenant_id, config_json, created_time, updated_time, deleted) VALUES(?,?,NOW(),NOW(),0)",
                        tenantId, configJson);
            } else {
                affected = jdbcTemplate.update(
                        "UPDATE delivery_global_config SET config_json=?, updated_time=NOW() WHERE id=? AND tenant_id=?",
                        configJson, id, tenantId);
            }
            if (affected != 1) {
                throw new BizException(503, "全店发货配置暂时无法保存，请稍后重试");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("保存全店发货配置失败, tenantId={}, configId={}, errorType={}", tenantId, id, e.getClass().getSimpleName());
            throw new BizException(503, "全店发货配置暂时无法保存，请稍后重试");
        }
        return Result.ok(null);
    }

    private Long requireTenant() {
        Long tenantId = TenantContext.getCurrentTenantId();
        if (tenantId == null) {
            throw new BizException(401, "登录状态已失效");
        }
        return tenantId;
    }
}
