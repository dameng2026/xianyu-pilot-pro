package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.AutomationClient;
import com.xianyu.admin.service.OutboundImageUrlPolicy;
import com.xianyu.admin.service.OpenSourceContentService;
import com.xianyu.admin.service.PublicContentMediaService;
import com.xianyu.admin.service.TenantSupportService;
import com.xianyu.admin.service.UploadedImageValidator;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.mock.web.MockMultipartHttpServletRequest;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.util.Map;
import java.net.URI;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.verify;
import static org.mockito.ArgumentMatchers.eq;

class AdminContentControllerSecurityTest {

    @Test
    void urlImportRejectsPrivateDestinationsBeforeCallingAutomation() throws Exception {
        AutomationClient client = mock(AutomationClient.class);
        OutboundImageUrlPolicy policy = mock(OutboundImageUrlPolicy.class);
        when(policy.validate("http://127.0.0.1/internal.png"))
                .thenThrow(new IllegalArgumentException("private destination"));
        AdminContentController controller = controller(client, policy);

        BizException error = assertThrows(BizException.class, () -> controller.carouselUploadFromUrl(
                Map.of("url", "http://127.0.0.1/internal.png")));
        assertEquals(400, error.getCode());
        verifyNoInteractions(client);
    }

    @Test
    void uploadRejectsSpoofedImageBeforeCallingAutomation() throws Exception {
        AutomationClient client = mock(AutomationClient.class);
        OutboundImageUrlPolicy policy = mock(OutboundImageUrlPolicy.class);
        AdminContentController controller = controller(client, policy);
        MockMultipartHttpServletRequest request = new MockMultipartHttpServletRequest();
        request.addFile(new MockMultipartFile(
                "file", "payload.html", "image/png", "<script>alert(1)</script>".getBytes()));

        BizException error = assertThrows(BizException.class, () -> controller.carouselUpload(request));
        assertEquals(400, error.getCode());
        verifyNoInteractions(client);
    }

    @Test
    void carouselUrlImportExplicitlyPublishesOnlyForCarouselPurpose() throws Exception {
        AutomationClient client = mock(AutomationClient.class);
        OutboundImageUrlPolicy policy = mock(OutboundImageUrlPolicy.class);
        when(policy.validate("https://images.example/banner.png"))
                .thenReturn(URI.create("https://images.example/banner.png"));
        TenantSupportService tenants = mock(TenantSupportService.class);
        when(tenants.resolveCurrentOrDefaultTenantId()).thenReturn(7L);
        AdminContentController controller = new AdminContentController(
                mock(OpenSourceContentService.class),
                new PublicContentMediaService(client, tenants, policy, new UploadedImageValidator()));

        controller.carouselUploadFromUrl(Map.of("url", "https://images.example/banner.png"));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> payload = ArgumentCaptor.forClass(Map.class);
        verify(client).postInternalForData(
                eq("/api/image/uploadFromUrl"), payload.capture(), eq(Long.valueOf(7L)));
        assertEquals("public", payload.getValue().get("visibility"));
        assertEquals("carousel", payload.getValue().get("purpose"));
    }

    @Test
    void commercialContentCrudUsesJavaDatabaseServiceInsteadOfAutomation() {
        AutomationClient client = mock(AutomationClient.class);
        OpenSourceContentService content = mock(OpenSourceContentService.class);
        AdminContentController controller = new AdminContentController(
                content,
                mock(PublicContentMediaService.class)
        );

        controller.carouselList();
        controller.announcementList();

        verify(content).listCommercialHomeCarousels();
        verify(content).listCommercialHomeAnnouncements();
        verifyNoInteractions(client);
    }

    @Test
    void carouselFileUploadUsesDedicatedInternalProcessingRoute() throws Exception {
        AutomationClient client = mock(AutomationClient.class);
        TenantSupportService tenants = mock(TenantSupportService.class);
        when(tenants.resolveCurrentOrDefaultTenantId()).thenReturn(7L);
        AdminContentController controller = new AdminContentController(
                mock(OpenSourceContentService.class),
                new PublicContentMediaService(
                        client,
                        tenants,
                        mock(OutboundImageUrlPolicy.class),
                        new UploadedImageValidator()
                )
        );
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        ImageIO.write(new BufferedImage(8, 6, BufferedImage.TYPE_INT_RGB), "png", bytes);
        MockMultipartHttpServletRequest request = new MockMultipartHttpServletRequest();
        request.addFile(new MockMultipartFile(
                "file", "banner.png", "image/png", bytes.toByteArray()));

        controller.carouselUpload(request);

        verify(client).uploadInternalForData(
                eq("/api/internal/content/public-images/upload"),
                org.mockito.ArgumentMatchers.any(),
                eq("carousel.png"),
                eq(Map.of("purpose", "carousel")),
                eq(7L)
        );
    }

    private AdminContentController controller(AutomationClient client, OutboundImageUrlPolicy policy) {
        return new AdminContentController(
                mock(OpenSourceContentService.class),
                new PublicContentMediaService(
                        client,
                        mock(TenantSupportService.class),
                        policy,
                        new UploadedImageValidator()
                )
        );
    }
}
