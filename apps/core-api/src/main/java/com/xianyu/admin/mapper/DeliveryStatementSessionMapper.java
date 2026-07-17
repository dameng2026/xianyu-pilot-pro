package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.DeliveryStatementSession;
import org.apache.ibatis.annotations.*;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 发货声明会话 Mapper
 */
@Mapper
public interface DeliveryStatementSessionMapper {

    @Insert("INSERT INTO delivery_statement_session(" +
            "tenant_id, account_id, order_id, buyer_id, buyer_nick, xy_goods_id, goods_title, " +
            "s_id, pnm_id, statement_content, statement_msg_id, status, sent_at, " +
            "created_time, updated_time, deleted" +
            ") VALUES(" +
            "#{tenantId}, #{accountId}, #{orderId}, #{buyerId}, #{buyerNick}, #{xyGoodsId}, #{goodsTitle}, " +
            "#{sId}, #{pnmId}, #{statementContent}, #{statementMsgId}, #{status}, #{sentAt}, " +
            "NOW(), NOW(), 0)")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(DeliveryStatementSession session);

    @Select("SELECT * FROM delivery_statement_session WHERE id=#{id} AND tenant_id=#{tenantId} AND deleted=0")
    DeliveryStatementSession findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("<script>" +
            "SELECT * FROM delivery_statement_session " +
            "WHERE tenant_id=#{tenantId} AND deleted=0 " +
            "<if test='status != null and status != \"\"'>AND status=#{status}</if> " +
            "<if test='accountId != null'>AND account_id=#{accountId}</if> " +
            "ORDER BY created_time DESC LIMIT #{offset}, #{limit}" +
            "</script>")
    List<DeliveryStatementSession> list(@Param("tenantId") Long tenantId,
                                        @Param("accountId") Long accountId,
                                        @Param("status") String status,
                                        @Param("offset") int offset,
                                        @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM delivery_statement_session " +
            "WHERE tenant_id=#{tenantId} AND deleted=0 " +
            "<if test='status != null and status != \"\"'>AND status=#{status}</if> " +
            "<if test='accountId != null'>AND account_id=#{accountId}</if>" +
            "</script>")
    int count(@Param("tenantId") Long tenantId,
              @Param("accountId") Long accountId,
              @Param("status") String status);

    /**
     * 按 会话+状态 查询（用于买家回复"确认/取消"时定位 waiting 会话）
     */
    @Select("SELECT * FROM delivery_statement_session " +
            "WHERE tenant_id=#{tenantId} AND account_id=#{accountId} " +
            "AND s_id=#{sId} AND status=#{status} AND deleted=0 " +
            "ORDER BY created_time ASC LIMIT 1")
    DeliveryStatementSession findBySessionAndStatus(@Param("tenantId") Long tenantId,
                                                     @Param("accountId") Long accountId,
                                                     @Param("sId") String sId,
                                                     @Param("status") String status);

    /**
     * 按 订单 查询非终态会话（declaring/waiting）
     * 用于幂等：同一订单已有未完成声明会话时不重复创建
     */
    @Select("SELECT * FROM delivery_statement_session " +
            "WHERE tenant_id=#{tenantId} AND account_id=#{accountId} " +
            "AND order_id=#{orderId} AND status IN ('declaring','waiting') AND deleted=0 " +
            "ORDER BY created_time DESC LIMIT 1")
    DeliveryStatementSession findActiveByOrder(@Param("tenantId") Long tenantId,
                                                @Param("accountId") Long accountId,
                                                @Param("orderId") String orderId);

    /**
     * 按 订单 查询已确认会话（用于 executeDelivery 前置校验：声明开关开时必须有 confirmed 会话）
     */
    @Select("SELECT * FROM delivery_statement_session " +
            "WHERE tenant_id=#{tenantId} AND account_id=#{accountId} " +
            "AND order_id=#{orderId} AND status='confirmed' AND deleted=0 " +
            "ORDER BY confirmed_at DESC LIMIT 1")
    DeliveryStatementSession findConfirmedByOrder(@Param("tenantId") Long tenantId,
                                                   @Param("accountId") Long accountId,
                                                   @Param("orderId") String orderId);

    @Update("UPDATE delivery_statement_session SET status=#{status}, updated_time=NOW() WHERE id=#{id} AND tenant_id=#{tenantId}")
    int updateStatus(@Param("tenantId") Long tenantId,
                     @Param("id") Long id,
                     @Param("status") String status);

    @Update("UPDATE delivery_statement_session " +
            "SET status='waiting', sent_at=#{sentAt}, statement_msg_id=#{msgId}, updated_time=NOW() " +
            "WHERE id=#{id} AND tenant_id=#{tenantId}")
    int markWaiting(@Param("tenantId") Long tenantId,
                    @Param("id") Long id,
                    @Param("sentAt") LocalDateTime sentAt,
                    @Param("msgId") String msgId);

    @Update("UPDATE delivery_statement_session " +
            "SET status='confirmed', confirmed_at=#{confirmedAt}, confirm_source=#{source}, " +
            "reply_msg_id=#{replyMsgId}, updated_time=NOW() " +
            "WHERE id=#{id} AND tenant_id=#{tenantId} AND status='waiting'")
    int markConfirmed(@Param("tenantId") Long tenantId,
                      @Param("id") Long id,
                      @Param("confirmedAt") LocalDateTime confirmedAt,
                      @Param("source") String source,
                      @Param("replyMsgId") String replyMsgId);

    @Update("UPDATE delivery_statement_session " +
            "SET status='cancelled', cancelled_at=#{cancelledAt}, cancel_source=#{source}, " +
            "reply_msg_id=#{replyMsgId}, updated_time=NOW() " +
            "WHERE id=#{id} AND tenant_id=#{tenantId} AND status='waiting'")
    int markCancelled(@Param("tenantId") Long tenantId,
                      @Param("id") Long id,
                      @Param("cancelledAt") LocalDateTime cancelledAt,
                      @Param("source") String source,
                      @Param("replyMsgId") String replyMsgId);

    @Update("UPDATE delivery_statement_session SET delivery_record_id=#{recordId}, updated_time=NOW() " +
            "WHERE id=#{id} AND tenant_id=#{tenantId}")
    int bindDeliveryRecord(@Param("tenantId") Long tenantId,
                           @Param("id") Long id,
                           @Param("recordId") Long recordId);
}
