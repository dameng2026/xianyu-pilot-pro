package com.xianyu.admin.dto;

/**
 * 通用模型按用户等级定价配置 DTO。
 * 用于管理端 GET/PUT /admin-api/ai-billing/tier-config 接口。
 * normal=普通用户(vip_level=0), vip=VIP(vip_level=1), svp=SVP(vip_level=2)
 */
public class TierPriceConfigDTO {
    private String moduleKey;
    private Long normal;  // 普通用户每次扣费 Token 数
    private Long vip;     // VIP 用户每次扣费 Token 数
    private Long svp;     // SVP 用户每次扣费 Token 数

    public String getModuleKey() { return moduleKey; }
    public void setModuleKey(String moduleKey) { this.moduleKey = moduleKey; }
    public Long getNormal() { return normal; }
    public void setNormal(Long normal) { this.normal = normal; }
    public Long getVip() { return vip; }
    public void setVip(Long vip) { this.vip = vip; }
    public Long getSvp() { return svp; }
    public void setSvp(Long svp) { this.svp = svp; }
}
