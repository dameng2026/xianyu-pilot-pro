package com.xianyu.admin.entity;

import jakarta.persistence.*;

import java.time.LocalDateTime;

/**
 * 发货声明会话实体
 * 按订单粒度跟踪"收到付款→发送声明→买家确认/取消→触发发货"全流程
 */
@Entity
@Table(name = "delivery_statement_session")
public class DeliveryStatementSession extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    /** 订单号（从 reminderUrl 提取的闲鱼订单号，字符串） */
    @Column(name = "order_id")
    private String orderId;

    @Column(name = "buyer_id")
    private String buyerId;

    @Column(name = "buyer_nick")
    private String buyerNick;

    @Column(name = "xy_goods_id")
    private String xyGoodsId;

    @Column(name = "goods_title")
    private String goodsTitle;

    @Column(name = "s_id")
    private String sId;

    @Column(name = "pnm_id")
    private String pnmId;

    @Column(name = "statement_content", columnDefinition = "TEXT")
    private String statementContent;

    @Column(name = "statement_msg_id")
    private String statementMsgId;

    /** 状态：declaring/waiting/confirmed/cancelled */
    @Column(name = "status")
    private String status;

    @Column(name = "sent_at")
    private LocalDateTime sentAt;

    @Column(name = "confirmed_at")
    private LocalDateTime confirmedAt;

    @Column(name = "cancelled_at")
    private LocalDateTime cancelledAt;

    /** 确认来源：buyer=买家回复/seller=卖家手动 */
    @Column(name = "confirm_source")
    private String confirmSource;

    /** 取消来源：buyer=买家回复/seller=卖家手动 */
    @Column(name = "cancel_source")
    private String cancelSource;

    @Column(name = "reply_msg_id")
    private String replyMsgId;

    @Column(name = "delivery_record_id")
    private Long deliveryRecordId;

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

    public String getOrderId() {
        return orderId;
    }

    public void setOrderId(String orderId) {
        this.orderId = orderId;
    }

    public String getBuyerId() {
        return buyerId;
    }

    public void setBuyerId(String buyerId) {
        this.buyerId = buyerId;
    }

    public String getBuyerNick() {
        return buyerNick;
    }

    public void setBuyerNick(String buyerNick) {
        this.buyerNick = buyerNick;
    }

    public String getXyGoodsId() {
        return xyGoodsId;
    }

    public void setXyGoodsId(String xyGoodsId) {
        this.xyGoodsId = xyGoodsId;
    }

    public String getGoodsTitle() {
        return goodsTitle;
    }

    public void setGoodsTitle(String goodsTitle) {
        this.goodsTitle = goodsTitle;
    }

    public String getSId() {
        return sId;
    }

    public void setSId(String sId) {
        this.sId = sId;
    }

    public String getPnmId() {
        return pnmId;
    }

    public void setPnmId(String pnmId) {
        this.pnmId = pnmId;
    }

    public String getStatementContent() {
        return statementContent;
    }

    public void setStatementContent(String statementContent) {
        this.statementContent = statementContent;
    }

    public String getStatementMsgId() {
        return statementMsgId;
    }

    public void setStatementMsgId(String statementMsgId) {
        this.statementMsgId = statementMsgId;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public LocalDateTime getSentAt() {
        return sentAt;
    }

    public void setSentAt(LocalDateTime sentAt) {
        this.sentAt = sentAt;
    }

    public LocalDateTime getConfirmedAt() {
        return confirmedAt;
    }

    public void setConfirmedAt(LocalDateTime confirmedAt) {
        this.confirmedAt = confirmedAt;
    }

    public LocalDateTime getCancelledAt() {
        return cancelledAt;
    }

    public void setCancelledAt(LocalDateTime cancelledAt) {
        this.cancelledAt = cancelledAt;
    }

    public String getConfirmSource() {
        return confirmSource;
    }

    public void setConfirmSource(String confirmSource) {
        this.confirmSource = confirmSource;
    }

    public String getCancelSource() {
        return cancelSource;
    }

    public void setCancelSource(String cancelSource) {
        this.cancelSource = cancelSource;
    }

    public String getReplyMsgId() {
        return replyMsgId;
    }

    public void setReplyMsgId(String replyMsgId) {
        this.replyMsgId = replyMsgId;
    }

    public Long getDeliveryRecordId() {
        return deliveryRecordId;
    }

    public void setDeliveryRecordId(Long deliveryRecordId) {
        this.deliveryRecordId = deliveryRecordId;
    }
}
