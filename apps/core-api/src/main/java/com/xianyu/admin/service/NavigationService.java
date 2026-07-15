package com.xianyu.admin.service;

import com.xianyu.admin.dto.*;
import com.xianyu.admin.entity.*;
import com.xianyu.admin.mapper.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class NavigationService {
    private static final Logger log = LoggerFactory.getLogger(NavigationService.class);

    private final XianyuAccountMapper accountMapper;
    private final XianyuGoodsMapper goodsMapper;
    private final XianyuTradeOrderMapper orderMapper;
    private final XianyuConversationMapper conversationMapper;
    private final DeliveryRecordMapper deliveryRecordMapper;
    private final NotificationMapper notificationMapper;
    private final SystemServiceStatusMapper systemServiceStatusMapper;

    public NavigationService(XianyuAccountMapper accountMapper,
                             XianyuGoodsMapper goodsMapper,
                             XianyuTradeOrderMapper orderMapper,
                             XianyuConversationMapper conversationMapper,
                             DeliveryRecordMapper deliveryRecordMapper,
                             NotificationMapper notificationMapper,
                             SystemServiceStatusMapper systemServiceStatusMapper) {
        this.accountMapper = accountMapper;
        this.goodsMapper = goodsMapper;
        this.orderMapper = orderMapper;
        this.conversationMapper = conversationMapper;
        this.deliveryRecordMapper = deliveryRecordMapper;
        this.notificationMapper = notificationMapper;
        this.systemServiceStatusMapper = systemServiceStatusMapper;
    }

    /**
     * 导航概览（顶部卡片）
     */
    public NavigationOverviewVO overview(Long tenantId) {
        NavigationOverviewVO vo = new NavigationOverviewVO();

        // 账号数
        vo.setAccountCount(accountMapper.countAll(tenantId));

        // 商品数
        vo.setGoodsCount(goodsMapper.countAll(tenantId));

        // 今日订单
        vo.setTodayOrderCount(orderMapper.countToday(tenantId));

        // 消息数（会话总数）
        vo.setMessageCount(conversationMapper.countAll(tenantId));

        // 待处理（待发货）
        vo.setPendingCount(deliveryRecordMapper.countPending(tenantId));

        return vo;
    }

    /**
     * 最近通知
     */
    public List<NotificationVO> recentNotifications(Long tenantId, int limit) {
        List<Notification> notifications = notificationMapper.listRecent(tenantId, limit);
        List<NotificationVO> result = new ArrayList<>();

        for (Notification n : notifications) {
            NotificationVO vo = new NotificationVO();
            vo.setId(n.getId());
            vo.setTitle(n.getTitle());
            vo.setContent(n.getContent());
            vo.setType(n.getType());
            vo.setStatus(n.getStatus());
            vo.setCreatedTime(n.getCreatedTime());
            result.add(vo);
        }

        return result;
    }

    /**
     * 系统状态
     */
    public List<SystemStatusVO> systemStatus() {
        List<SystemServiceStatus> nodes = systemServiceStatusMapper.listAll();
        List<SystemStatusVO> result = new ArrayList<>();

        for (SystemServiceStatus node : nodes) {
            SystemStatusVO vo = new SystemStatusVO();
            vo.setId(node.getId());
            vo.setNodeName(node.getNodeName());
            vo.setStatus(node.getStatus());
            vo.setCpu(node.getCpuUsage());
            vo.setMemory(node.getMemoryUsage());
            vo.setDisk(node.getDiskUsage());
            vo.setLastHeartbeat(node.getLastHeartbeatTime());
            result.add(vo);
        }

        return result;
    }
}
