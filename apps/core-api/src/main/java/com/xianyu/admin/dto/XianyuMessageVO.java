package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 闲鱼消息VO
 */
public class XianyuMessageVO {
    private Long id;
    private Long conversationId;
    private String fromUserId;
    private String toUserId;
    private String content;
    private String messageType;
    private String direction;
    private Integer isAutoReply;
    private LocalDateTime createdTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getConversationId() { return conversationId; }
    public void setConversationId(Long conversationId) { this.conversationId = conversationId; }
    public String getFromUserId() { return fromUserId; }
    public void setFromUserId(String fromUserId) { this.fromUserId = fromUserId; }
    public String getToUserId() { return toUserId; }
    public void setToUserId(String toUserId) { this.toUserId = toUserId; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public String getMessageType() { return messageType; }
    public void setMessageType(String messageType) { this.messageType = messageType; }
    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
    public Integer getIsAutoReply() { return isAutoReply; }
    public void setIsAutoReply(Integer isAutoReply) { this.isAutoReply = isAutoReply; }
    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
}
