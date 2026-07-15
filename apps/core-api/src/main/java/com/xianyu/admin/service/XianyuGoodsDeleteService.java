package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.DeleteResultVO;
import com.xianyu.admin.entity.OperationLog;
import com.xianyu.admin.entity.XianyuAccountAuth;
import com.xianyu.admin.entity.XianyuGoods;
import com.xianyu.admin.mapper.OperationLogMapper;
import com.xianyu.admin.mapper.XianyuAccountAuthMapper;
import com.xianyu.admin.mapper.XianyuGoodsMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 闲鱼商品删除服务 —— 编排完整的删除流程。
 * <p>
 * 删除流程：
 * 1. 校验商品是否存在
 * 2. 获取账号 Cookie
 * 3. 调用闲鱼平台删除 API（含重试机制）
 * 4. 从数据库彻底移除商品记录
 * 5. 记录操作日志
 * 6. 返回删除结果状态反馈
 * </p>
 */
@Service
public class XianyuGoodsDeleteService {

    private static final Logger log = LoggerFactory.getLogger(XianyuGoodsDeleteService.class);

    /** 最大重试次数 */
    private static final int MAX_RETRY = 3;

    /** 重试基础等待时间（毫秒） */
    private static final long BASE_RETRY_DELAY_MS = 1000;

    private final XianyuGoodsMapper goodsMapper;
    private final XianyuAccountAuthMapper authMapper;
    private final OperationLogMapper operationLogMapper;
    private final XianyuItemDeleteClient deleteClient;
    private final CookieCryptoService cookieCryptoService;

    public XianyuGoodsDeleteService(XianyuGoodsMapper goodsMapper,
                                     XianyuAccountAuthMapper authMapper,
                                     OperationLogMapper operationLogMapper,
                                     XianyuItemDeleteClient deleteClient,
                                     CookieCryptoService cookieCryptoService) {
        this.goodsMapper = goodsMapper;
        this.authMapper = authMapper;
        this.operationLogMapper = operationLogMapper;
        this.deleteClient = deleteClient;
        this.cookieCryptoService = cookieCryptoService;
    }

    /**
     * 兼容旧方法：执行远端删除。
     */
    @Transactional
    public DeleteResultVO executeDelete(Long tenantId, Long userId, Long id, String ipAddress) {
        return executeRemoteDelete(tenantId, userId, id, ipAddress);
    }

    /**
     * 仅删除本地商品记录，不调用闲鱼平台删除接口。
     */
    @Transactional
    public DeleteResultVO executeLocalDelete(Long tenantId, Long userId, Long id, String ipAddress) {
        XianyuGoods goods = goodsMapper.findById(tenantId, id);
        if (goods == null) {
            throw new BizException(404, "商品不存在");
        }
        int affected = goodsMapper.softDelete(tenantId, id);
        if (affected <= 0) {
            throw new BizException(404, "商品不存在或已删除");
        }
        Long logId = recordOperationLog(tenantId, userId, goods, "DELETE_LOCAL", false,
                0, null, ipAddress);
        DeleteResultVO result = DeleteResultVO.success(true, false);
        result.setOperationLogId(logId);
        return result;
    }

    /**
     * 执行远端商品删除流程：调用闲鱼平台删除 API，并在本地软删除保留审计痕迹。
     */
    @Transactional
    public DeleteResultVO executeRemoteDelete(Long tenantId, Long userId, Long id, String ipAddress) {
        XianyuGoods goods = goodsMapper.findById(tenantId, id);
        if (goods == null) {
            throw new BizException(404, "商品不存在");
        }

        String externalGoodsId = goods.getExternalGoodsId();
        Long accountId = goods.getAccountId();
        String cookie = getAccountCookie(tenantId, accountId);

        boolean platformDeleted = false;
        int retryCount = 0;
        String platformError = null;

        if (cookie != null && externalGoodsId != null && !externalGoodsId.isBlank()) {
            platformDeleted = deleteWithRetry(cookie, externalGoodsId);
            if (!platformDeleted) {
                retryCount = MAX_RETRY;
                platformError = "闲鱼平台删除失败，已达最大重试次数(" + MAX_RETRY + ")";
            }
        } else {
            platformError = cookie == null
                    ? "账号无有效Cookie，无法调用闲鱼删除接口"
                    : "商品缺少 externalGoodsId，无法调用闲鱼删除接口";
            log.warn("跳过闲鱼平台删除: id={}, reason={}", id, platformError);
        }

        goodsMapper.softDelete(tenantId, id);
        log.info("数据库商品已软删除: id={}, tenantId={}, platformDeleted={}", id, tenantId, platformDeleted);

        Long logId = recordOperationLog(tenantId, userId, goods, "DELETE_REMOTE", platformDeleted,
                retryCount, platformError, ipAddress);

        DeleteResultVO result = platformDeleted
                ? DeleteResultVO.success(true, true)
                : DeleteResultVO.partialSuccess(true, retryCount, platformError);
        result.setOperationLogId(logId);
        return result;
    }

