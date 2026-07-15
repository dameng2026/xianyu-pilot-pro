package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.xianyu.admin.common.BizException;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

class OpenSourceContentLinkSecurityTest {
    @Test
    void acceptsInternalOrHttpHttpsCarouselLinks() {
        assertEquals("", OpenSourceContentService.safeCarouselLink("", true));
        assertEquals("/settings/profile", OpenSourceContentService.safeCarouselLink("/settings/profile", true));
        assertEquals("#/settings/profile", OpenSourceContentService.safeCarouselLink("#/settings/profile", true));
        assertEquals("https://docs.example.com/guide",
                OpenSourceContentService.safeCarouselLink("https://docs.example.com/guide", true));
        assertEquals("http://example.com/insecure",
                OpenSourceContentService.safeCarouselLink("http://example.com/insecure", true));
        assertEquals("https://example.com:8443/page",
                OpenSourceContentService.safeCarouselLink("https://example.com:8443/page", true));
        assertEquals("https://example.com/page#section",
                OpenSourceContentService.safeCarouselLink("https://example.com/page#section", true));
        assertEquals("https://user:password@example.com/path",
                OpenSourceContentService.safeCarouselLink("https://user:password@example.com/path", true));

        for (String unsafe : new String[]{
                "javascript:alert(1)",
                "data:text/html,attack",
                "//evil.example/path"
        }) {
            assertThrows(IllegalArgumentException.class,
                    () -> OpenSourceContentService.safeCarouselLink(unsafe, true));
            assertEquals("", OpenSourceContentService.safeCarouselLink(unsafe, false));
        }
    }

    @Test
    void acceptsOnlyGovernedContentMediaOrHttpsCarouselImages() {
        assertEquals("/uploads/images/tenant-7/carousel_abcd1234.webp",
                OpenSourceContentService.safeCarouselImage(
                        "/uploads/images/tenant-7/carousel_abcd1234.webp", true));
        assertEquals("https://cdn.example.com/banner.webp",
                OpenSourceContentService.safeCarouselImage(
                        "https://cdn.example.com/banner.webp", true));

        for (String unsafe : new String[]{
                "javascript:alert(1)",
                "data:image/svg+xml,<svg onload=alert(1)>",
                "http://example.com/banner.png",
                "//evil.example/banner.png",
                "/api/admin/export",
                "/uploads/private/tenant-7/banner.png",
                "/uploads/public/tenant-7/2026/07/banner.webp",
                "/uploads/public/../private/banner.png",
                "https://user:password@example.com/banner.png"
        }) {
            assertThrows(IllegalArgumentException.class,
                    () -> OpenSourceContentService.safeCarouselImage(unsafe, true));
            assertEquals("", OpenSourceContentService.safeCarouselImage(unsafe, false));
        }
    }

    @Test
    void rejectsInvalidCommercialContentBeforeDatabaseAccess() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        OpenSourceContentService service = new OpenSourceContentService(jdbcTemplate);

        assertThrows(IllegalArgumentException.class, () -> service.saveCommercialHomeCarousel(Map.of(
                "title", "危险图片",
                "imageUrl", "javascript:alert(1)"
        )));
        BizException blankAnnouncement = assertThrows(BizException.class,
                () -> service.saveCommercialHomeAnnouncement(Map.of(
                        "title", " ",
                        "content", "正文"
                )));
        assertEquals(400, blankAnnouncement.getCode());

        List<Map<String, Object>> covers = new ArrayList<>();
        for (int index = 0; index < 11; index += 1) {
            Map<String, Object> cover = new LinkedHashMap<>();
            cover.put("imageUrl", "https://cdn.example.com/" + index + ".png");
            covers.add(cover);
        }
        BizException tooManyCovers = assertThrows(BizException.class,
                () -> service.saveCommercialHomeCarousel(Map.of(
                        "title", "过多图片",
                        "coverItems", covers
                )));
        assertEquals(400, tooManyCovers.getCode());
        verifyNoInteractions(jdbcTemplate);
    }

    @Test
    void rejectsStoredAboutPageScriptAndUnsafeDestinationsBeforeDatabaseAccess() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        OpenSourceContentService service = new OpenSourceContentService(jdbcTemplate);

        BizException unsafeLegalUrl = assertThrows(BizException.class,
                () -> service.saveAboutContent(Map.of(
                        "legalDocs", Map.of(
                                "termsUrl", "javascript:alert(1)",
                                "privacyUrl", "",
                                "supportEmail", "support@company.cn"
                        )
                )));
        assertEquals(400, unsafeLegalUrl.getCode());

        BizException unsafeAction = assertThrows(BizException.class,
                () -> service.saveAboutContent(Map.of(
                        "supports", List.of(Map.of(
                                "label", "危险入口",
                                "actionType", "external",
                                "actionValue", "http://insecure.example/path"
                        ))
                )));
        assertEquals(400, unsafeAction.getCode());

        BizException storedMarkup = assertThrows(BizException.class,
                () -> service.saveAboutContent(Map.of(
                        "heroTitle", "<img src=x onerror=alert(1)>"
                )));
        assertEquals(400, storedMarkup.getCode());
        verifyNoInteractions(jdbcTemplate);
    }
}
