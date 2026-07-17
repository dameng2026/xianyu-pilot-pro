package com.xianyu.admin.service;

import com.xianyu.admin.entity.DeliveryStatementSession;
import com.xianyu.admin.mapper.DeliveryStatementSessionMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * 发货声明拦截检查服务（轻量级，无对 DeliveryExecutionService 的依赖）
 *
 * 仅供 DeliveryExecutionService / DeliverySchedulerService 在发货前调用，
 * 判断"声明开关是否开启"以及"该订单是否已通过声明确认"。
 *
 * 注意：本服务不负责声明会话的生命周期管理（创建/确认/取消），
 * 那些逻辑在 DeliveryStatementSessionService 中。
 */
@Service
public class DeliveryStatementCheckService {
    private static final Logger log = LoggerFactory.getLogger(DeliveryStatementCheckService.class);

    private final JdbcTemplate jdbcTemplate;
    private final DeliveryStatementSessionMapper sessionMapper;

    public DeliveryStatementCheckService(JdbcTemplate jdbcTemplate,
                                         DeliveryStatementSessionMapper sessionMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.sessionMapper = sessionMapper;
    }

    /**
     * 判断指定租户的发货声明是否开启
     */
    public boolean isStatementEnabled(Long tenantId) {
        if (tenantId == null) {
            return false;
        }
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "SELECT COUNT(*) FROM delivery_statement WHERE tenant_id=? AND enabled=1 AND deleted=0",
                    Integer.class, tenantId);
            return count != null && count > 0;
        } catch (Exception e) {
            log.warn("查询发货声明开关失败 tenantId={} errorType={}",
                    tenantId, e.getClass().getSimpleName());
            return false;
        }
    }

    /**
     * 发货前置校验：声明开关开启时，必须存在该订单的 confirmed 会话才能发货
     *
     * @param tenantId         租户
     * @param accountId        账号
     * @param externalOrderId  闲鱼订单号
     * @return true=允许发货（声明关闭 或 已确认）；false=拦截发货（等待买家确认）
     */
    public boolean canDeliverAfterStatementCheck(Long tenantId, Long accountId, String externalOrderId) {
        if (!isStatementEnabled(tenantId)) {
            return true; // 声明关闭，按原流程发货
        }
        if (externalOrderId == null || externalOrderId.isBlank()) {
            log.info("声明开启但订单号缺失，拦截发货 tenantId={} accountId={}", tenantId, accountId);
            return false;
        }
        DeliveryStatementSession confirmed = sessionMapper.findConfirmedByOrder(tenantId, accountId, externalOrderId);
        if (confirmed != null) {
            return true;
        }
        log.info("声明开启且未确认，拦截发货 tenantId={} accountId={} orderId={}",
                tenantId, accountId, externalOrderId);
        return false;
    }
}
