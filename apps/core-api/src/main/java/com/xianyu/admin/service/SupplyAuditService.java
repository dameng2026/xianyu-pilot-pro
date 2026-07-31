package com.xianyu.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.xianyu.admin.security.AdminContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

/**
 * 供货商品审核服务
 * 提交审核 / 通过 / 驳回 / 历史查询
 */
@Service
public class SupplyAuditService {

    private final JdbcTemplate jdbcTemplate;
    private final TradeNotifyService notifyService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SupplyAuditService(JdbcTemplate jdbcTemplate, TradeNotifyService notifyService) {
        this.jdbcTemplate = jdbcTemplate;
        this.notifyService = notifyService;
    }

    /**
     * 提交审核
     */
    @Transactional
    public void submitForAudit(String moduleKey, Long businessId, Long submitterId,
                                Long tenantId, Map<String, Object> snapshot) {
        try {
            String snapshotJson = objectMapper.writeValueAsString(snapshot);
            jdbcTemplate.update(
                "INSERT INTO audit_record(tenant_id, module_key, business_id, submitter_id, " +
                "status, snapshot_json, submitted_at) VALUES(?, ?, ?, ?, 'pending', ?, NOW())",
                tenantId, moduleKey, businessId, submitterId, snapshotJson);
        } catch (Exception e) {
            throw new RuntimeException("提交审核失败: " + e.getMessage());
        }
    }

    /**
     * 待审核列表（后台）
     */
    public Map<String, Object> pendingList(int page, int size, String moduleKey) {
        int offset = (page - 1) * size;
        StringBuilder where = new StringBuilder("WHERE a.status = 'pending'");
        List<Object> params = new ArrayList<>();
        if (moduleKey != null && !moduleKey.isEmpty()) {
            where.append(" AND a.module_key = ?");
            params.add(moduleKey);
        }

        Integer total = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM audit_record a " + where, Integer.class, params.toArray());

        List<Object> listParams = new ArrayList<>(params);
        listParams.add(size);
        listParams.add(offset);

        List<Map<String, Object>> list = jdbcTemplate.queryForList(
            "SELECT a.*, u.username as submitter_name " +
            "FROM audit_record a LEFT JOIN sys_user u ON a.submitter_id = u.id " +
            where + " ORDER BY a.submitted_at ASC LIMIT ? OFFSET ?",
            listParams.toArray());

        // 供货商品审核补充商品标题
        for (Map<String, Object> item : list) {
            if ("supply_product".equals(item.get("module_key"))) {
                Long businessId = ((Number) item.get("business_id")).longValue();
                List<Map<String, Object>> products = jdbcTemplate.queryForList(
                    "SELECT title, cover_url, price_cent, product_type, seller_id FROM supply_product WHERE id = ?",
                    businessId);
                if (!products.isEmpty()) {
                    item.put("productInfo", products.get(0));
                }
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("total", total);
        result.put("list", list);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    /**
     * 审核通过
     */
    @Transactional
    public Map<String, Object> approve(Long auditId, String reason) {
        Long auditorId = AdminContext.userId();

        Map<String, Object> audit = getAuditRecord(auditId);
        String moduleKey = (String) audit.get("module_key");
        Long businessId = ((Number) audit.get("business_id")).longValue();
        Long submitterId = ((Number) audit.get("submitter_id")).longValue();

        // 更新审核记录
        jdbcTemplate.update(
            "UPDATE audit_record SET status = 'approved', auditor_id = ?, reason = ?, audited_at = NOW() " +
            "WHERE id = ? AND status = 'pending'",
            auditorId, reason != null ? reason : "", auditId);

        // 更新业务表状态
        if ("supply_product".equals(moduleKey)) {
            jdbcTemplate.update(
                "UPDATE supply_product SET audit_status = 'approved', audit_at = NOW(), auditor_id = ? WHERE id = ?",
                auditorId, businessId);
        }

        // 通知供货商
        notifyService.notifyAuditApproved(submitterId, businessId, moduleKey);

        Map<String, Object> result = new HashMap<>();
        result.put("message", "审核通过");
        return result;
    }

    /**
     * 审核驳回
     */
    @Transactional
    public Map<String, Object> reject(Long auditId, String reason) {
        Long auditorId = AdminContext.userId();

        Map<String, Object> audit = getAuditRecord(auditId);
        String moduleKey = (String) audit.get("module_key");
        Long businessId = ((Number) audit.get("business_id")).longValue();
        Long submitterId = ((Number) audit.get("submitter_id")).longValue();

        // 更新审核记录
        jdbcTemplate.update(
            "UPDATE audit_record SET status = 'rejected', auditor_id = ?, reason = ?, audited_at = NOW() " +
            "WHERE id = ? AND status = 'pending'",
            auditorId, reason, auditId);

        // 更新业务表状态
        if ("supply_product".equals(moduleKey)) {
            jdbcTemplate.update(
                "UPDATE supply_product SET audit_status = 'rejected', audit_reason = ?, audit_at = NOW(), auditor_id = ? WHERE id = ?",
                reason, auditorId, businessId);
        }

        // 通知供货商
        notifyService.notifyAuditRejected(submitterId, businessId, moduleKey, reason);

        Map<String, Object> result = new HashMap<>();
        result.put("message", "已驳回");
        return result;
    }

    /**
     * 审核历史
     */
    public Map<String, Object> history(int page, int size, String moduleKey, String status) {
        int offset = (page - 1) * size;
        StringBuilder where = new StringBuilder("WHERE 1=1");
        List<Object> params = new ArrayList<>();
        if (moduleKey != null && !moduleKey.isEmpty()) {
            where.append(" AND module_key = ?");
            params.add(moduleKey);
        }
        if (status != null && !status.isEmpty()) {
            where.append(" AND status = ?");
            params.add(status);
        }

        Integer total = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM audit_record " + where, Integer.class, params.toArray());

        List<Object> listParams = new ArrayList<>(params);
        listParams.add(size);
        listParams.add(offset);

        List<Map<String, Object>> list = jdbcTemplate.queryForList(
            "SELECT a.*, u.username as submitter_name, au.username as auditor_name " +
            "FROM audit_record a " +
            "LEFT JOIN sys_user u ON a.submitter_id = u.id " +
            "LEFT JOIN sys_admin_user au ON a.auditor_id = au.id " +
            where + " ORDER BY a.submitted_at DESC LIMIT ? OFFSET ?",
            listParams.toArray());

        Map<String, Object> result = new HashMap<>();
        result.put("total", total);
        result.put("list", list);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    private Map<String, Object> getAuditRecord(Long auditId) {
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
            "SELECT * FROM audit_record WHERE id = ?", auditId);
        if (records.isEmpty()) {
            throw new RuntimeException("审核记录不存在");
        }
        return records.get(0);
    }
}
