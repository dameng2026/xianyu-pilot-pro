package com.xianyu.admin.dto;

import jakarta.validation.constraints.Min;

public class OrderManualDeliveryRequest {
    /**
     * 发货方式：text / card。
     * 当 sourceId 不为空时由后端根据货源推断，此字段可空。
     */
    private String deliveryMode;

    /**
     * 触发时机：after_payment / after_receipt / after_review
     */
    private String deliveryTiming;

    /**
     * 自定义发货内容。
     * 当 sourceId 不为空时由后端从货源库填充，此字段可空。
     */
    private String deliveryContent;

    /**
     * 发货数量，默认 1
     */
    @Min(1)
    private Integer quantityRequested = 1;

    /**
     * 货源库货源 ID（可选）。
     * 不为空时表示从货源库发货：
     *   - 货源为文本模式：用货源 content 直接发货
     *   - 货源为卡密模式：从货源绑定的卡密组认领一张卡密，应用货源 content 作为模板替换后发货，
     *     并将卡密标记为已使用
     * 为空时走原自定义发货内容逻辑，deliveryMode / deliveryContent 必填。
     */
    private Long sourceId;

    public String getDeliveryMode() {
        return deliveryMode;
    }

    public void setDeliveryMode(String deliveryMode) {
        this.deliveryMode = deliveryMode;
    }

    public String getDeliveryTiming() {
        return deliveryTiming;
    }

    public void setDeliveryTiming(String deliveryTiming) {
        this.deliveryTiming = deliveryTiming;
    }

    public String getDeliveryContent() {
        return deliveryContent;
    }

    public void setDeliveryContent(String deliveryContent) {
        this.deliveryContent = deliveryContent;
    }

    public Integer getQuantityRequested() {
        return quantityRequested;
    }

    public void setQuantityRequested(Integer quantityRequested) {
        this.quantityRequested = quantityRequested;
    }

    public Long getSourceId() {
        return sourceId;
    }

    public void setSourceId(Long sourceId) {
        this.sourceId = sourceId;
    }
}
