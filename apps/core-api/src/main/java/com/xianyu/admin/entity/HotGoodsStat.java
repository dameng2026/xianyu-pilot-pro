package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDate;

/**
 * 热销商品统计实体
 * 存储当日销量大于5件的商品数据，用于模型训练和爆款文案分析
 */
@Entity
@Table(name = "hot_goods_stat")
public class HotGoodsStat extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "goods_id")
    private Long goodsId;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "title")
    private String title;

    @Column(name = "price")
    private String price;

    @Column(name = "cover_pic", columnDefinition = "TEXT")
    private String coverPic;

    @Column(name = "daily_sales")
    private Integer dailySales;

    @Column(name = "stat_date")
    private LocalDate statDate;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getGoodsId() { return goodsId; }
    public void setGoodsId(Long goodsId) { this.goodsId = goodsId; }

    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getPrice() { return price; }
    public void setPrice(String price) { this.price = price; }

    public String getCoverPic() { return coverPic; }
    public void setCoverPic(String coverPic) { this.coverPic = coverPic; }

    public Integer getDailySales() { return dailySales; }
    public void setDailySales(Integer dailySales) { this.dailySales = dailySales; }

    public LocalDate getStatDate() { return statDate; }
    public void setStatDate(LocalDate statDate) { this.statDate = statDate; }
}