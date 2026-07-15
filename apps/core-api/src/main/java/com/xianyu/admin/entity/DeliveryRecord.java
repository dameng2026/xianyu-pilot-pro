package com.xianyu.admin.entity;

import jakarta.persistence.*;

import java.time.LocalDateTime;

/**
 * 发货记录实体
 */
@Entity
@Table(name = "delivery_record")
public class DeliveryRecord extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "order_id")
    private Long orderId;

    @Column(name = "rule_id")
    private Long ruleId;

    @Column(name = "delivery_type")
    private String deliveryType;

    @Column(name = "content", columnDefinition = "TEXT")
    private String content;

    /**
     * 状态：1成功 0失败
     */
    @Column(name = "status")
    private Integer status;

    @Column(name = "retry_count")
    private Integer retryCount;

    @Column(name = "fail_reason")
    private String failReason;

    @Column(name = "delivery_mode")
    private String deliveryMode;

    @Column(name = "delivery_method")
    private String deliveryMethod;

    @Column(name = "delivery_status")
    private String deliveryStatus;

    @Column(name = "delivery_content", columnDefinition = "TEXT")
    private String deliveryContent;

    @Column(name = "delivery_timing")
    private String deliveryTiming;

    @Column(name = "quantity_requested")
    private Integer quantityRequested;

    @Column(name = "quantity_sent")
    private Integer quantitySent;

    @Column(name = "platform_sync_time")
    private LocalDateTime platformSyncTime;

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

    public Long getOrderId() {
        return orderId;
    }

    public void setOrderId(Long orderId) {
        this.orderId = orderId;
    }

    public Long getRuleId() {
        return ruleId;
    }

    public void setRuleId(Long ruleId) {
        this.ruleId = ruleId;
    }

    public String getDeliveryType() {
        return deliveryType;
    }

    public void setDeliveryType(String deliveryType) {
        this.deliveryType = deliveryType;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }

    public Integer getRetryCount() {
        return retryCount;
    }

    public void setRetryCount(Integer retryCount) {
        this.retryCount = retryCount;
    }

    public String getFailReason() {
        return failReason;
    }

    public void setFailReason(String failReason) {
        this.failReason = failReason;
    }

    public String getDeliveryMode() {
        return deliveryMode;
    }

    public void setDeliveryMode(String deliveryMode) {
        this.deliveryMode = deliveryMode;
    }

    public String getDeliveryMethod() {
        return deliveryMethod;
    }

    public void setDeliveryMethod(String deliveryMethod) {
        this.deliveryMethod = deliveryMethod;
    }

    public String getDeliveryStatus() {
        return deliveryStatus;
    }

    public void setDeliveryStatus(String deliveryStatus) {
        this.deliveryStatus = deliveryStatus;
    }

    public String getDeliveryContent() {
        return deliveryContent;
    }

    public void setDeliveryContent(String deliveryContent) {
        this.deliveryContent = deliveryContent;
    }

    public String getDeliveryTiming() {
        return deliveryTiming;
    }

    public void setDeliveryTiming(String deliveryTiming) {
        this.deliveryTiming = deliveryTiming;
    }

    public Integer getQuantityRequested() {
        return quantityRequested;
    }

    public void setQuantityRequested(Integer quantityRequested) {
        this.quantityRequested = quantityRequested;
    }

    public Integer getQuantitySent() {
        return quantitySent;
    }

    public void setQuantitySent(Integer quantitySent) {
        this.quantitySent = quantitySent;
    }

    public LocalDateTime getPlatformSyncTime() {
        return platformSyncTime;
    }

    public void setPlatformSyncTime(LocalDateTime platformSyncTime) {
        this.platformSyncTime = platformSyncTime;
    }
}
