package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * 卡片项实体
 */
@Entity
@Table(name = "card_item")
public class CardItem extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "group_id")
    private Long groupId;

    @Column(name = "card_content", columnDefinition = "TEXT")
    private String cardContent;

    @Column(name = "card_key", columnDefinition = "TEXT")
    private String cardKey;

    @Column(name = "card_value", columnDefinition = "TEXT")
    private String cardValue;

    @Column(name = "extra_info", columnDefinition = "TEXT")
    private String extraInfo;

    /**
     * 状态：0未使用 1已使用 2禁用
     */
    @Column(name = "status")
    private Integer status;

    @Column(name = "used_order_id")
    private Long usedOrderId;

    @Column(name = "used_by_order_id")
    private Long usedByOrderId;

    @Column(name = "used_time")
    private LocalDateTime usedTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getGroupId() {
        return groupId;
    }

    public void setGroupId(Long groupId) {
        this.groupId = groupId;
    }

    public String getCardContent() {
        return cardContent;
    }

    public void setCardContent(String cardContent) {
        this.cardContent = cardContent;
    }

    public String getCardKey() {
        return cardKey;
    }

    public void setCardKey(String cardKey) {
        this.cardKey = cardKey;
    }

    public String getCardValue() {
        return cardValue;
    }

    public void setCardValue(String cardValue) {
        this.cardValue = cardValue;
    }

    public String getExtraInfo() {
        return extraInfo;
    }

    public void setExtraInfo(String extraInfo) {
        this.extraInfo = extraInfo;
    }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }

    public Long getUsedOrderId() {
        return usedOrderId;
    }

    public void setUsedOrderId(Long usedOrderId) {
        this.usedOrderId = usedOrderId;
    }

    public Long getUsedByOrderId() {
        return usedByOrderId;
    }

    public void setUsedByOrderId(Long usedByOrderId) {
        this.usedByOrderId = usedByOrderId;
    }

    public LocalDateTime getUsedTime() {
        return usedTime;
    }

    public void setUsedTime(LocalDateTime usedTime) {
        this.usedTime = usedTime;
    }
}
