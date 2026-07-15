package com.xianyu.admin.dto;

/**
 * 账号健康VO
 */
public class AccountHealthVO {

    private Long accountId;
    private String nickname;
    private Integer healthScore;
    private Integer status;

    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }

    public String getNickname() { return nickname != null ? nickname : ""; }
    public void setNickname(String nickname) { this.nickname = nickname; }

    public Integer getHealthScore() { return healthScore != null ? healthScore : 0; }
    public void setHealthScore(Integer healthScore) { this.healthScore = healthScore; }

    public Integer getStatus() { return status != null ? status : 0; }
    public void setStatus(Integer status) { this.status = status; }
}
