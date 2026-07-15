package com.xianyu.admin.entity;

import jakarta.persistence.*;

/**
 * 闲鱼消息实体
 */
@Entity
@Table(name = "xianyu_message")
public class XianyuMessage extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "conversation_id")
    private Long conversationId;

    @Column(name = "from_user_id")
    private String fromUserId;

    @Column(name = "to_user_id")
    private String toUserId;

    @Column(name = "content", columnDefinition = "TEXT")
    private String content;

    /**
     * 消息类型：text/image/card
     */
    @Column(name = "message_type")
    private String messageType;

    /**
     * 方向：sent/received
     */
    @Column(name = "direction")
    private String direction;

    /**
     * 是否自动回复：0否 1是
     */
    @Column(name = "is_auto_reply")
    private Integer isAutoReply;

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

    public Long getConversationId() {
        return conversationId;
    }

    public void setConversationId(Long conversationId) {
        this.conversationId = conversationId;
    }

    public String getFromUserId() {
        return fromUserId;
    }

    public void setFromUserId(String fromUserId) {
        this.fromUserId = fromUserId;
    }

    public String getToUserId() {
        return toUserId;
    }

    public void setToUserId(String toUserId) {
        this.toUserId = toUserId;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public String getMessageType() {
        return messageType;
    }

    public void setMessageType(String messageType) {
        this.messageType = messageType;
    }

    public String getDirection() {
        return direction;
    }

    public void setDirection(String direction) {
        this.direction = direction;
    }

    public Integer getIsAutoReply() {
        return isAutoReply;
    }

    public void setIsAutoReply(Integer isAutoReply) {
        this.isAutoReply = isAutoReply;
    }
}
