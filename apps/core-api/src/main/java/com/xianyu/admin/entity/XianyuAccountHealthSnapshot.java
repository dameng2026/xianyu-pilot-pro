package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * 闲鱼账号健康快照实体
 */
@Entity
@Table(name = "xianyu_account_health_snapshot")
public class XianyuAccountHealthSnapshot extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "health_score")
    private Integer healthScore;

    @Column(name = "api_success_rate")
    private Double apiSuccessRate;

    @Column(name = "avg_response_ms")
    private Integer avgResponseMs;

    @Column(name = "ws_latency_ms")
    private Integer wsLatencyMs;

    @Column(name = "collected_time")
    private LocalDateTime collectedTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getAccountId() {
        return accountId;
    }

    public void setAccountId(Long accountId) {
        this.accountId = accountId;
    }

    public Integer getHealthScore() {
        return healthScore;
    }

    public void setHealthScore(Integer healthScore) {
        this.healthScore = healthScore;
    }

    public Double getApiSuccessRate() {
        return apiSuccessRate;
    }

    public void setApiSuccessRate(Double apiSuccessRate) {
        this.apiSuccessRate = apiSuccessRate;
    }

    public Integer getAvgResponseMs() {
        return avgResponseMs;
    }

    public void setAvgResponseMs(Integer avgResponseMs) {
        this.avgResponseMs = avgResponseMs;
    }

    public Integer getWsLatencyMs() {
        return wsLatencyMs;
    }

    public void setWsLatencyMs(Integer wsLatencyMs) {
        this.wsLatencyMs = wsLatencyMs;
    }

    public LocalDateTime getCollectedTime() {
        return collectedTime;
    }

    public void setCollectedTime(LocalDateTime collectedTime) {
        this.collectedTime = collectedTime;
    }
}
