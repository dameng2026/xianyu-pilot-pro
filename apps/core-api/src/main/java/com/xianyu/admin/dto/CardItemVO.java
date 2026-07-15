package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 卡片项VO
 */
public class CardItemVO {
    private Long id;
    private Long groupId;
    private String cardContent;
    private String content;
    private Integer status;
    private Long usedOrderId;
    private LocalDateTime usedTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getGroupId() { return groupId; }
    public void setGroupId(Long groupId) { this.groupId = groupId; }
    public String getCardContent() { return cardContent; }
    public void setCardContent(String cardContent) { this.cardContent = cardContent; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
    public Long getUsedOrderId() { return usedOrderId; }
    public void setUsedOrderId(Long usedOrderId) { this.usedOrderId = usedOrderId; }
    public LocalDateTime getUsedTime() { return usedTime; }
    public void setUsedTime(LocalDateTime usedTime) { this.usedTime = usedTime; }
}
