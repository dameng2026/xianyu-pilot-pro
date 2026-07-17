package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.Map;

/**
 * 货源商城商品 AI 分类定时调度器。
 * 每日凌晨 3 点扫描所有 category 为空或需要重新分类的商品，
 * 调用 automation-service 的 /api/v1/mall/categorize 接口进行 AI 分类，
 * 并更新商品的 category 和 ai_category_confidence 字段。
 */
@Service
public class MallCategoryScheduler {
    private static final Logger log = LoggerFactory.getLogger(MallCategoryScheduler.class);

    private final MallProductService mallProductService;

    public MallCategoryScheduler(MallProductService mallProductService) {
        this.mallProductService = mallProductService;
    }

    /**
     * 每日凌晨 3 点执行 AI 分类刷新。
     * cron 表达式：秒 分 时 日 月 周
     * 0 0 3 * * * = 每天 03:00:00 执行
     */
    @Scheduled(cron = "0 0 3 * * *")
    public void refreshCategoriesDaily() {
        try {
            Map<String, Object> result = mallProductService.refreshCategories();
            Object total = result.get("total");
            Object updated = result.get("updated");
            Object failed = result.get("failed");
            log.info("商城商品 AI 分类定时任务完成: total={}, updated={}, failed={}", total, updated, failed);
        } catch (Exception e) {
            log.error("商城商品 AI 分类定时任务异常, errorType={}", e.getClass().getSimpleName());
        }
    }
}
