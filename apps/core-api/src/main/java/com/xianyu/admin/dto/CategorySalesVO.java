package com.xianyu.admin.dto;

/**
 * 类目销售统计VO
 */
public class CategorySalesVO {

    private String categoryName;
    private Integer goodsCount;
    private Integer salesCount;

    public String getCategoryName() { return categoryName != null ? categoryName : "未分类"; }
    public void setCategoryName(String categoryName) { this.categoryName = categoryName; }

    public Integer getGoodsCount() { return goodsCount != null ? goodsCount : 0; }
    public void setGoodsCount(Integer goodsCount) { this.goodsCount = goodsCount; }

    public Integer getSalesCount() { return salesCount != null ? salesCount : 0; }
    public void setSalesCount(Integer salesCount) { this.salesCount = salesCount; }
}
