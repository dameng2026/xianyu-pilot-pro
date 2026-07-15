package com.xianyu.admin.dto;

import jakarta.validation.constraints.NotBlank;

public class ScheduleRedeliveryRequest {
    @NotBlank
    private String cronExpression;

    public String getCronExpression() {
        return cronExpression;
    }

    public void setCronExpression(String cronExpression) {
        this.cronExpression = cronExpression;
    }
}
