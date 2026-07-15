package com.xianyu.admin.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

public class OrderManualDeliveryRequest {
    @NotBlank
    private String deliveryMode;

    @NotBlank
    private String deliveryTiming;

    @NotBlank
    private String deliveryContent;

    @Min(1)
    private Integer quantityRequested = 1;

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
}
