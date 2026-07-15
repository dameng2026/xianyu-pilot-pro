package com.xianyu.admin.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public class XianyuAccountDTO {

    @NotBlank(message = "externalUid不能为空")
    private String externalUid;

    private String nickname;

    private String avatarUrl;

    private String province;

    private String city;

    private Integer accountLevel;

    private String remark;

    private Integer status;

    public String getExternalUid() { return externalUid; }
    public void setExternalUid(String externalUid) { this.externalUid = externalUid; }

    public String getNickname() { return nickname; }
    public void setNickname(String nickname) { this.nickname = nickname; }

    public String getAvatarUrl() { return avatarUrl; }
    public void setAvatarUrl(String avatarUrl) { this.avatarUrl = avatarUrl; }

    public String getProvince() { return province; }
    public void setProvince(String province) { this.province = province; }

    public String getCity() { return city; }
    public void setCity(String city) { this.city = city; }

    public Integer getAccountLevel() { return accountLevel; }
    public void setAccountLevel(Integer accountLevel) { this.accountLevel = accountLevel; }

    public String getRemark() { return remark; }
    public void setRemark(String remark) { this.remark = remark; }

    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
}
