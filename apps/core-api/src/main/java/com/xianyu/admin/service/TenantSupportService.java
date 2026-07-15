package com.xianyu.admin.service;

import com.xianyu.admin.security.TenantContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class TenantSupportService {
    private static final Logger log = LoggerFactory.getLogger(TenantSupportService.class);

    private final JdbcTemplate jdbcTemplate;

    public TenantSupportService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Long resolveCurrentOrDefaultTenantId() {
        Long tenantId = TenantContext.getCurrentTenantId();
        return tenantId != null ? tenantId : findOrCreateDefaultTenantId();
    }

    public Long findOrCreateDefaultTenantId() {
        List<Map<String, Object>> tenants = jdbcTemplate.queryForList(
                "SELECT id FROM sys_tenant WHERE deleted=0 ORDER BY id ASC LIMIT 1");
        if (!tenants.isEmpty()) {
            return ((Number) tenants.get(0).get("id")).longValue();
        }

        jdbcTemplate.update(
                "INSERT INTO sys_tenant(tenant_name, name, display_name, status, created_time, updated_time, deleted) " +
                        "VALUES(?,?,?,1,NOW(),NOW(),0)",
                "default", "default", "Default Tenant");
        Long tenantId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        log.info("Created fallback tenant for content management: id={}", tenantId);
        return tenantId;
    }
}
