package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import com.xianyu.admin.dto.MaintenanceStatusVO;

/**
 * 维护模式状态读取服务。
 * <p>状态存储于 Redis，由部署脚本（AI 遵循 .trae/rules/maintenance-mode-deployment.md）通过 redis-cli 切换：
 * <ul>
 *   <li>开启维护：SET xianyu:maintenance:enabled true</li>
 *   <li>关闭维护：DEL xianyu:maintenance:enabled xianyu:maintenance:message xianyu:maintenance:until</li>
 * </ul>
 * 降级策略：Redis 不可达时返回 enabled=false，绝不因基础设施故障锁死前台。
 */
@Service
public class MaintenanceService {

    private static final Logger log = LoggerFactory.getLogger(MaintenanceService.class);

    private static final String KEY_ENABLED = "xianyu:maintenance:enabled";
    private static final String KEY_MESSAGE = "xianyu:maintenance:message";
    private static final String KEY_UNTIL = "xianyu:maintenance:until";

    private final StringRedisTemplate redisTemplate;

    public MaintenanceService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /**
     * 读取当前维护状态。Redis 异常时降级为未维护。
     */
    public MaintenanceStatusVO getStatus() {
        try {
            String enabled = redisTemplate.opsForValue().get(KEY_ENABLED);
            boolean on = "true".equalsIgnoreCase(enabled);
            if (!on) {
                return new MaintenanceStatusVO(false, null, null);
            }
            String message = redisTemplate.opsForValue().get(KEY_MESSAGE);
            String until = redisTemplate.opsForValue().get(KEY_UNTIL);
            return new MaintenanceStatusVO(true, message, until);
        } catch (Exception e) {
            // Redis 不可达：宁可漏报维护，也不锁死用户
            log.warn("读取维护状态失败，降级为未维护: {}", e.getMessage());
            return new MaintenanceStatusVO(false, null, null);
        }
    }
}
