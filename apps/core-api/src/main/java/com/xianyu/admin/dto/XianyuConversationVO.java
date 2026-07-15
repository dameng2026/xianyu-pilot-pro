package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 闲鱼会话VO
 */
public class XianyuConversationVO {
    private Long id;
    private Long accountId;
    private String externalBuyerId;
    private String buyerName;
    private String buyerAvatar;
    private String goodsTitle;
    private Integer status;
    private String statusText;
    private LocalDateTime lastMessageTime;
    private String lastMessageContent;
    private Integer unreadCount;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getExternalBuyerId() { return externalBuyerId; }
    public void setExternalBuyerId(String externalBuyerId) { this.externalBuyerId = externalBuyerId; }
    public String getBuyerName() { return buyerName; }
    public void setBuyerName(String buyerName) { this.buyerName = buyerName; }
    public String getBuyerAvatar() { return buyerAvatar; }
    public void setBuyerAvatar(String buyerAvatar) { this.buyerAvatar = buyerAvatar; }
    public String getGoodsTitle() { return goodsTitle; }
    public void setGoodsTitle(String goodsTitle) { this.goodsTitle = goodsTitle; }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
    public String getStatusText() { return statusText; }
    public void setStatusText(String statusText) { this.statusText = statusText; }
    public LocalDateTime getLastMessageTime() { return lastMessageTime; }
    public void setLastMessageTime(LocalDateTime lastMessageTime) { this.lastMessageTime = lastMessageTime; }
    public String getLastMessageContent() { return lastMessageContent; }
    public void setLastMessageContent(String lastMessageContent) { this.lastMessageContent = lastMessageContent; }
    public Integer getUnreadCount() { return unreadCount; }
    public void setUnreadCount(Integer unreadCount) { this.unreadCount = unreadCount; }
}
