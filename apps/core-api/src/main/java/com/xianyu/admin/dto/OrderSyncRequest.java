package com.xianyu.admin.dto;

public class OrderSyncRequest {
    private Long accountId;
    private String externalOrderId;
    private Boolean syncDeliveryStatus = Boolean.TRUE;

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

    public Boolean getSyncDeliveryStatus() {
        return syncDeliveryStatus;
    }

    public void setSyncDeliveryStatus(Boolean syncDeliveryStatus) {
        this.syncDeliveryStatus = syncDeliveryStatus;
    }
}
