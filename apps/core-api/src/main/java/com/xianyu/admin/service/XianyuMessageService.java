package com.xianyu.admin.service;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.XianyuConversationVO;
import com.xianyu.admin.dto.XianyuMessageVO;
import com.xianyu.admin.entity.XianyuConversation;
import com.xianyu.admin.entity.XianyuMessage;
import com.xianyu.admin.mapper.XianyuConversationMapper;
import com.xianyu.admin.mapper.XianyuMessageMapper;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class XianyuMessageService {

    private final XianyuConversationMapper conversationMapper;
    private final XianyuMessageMapper messageMapper;
    private final OperationAuditService auditService;

    public XianyuMessageService(XianyuConversationMapper conversationMapper,
                                 XianyuMessageMapper messageMapper,
                                 OperationAuditService auditService) {
        this.conversationMapper = conversationMapper;
        this.messageMapper = messageMapper;
        this.auditService = auditService;
    }

    /**
     * 分页查询会话列表
     */
    public PageResult<XianyuConversationVO> conversations(Long tenantId, Long accountId, String keyword,
                                                            int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = conversationMapper.count(tenantId, accountId, keyword);
        List<XianyuConversation> list = conversationMapper.list(tenantId, accountId, keyword, offset, limit);

        List<XianyuConversationVO> records = new ArrayList<>();
        for (XianyuConversation c : list) {
            records.add(toConversationVO(c));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 分页查询会话消息列表
     */
    public PageResult<XianyuMessageVO> messages(Long tenantId, Long conversationId, int current, int size) {
        int safeCurrent = PageUtils.normalizeCurrent(current);
        int safeSize = PageUtils.normalizeSize(size);
        int offset = (safeCurrent - 1) * safeSize;
        int limit = safeSize;

        int total = messageMapper.countByConversationId(tenantId, conversationId);
        List<XianyuMessage> list = messageMapper.listByConversationId(tenantId, conversationId, offset, limit);

        List<XianyuMessageVO> records = new ArrayList<>();
        for (XianyuMessage m : list) {
            records.add(toMessageVO(m));
        }
        return new PageResult<>(records, safeCurrent, safeSize, total);
    }

    /**
     * 持久化会话状态。
     * status 约定：0=进行中, 1=已完成, 2=已关闭, 3=已转接。
     */
    public XianyuConversationVO updateConversationStatus(Long tenantId, Long userId, Long conversationId,
                                                         String action, String note, String ipAddress) {
        XianyuConversation conversation = conversationMapper.findById(tenantId, conversationId);
        if (conversation == null) {
            throw new BizException(404, "会话不存在");
        }
        int status = normalizeStatusAction(action);
        int clearUnread = status == 1 || status == 2 || status == 3 ? 1 : 0;
        int affected = conversationMapper.updateStatus(tenantId, conversationId, status, clearUnread);
        if (affected <= 0) {
            throw new BizException(404, "会话不存在或已删除");
        }
        String desc = statusText(status) + "会话: " + safe(conversation.getBuyerName(), conversation.getExternalBuyerId());
        if (note != null && !note.isBlank()) {
            desc += " | 备注: " + (note.length() > 200 ? note.substring(0, 200) : note);
        }
        auditService.record(tenantId, userId, "CONVERSATION_" + action.toUpperCase(), desc,
                "xianyu_conversation", conversationId, ipAddress);
        XianyuConversation updated = conversationMapper.findById(tenantId, conversationId);
        return toConversationVO(updated);
    }

    public XianyuConversationVO markRead(Long tenantId, Long userId, Long conversationId, String ipAddress) {
        XianyuConversation conversation = conversationMapper.findById(tenantId, conversationId);
        if (conversation == null) {
            throw new BizException(404, "会话不存在");
        }
        conversationMapper.markRead(tenantId, conversationId);
        auditService.record(tenantId, userId, "CONVERSATION_MARK_READ",
                "标记会话已读: " + safe(conversation.getBuyerName(), conversation.getExternalBuyerId()),
                "xianyu_conversation", conversationId, ipAddress);
        return toConversationVO(conversationMapper.findById(tenantId, conversationId));
    }

    private int normalizeStatusAction(String action) {
        String raw = action == null ? "" : action.trim().toLowerCase();
        return switch (raw) {
            case "in_progress", "progress", "reopen", "open" -> 0;
            case "complete", "completed", "end", "ended" -> 1;
            case "close", "closed" -> 2;
            case "transfer", "transferred" -> 3;
            default -> throw new BizException(400, "不支持的会话状态操作: " + action);
        };
    }

    private String statusText(Integer status) {
        if (status == null) return "未知";
        return switch (status) {
            case 0 -> "进行中";
            case 1 -> "已完成";
            case 2 -> "已关闭";
            case 3 -> "已转接";
            default -> "未知";
        };
    }

    private String safe(String primary, String fallback) {
        if (primary != null && !primary.isBlank()) return primary;
        return fallback != null && !fallback.isBlank() ? fallback : "未知买家";
    }

    private XianyuConversationVO toConversationVO(XianyuConversation c) {
        XianyuConversationVO vo = new XianyuConversationVO();
        vo.setId(c.getId());
        vo.setAccountId(c.getAccountId());
        vo.setExternalBuyerId(c.getExternalBuyerId());
        vo.setBuyerName(c.getBuyerName());
        vo.setBuyerAvatar(c.getBuyerAvatar());
        vo.setGoodsTitle(c.getGoodsTitle());
        vo.setStatus(c.getStatus());
        vo.setStatusText(statusText(c.getStatus()));
        vo.setLastMessageTime(c.getLastMessageTime());
        vo.setLastMessageContent(c.getLastMessageContent());
        vo.setUnreadCount(c.getUnreadCount());
        return vo;
    }

    private XianyuMessageVO toMessageVO(XianyuMessage m) {
        XianyuMessageVO vo = new XianyuMessageVO();
        vo.setId(m.getId());
        vo.setConversationId(m.getConversationId());
        vo.setFromUserId(m.getFromUserId());
        vo.setToUserId(m.getToUserId());
        vo.setContent(m.getContent());
        vo.setMessageType(m.getMessageType());
        vo.setDirection(m.getDirection());
        vo.setIsAutoReply(m.getIsAutoReply());
        vo.setCreatedTime(m.getCreatedTime());
        return vo;
    }
}
