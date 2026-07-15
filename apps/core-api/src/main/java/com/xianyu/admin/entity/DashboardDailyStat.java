package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 仪表盘每日统计实体
 */
@Entity
@Table(name = "dashboard_daily_stat")
public class DashboardDailyStat extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "stat_date")
    private LocalDate statDate;

    @Column(name = "account_count")
    private Integer accountCount;

    @Column(name = "goods_count")
    private Integer goodsCount;

    @Column(name = "selling_goods_count")
    private Integer sellingGoodsCount;

    @Column(name = "order_count")
    private Integer orderCount;

    @Column(name = "order_amount")
    private BigDecimal orderAmount;

    @Column(name = "message_count")
    private Integer messageCount;

    @Column(name = "auto_reply_count")
    private Integer autoReplyCount;

    @Column(name = "delivery_success_count")
    private Integer deliverySuccessCount;

    @Column(name = "delivery_fail_count")
    private Integer deliveryFailCount;

    @Column(name = "ws_online_rate")
    private Double wsOnlineRate;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public LocalDate getStatDate() {
        return statDate;
    }

    public void setStatDate(LocalDate statDate) {
        this.statDate = statDate;
    }

    public Integer getAccountCount() {
        return accountCount;
    }

    public void setAccountCount(Integer accountCount) {
        this.accountCount = accountCount;
    }

    public Integer getGoodsCount() {
        return goodsCount;
    }

    public void setGoodsCount(Integer goodsCount) {
        this.goodsCount = goodsCount;
    }

    public Integer getSellingGoodsCount() {
        return sellingGoodsCount;
    }

    public void setSellingGoodsCount(Integer sellingGoodsCount) {
        this.sellingGoodsCount = sellingGoodsCount;
    }

    public Integer getOrderCount() {
        return orderCount;
    }

    public void setOrderCount(Integer orderCount) {
        this.orderCount = orderCount;
    }

    public BigDecimal getOrderAmount() {
        return orderAmount;
    }

    public void setOrderAmount(BigDecimal orderAmount) {
        this.orderAmount = orderAmount;
    }

    public Integer getMessageCount() {
        return messageCount;
    }

    public void setMessageCount(Integer messageCount) {
        this.messageCount = messageCount;
    }

    public Integer getAutoReplyCount() {
        return autoReplyCount;
    }

    public void setAutoReplyCount(Integer autoReplyCount) {
        this.autoReplyCount = autoReplyCount;
    }

    public Integer getDeliverySuccessCount() {
        return deliverySuccessCount;
    }

    public void setDeliverySuccessCount(Integer deliverySuccessCount) {
        this.deliverySuccessCount = deliverySuccessCount;
    }

    public Integer getDeliveryFailCount() {
        return deliveryFailCount;
    }

    public void setDeliveryFailCount(Integer deliveryFailCount) {
        this.deliveryFailCount = deliveryFailCount;
    }

    public Double getWsOnlineRate() {
        return wsOnlineRate;
    }

    public void setWsOnlineRate(Double wsOnlineRate) {
        this.wsOnlineRate = wsOnlineRate;
    }
}
