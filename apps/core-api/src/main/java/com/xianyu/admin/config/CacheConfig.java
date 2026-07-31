package com.xianyu.admin.config;

import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import java.util.concurrent.TimeUnit;

/**
 * 应用层本地缓存配置（基于 Caffeine）。
 *
 * 设计原则：
 * 1. 仅缓存「读多写极少」的全局公共配置/数据（交易配置、系统配置、功能开关、AI 计费档位、模型配置、数据保留配置、商城公共数据等）。
 * 2. 不缓存含用户态/租户态的数据（避免跨用户越权风险），用户维度的配置走 BusinessSettingsService 不接入本地缓存。
 * 3. 不缓存敏感字段解密后的结果（如邮件密码、SecretKey），相关 Service 显式不使用 @Cacheable。
 * 4. TTL 较短（5 分钟），即使后台直接改库也能很快收敛；写操作通过 @CacheEvict 即时失效。
 *
 * 缓存清单：
 * - tradeConfig        交易配置（抽佣率、冷冻期等）        TTL 5min  容量 256
 * - systemConfig       系统配置（站点名/LOGO/备案号）      TTL 5min  容量 256
 * - featureSwitches    功能开关列表                        TTL 5min  容量 256
 * - tierConfig         AI 模型三档定价                      TTL 5min  容量 256
 * - modelConfig        AI 模型配置（含生图模型列表）        TTL 5min  容量 256
 * - dataRetention      数据保留配置                        TTL 5min  容量 256
 * - mallPublic         商城公共数据（FAQ/分类/分类树）      TTL 5min  容量 256
 */
@Configuration
public class CacheConfig {

    /**
     * 默认缓存：TTL 5 分钟，最大 256 条。
     * 适合频繁访问的配置类与公共数据。
     */
    @Bean
    @Primary
    public CacheManager cacheManager() {
        CaffeineCacheManager manager = new CaffeineCacheManager(
                "tradeConfig",
                "systemConfig",
                "featureSwitches",
                "tierConfig",
                "modelConfig",
                "dataRetention",
                "mallPublic"
        );
        manager.setCaffeine(Caffeine.newBuilder()
                .expireAfterWrite(5, TimeUnit.MINUTES)
                .maximumSize(256)
                .recordStats());
        // 不缓存 null 值，避免缓存穿透时存入空占位
        manager.setAllowNullValues(false);
        return manager;
    }
}