    /**
     * 带重试机制的闲鱼平台删除调用。
     */
    private boolean deleteWithRetry(String cookie, String externalGoodsId) {
        for (int attempt = 1; attempt <= MAX_RETRY; attempt++) {
            log.info("调用闲鱼平台删除商品: externalGoodsId={}, 第{}次尝试", externalGoodsId, attempt);

            boolean success = deleteClient.deleteItem(cookie, externalGoodsId);
            if (success) {
                log.info("闲鱼平台删除商品成功: externalGoodsId={}, 尝试次数={}",
                        externalGoodsId, attempt);
                return true;
            }

            if (attempt < MAX_RETRY) {
                long delay = BASE_RETRY_DELAY_MS * (1L << (attempt - 1)); // 1s, 2s, 4s 指数退避
                log.warn("闲鱼平台删除商品失败，{}ms 后重试: externalGoodsId={}, 尝试次数={}",
                        delay, externalGoodsId, attempt);
                try {
                    Thread.sleep(delay);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    log.warn("重试等待被中断: externalGoodsId={}", externalGoodsId);
                    return false;
                }
            }
        }

        log.error("闲鱼平台删除商品最终失败: externalGoodsId={}, 已达最大重试次数({})",
                externalGoodsId, MAX_RETRY);
        return false;
    }

    /**
     * 获取账号的有效 Cookie。
     */
    private String getAccountCookie(Long tenantId, Long accountId) {
        if (accountId == null) return null;
        try {
            XianyuAccountAuth auth = authMapper.findByAccountId(tenantId, accountId);
            if (auth != null && auth.getEncryptedCookie() != null && !auth.getEncryptedCookie().isBlank()) {
                return cookieCryptoService.decryptIfNeeded(auth.getEncryptedCookie());
            }
        } catch (Exception e) {
            log.warn("获取账号Cookie失败: accountId={}, errorType={}", accountId, e.getClass().getSimpleName());
        }
        return null;
    }

    /**
     * 记录操作日志。
     */
    private Long recordOperationLog(Long tenantId, Long userId, XianyuGoods goods,
                                     boolean platformDeleted, int retryCount,
                                     String platformError, String ipAddress) {
        return recordOperationLog(tenantId, userId, goods, "DELETE_REMOTE", platformDeleted, retryCount, platformError, ipAddress);
    }

    private Long recordOperationLog(Long tenantId, Long userId, XianyuGoods goods,
                                     String operationType, boolean platformDeleted, int retryCount,
                                     String platformError, String ipAddress) {
        try {
            OperationLog opLog = new OperationLog();
            opLog.setTenantId(tenantId);
            opLog.setUserId(userId);
            opLog.setOperationType(operationType);
            opLog.setTargetType("xianyu_goods");
            opLog.setTargetId(goods.getId());
            opLog.setIpAddress(ipAddress);

            StringBuilder desc = new StringBuilder();
            desc.append("DELETE_LOCAL".equals(operationType) ? "仅删除本地商品: " : "远端删除商品: ").append(goods.getTitle());
            if (goods.getExternalGoodsId() != null) {
                desc.append(" (闲鱼ID: ").append(goods.getExternalGoodsId()).append(")");
            }
            desc.append(" | 本地标记删除: 成功");
            if ("DELETE_REMOTE".equals(operationType)) {
                desc.append(" | 平台删除: ").append(platformDeleted ? "成功" : "失败");
            }
            if (!platformDeleted && platformError != null) {
                desc.append(" (").append(platformError).append(")");
            }
            if (retryCount > 0) {
                desc.append(" | 重试次数: ").append(retryCount);
            }
            opLog.setOperationDesc(desc.toString());

            operationLogMapper.insert(opLog);
            log.info("操作日志已记录: logId={}, targetId={}", opLog.getId(), goods.getId());
            return opLog.getId();
        } catch (Exception e) {
            log.error("记录操作日志失败: targetId={}, errorType={}", goods.getId(), e.getClass().getSimpleName());
            return null;
        }
    }
}