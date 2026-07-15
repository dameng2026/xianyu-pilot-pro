package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuAccountAuth;
import org.apache.ibatis.annotations.*;

import java.time.LocalDateTime;

@Mapper
public interface XianyuAccountAuthMapper {

    @Select("SELECT * FROM xianyu_account_auth WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0 ORDER BY updated_time DESC, id DESC LIMIT 1")
    XianyuAccountAuth findByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Select("SELECT * FROM xianyu_account_auth WHERE tenant_id = #{tenantId} AND account_id = #{accountId} ORDER BY deleted ASC, updated_time DESC, id DESC LIMIT 1")
    XianyuAccountAuth findLatestByAccountIdIncludingDeleted(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Insert("INSERT INTO xianyu_account_auth(tenant_id, account_id, encrypted_cookie, encrypted_token, login_username, encrypted_login_password, show_browser, cookie_status, ws_token, token_expire_time, last_login_status_code, last_login_status_message, last_login_check_time, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{encryptedCookie}, #{encryptedToken}, #{loginUsername}, #{encryptedLoginPassword}, #{showBrowser}, #{cookieStatus}, #{wsToken}, #{tokenExpireTime}, #{lastLoginStatusCode}, #{lastLoginStatusMessage}, #{lastLoginCheckTime}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuAccountAuth auth);

    @Update("UPDATE xianyu_account_auth SET encrypted_cookie = #{encryptedCookie}, encrypted_token = #{encryptedToken}, " +
            "login_username = #{loginUsername}, encrypted_login_password = #{encryptedLoginPassword}, show_browser = #{showBrowser}, " +
            "cookie_status = #{cookieStatus}, ws_token = #{wsToken}, token_expire_time = #{tokenExpireTime}, " +
            "last_login_status_code = #{lastLoginStatusCode}, last_login_status_message = #{lastLoginStatusMessage}, " +
            "last_login_check_time = #{lastLoginCheckTime}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int update(XianyuAccountAuth auth);

    @Update("UPDATE xianyu_account_auth SET cookie_status = #{cookieStatus}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0")
    int updateCookieStatus(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("cookieStatus") Integer cookieStatus);

    @Update("UPDATE xianyu_account_auth SET cookie_status = #{cookieStatus}, last_login_status_code = #{code}, " +
            "last_login_status_message = #{message}, last_login_check_time = #{checkedAt}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0")
    int updateLoginStatus(@Param("tenantId") Long tenantId,
                          @Param("accountId") Long accountId,
                          @Param("cookieStatus") Integer cookieStatus,
                          @Param("code") String code,
                          @Param("message") String message,
                          @Param("checkedAt") LocalDateTime checkedAt);

    @Update("UPDATE xianyu_account_auth SET deleted = 1, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0")
    int softDeleteByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Update("UPDATE xianyu_account_auth SET deleted = 0, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 1")
    int restoreByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Select("SELECT COUNT(*) FROM xianyu_account_auth WHERE tenant_id = #{tenantId} AND cookie_status = #{cookieStatus} AND deleted = 0")
    int countByCookieStatus(@Param("tenantId") Long tenantId, @Param("cookieStatus") Integer cookieStatus);
}
