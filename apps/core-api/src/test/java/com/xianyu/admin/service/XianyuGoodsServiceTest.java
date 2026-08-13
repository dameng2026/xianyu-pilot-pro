package com.xianyu.admin.service;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.dto.DeleteResultVO;
import com.xianyu.admin.dto.XianyuGoodsDTO;
import com.xianyu.admin.dto.XianyuGoodsVO;
import com.xianyu.admin.entity.XianyuGoods;
import com.xianyu.admin.mapper.XianyuGoodsMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class XianyuGoodsServiceTest {

    @Mock
    private XianyuGoodsMapper goodsMapper;

    @Mock
    private XianyuGoodsDeleteService deleteService;

    @Mock
    private JdbcTemplate jdbcTemplate;

    private XianyuGoodsService goodsService;

    @BeforeEach
    void setUp() {
        goodsService = new XianyuGoodsService(goodsMapper, deleteService, jdbcTemplate);
    }

    @Test
    void testPage() {
        XianyuGoods goods = buildGoods();
        when(goodsMapper.count(anyLong(), any(), any(), any(), any(), any())).thenReturn(1);
        when(goodsMapper.list(anyLong(), any(), any(), any(), any(), any(), anyInt(), anyInt())).thenReturn(List.of(goods));
        when(jdbcTemplate.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());

        PageResult<XianyuGoodsVO> result = goodsService.page(100L, 10L, null, null, null, 1, 10);

        assertNotNull(result);
        assertEquals(1, result.getTotal());
        assertEquals(1, result.getRecords().size());

        XianyuGoodsVO vo = result.getRecords().get(0);
        assertEquals(1L, vo.getId());
        assertEquals("测试商品", vo.getTitle());
        assertEquals("99.00", vo.getSoldPrice());
        assertEquals("https://img.example.com/pic.jpg", vo.getCoverPic());
        assertEquals(10, vo.getQuantity());
        assertEquals(100, vo.getExposureCount());
        assertEquals(50, vo.getViewCount());
        assertEquals(5, vo.getWantCount());
        assertEquals("详情描述", vo.getDetailInfo());
        assertEquals(1, vo.getSortOrder());
        assertEquals(1, vo.getStatus());
    }

    @Test
    void testDetail() {
        XianyuGoods goods = buildGoods();
        goods.setTitle("商品详情");
        when(goodsMapper.findById(100L, 1L)).thenReturn(goods);

        when(jdbcTemplate.queryForObject(anyString(), eq(Integer.class), any())).thenReturn(2);
        XianyuGoodsVO vo = goodsService.detail(100L, 1L);

        assertNotNull(vo);
        assertEquals(2, vo.getSkuCount());
        assertEquals("商品详情", vo.getTitle());
    }

    @Test
    void testDetailNotFound() {
        when(goodsMapper.findById(100L, 999L)).thenReturn(null);
        assertThrows(Exception.class, () -> goodsService.detail(100L, 999L));
    }

    @Test
    void testCreate() {
        XianyuGoodsDTO dto = buildDto();
        when(goodsMapper.insert(any(XianyuGoods.class))).thenReturn(1);

        goodsService.create(100L, dto);

        verify(goodsMapper, times(1)).insert(any(XianyuGoods.class));
    }

    @Test
    void testUpdate() {
        XianyuGoods existing = buildGoods();
        existing.setTitle("旧标题");
        when(goodsMapper.findById(100L, 1L)).thenReturn(existing);
        when(goodsMapper.update(any(XianyuGoods.class))).thenReturn(1);

        XianyuGoodsDTO dto = new XianyuGoodsDTO();
        dto.setTitle("新标题");

        goodsService.update(100L, 1L, dto);

        verify(goodsMapper, times(1)).update(any(XianyuGoods.class));
    }

    @Test
    void testDelete() {
        when(deleteService.executeLocalDelete(100L, 200L, 1L, "127.0.0.1")).thenReturn(new DeleteResultVO());

        goodsService.delete(100L, 200L, 1L, "127.0.0.1");

        verify(deleteService, times(1)).executeLocalDelete(100L, 200L, 1L, "127.0.0.1");
    }

    private XianyuGoods buildGoods() {
        XianyuGoods goods = new XianyuGoods();
        goods.setId(1L);
        goods.setTenantId(100L);
        goods.setAccountId(10L);
        goods.setExternalGoodsId("12345");
        goods.setTitle("测试商品");
        goods.setPrice("99.00");
        goods.setSoldPrice("99.00");
        goods.setCoverPic("https://img.example.com/pic.jpg");
        goods.setImageUrl("https://img.example.com/pic.jpg");
        goods.setStock("10");
        goods.setQuantity(10);
        goods.setExposureCount(100);
        goods.setViewCount(50);
        goods.setWantCount(5);
        goods.setDetailUrl("https://goofish.com/item/12345");
        goods.setDetailInfo("详情描述");
        goods.setDescription("详情描述");
        goods.setCategory("数码");
        goods.setSortOrder(1);
        goods.setStatus(0);
        return goods;
    }

    private XianyuGoodsDTO buildDto() {
        XianyuGoodsDTO dto = new XianyuGoodsDTO();
        dto.setAccountId(10L);
        dto.setExternalGoodsId("12345");
        dto.setTitle("新商品");
        dto.setPrice("99.00");
        dto.setSoldPrice("99.00");
        dto.setCoverPic("https://img.example.com/pic.jpg");
        dto.setImageUrl("https://img.example.com/pic.jpg");
        dto.setStock("10");
        dto.setQuantity(10);
        dto.setExposureCount(100);
        dto.setViewCount(50);
        dto.setWantCount(5);
        dto.setDetailUrl("https://goofish.com/item/12345");
        dto.setDetailInfo("详情");
        dto.setDescription("详情");
        dto.setCategory("数码");
        dto.setSortOrder(1);
        dto.setStatus(0);
        return dto;
    }
}
