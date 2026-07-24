package com.xianyu.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class ApiSliderChargeReconcileJob {

    private static final Logger log = LoggerFactory.getLogger(ApiSliderChargeReconcileJob.class);

    private final ApiSliderSolveService solveService;

    public ApiSliderChargeReconcileJob(ApiSliderSolveService solveService) {
        this.solveService = solveService;
    }

    /**
     * 每 5 分钟扫描僵尸记录，回滚 pending_count，避免计数泄漏导致用户无法发起新请求。
     */
    @Scheduled(cron = "${xianyu.api-slider.reconcile-cron:0 */5 * * * ?}")
    public void reconcile() {
        try {
            solveService.reconcileStaleRecords();
        } catch (Exception e) {
            log.warn("api slider reconcile job failed", e);
        }
    }
}
