package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.PublicContentMediaService;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.mock.web.MockMultipartHttpServletRequest;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class OpenSourceContentMediaControllerTest {

    @Test
    void fileUploadUsesDedicatedOpenSourceContentPurpose() {
        PublicContentMediaService media = mock(PublicContentMediaService.class);
        OpenSourceContentMediaController controller = new OpenSourceContentMediaController(media);
        MockMultipartHttpServletRequest request = new MockMultipartHttpServletRequest();
        MockMultipartFile file = new MockMultipartFile(
                "file", "group.png", "image/png", new byte[]{1, 2, 3});
        request.addFile(file);

        controller.upload(request);

        verify(media).upload(eq(file), eq(PublicContentMediaService.PURPOSE_OPEN_SOURCE_CONTENT));
    }

    @Test
    void urlImportUsesDedicatedOpenSourceContentPurpose() {
        PublicContentMediaService media = mock(PublicContentMediaService.class);
        OpenSourceContentMediaController controller = new OpenSourceContentMediaController(media);

        controller.importFromUrl(Map.of("url", "https://cdn.company.cn/group.png"));

        verify(media).importFromUrl(
                eq("https://cdn.company.cn/group.png"),
                eq(PublicContentMediaService.PURPOSE_OPEN_SOURCE_CONTENT));
    }

    @Test
    void uploadRejectsNonMultipartRequest() {
        OpenSourceContentMediaController controller = new OpenSourceContentMediaController(
                mock(PublicContentMediaService.class));

        BizException error = assertThrows(BizException.class,
                () -> controller.upload(new MockHttpServletRequest()));

        assertEquals(400, error.getCode());
    }
}
