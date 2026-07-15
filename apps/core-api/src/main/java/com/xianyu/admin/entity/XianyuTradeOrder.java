package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 闲鱼交易订单实体
 */
@Entity
@Table(name = "xianyu_trade_order")
public class XianyuTradeOrder extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "external_order_id")
    private String externalOrderId;

    /**
     * 订单状态：0待付款 1已付款 2待发货 3已发货 4已完成 5已关闭
     */
    @Column(name = "order_status")
    private Integer orderStatus;

    @Column(name = "total_amount")
    private BigDecimal totalAmount;

    @Column(name = "buyer_name")
    private String buyerName;

    @Column(name = "buyer_id")
    private String buyerId;

    @Column(name = "create_time")
    private LocalDateTime createTime;

    @Column(name = "pay_time")
    private LocalDateTime payTime;

    @Column(name = "ship_time")
    private LocalDateTime shipTime;

    @Column(name = "confirm_time")
    private LocalDateTime confirmTime;

    @Column(name = "buyer_message", columnDefinition = "TEXT")
    private String buyerMessage;

    @Column(name = "item_id")
    private String itemId;

    @Column(name = "is_bargain")
    private Boolean isBargain;

    @Column(name = "is_rated")
    private Boolean isRated;

    @Column(name = "is_red_flower")
    private Boolean isRedFlower;

    /**
     * 发货状态（数据库表可能无此字段，已废弃，改用 delivery_record 表统计）
     */
    @Transient
    private Integer deliveryStatus;

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

    public String getExternalOrderId() {
        return externalOrderId;
    }

    public void setExternalOrderId(String externalOrderId) {
        this.externalOrderId = externalOrderId;
    }

    public Integer getOrderStatus() {
        return orderStatus;
    }

    public void setOrderStatus(Integer orderStatus) {
        this.orderStatus = orderStatus;
    }

    public BigDecimal getTotalAmount() {
        return totalAmount;
    }

    public void setTotalAmount(BigDecimal totalAmount) {
        this.totalAmount = totalAmount;
    }

    public String getBuyerName() {
        return buyerName;
    }

    public void setBuyerName(String buyerName) {
        this.buyerName = buyerName;
    }

    public String getBuyerId() {
        return buyerId;
    }

    public void setBuyerId(String buyerId) {
        this.buyerId = buyerId;
    }

    public LocalDateTime getCreateTime() {
        return createTime;
    }

    public void setCreateTime(LocalDateTime createTime) {
        this.createTime = createTime;
    }

    public LocalDateTime getPayTime() {
        return payTime;
    }

    public void setPayTime(LocalDateTime payTime) {
        this.payTime = payTime;
    }

    public LocalDateTime getShipTime() {
        return shipTime;
    }

    public void setShipTime(LocalDateTime shipTime) {
        this.shipTime = shipTime;
    }

    public LocalDateTime getConfirmTime() {
        return confirmTime;
    }

    public void setConfirmTime(LocalDateTime confirmTime) {
        this.confirmTime = confirmTime;
    }

    public String getBuyerMessage() {
        return buyerMessage;
    }

    public void setBuyerMessage(String buyerMessage) {
        this.buyerMessage = buyerMessage;
    }

    public String getItemId() {
        return itemId;
    }

    public void setItemId(String itemId) {
        this.itemId = itemId;
    }

    public Boolean getIsBargain() {
        return isBargain;
    }

    public void setIsBargain(Boolean isBargain) {
        this.isBargain = isBargain;
    }

    public Boolean getIsRated() {
        return isRated;
    }

    public void setIsRated(Boolean isRated) {
        this.isRated = isRated;
    }

    public Boolean getIsRedFlower() {
        return isRedFlower;
    }

    public void setIsRedFlower(Boolean isRedFlower) {
        this.isRedFlower = isRedFlower;
    }

    public Integer getDeliveryStatus() {
        return deliveryStatus;
    }

    public void setDeliveryStatus(Integer deliveryStatus) {
        this.deliveryStatus = deliveryStatus;
    }
}
