package com.xianyu.admin.controller;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.dto.NavigationHomeVO;
import com.xianyu.admin.dto.NavigationOverviewVO;
import com.xianyu.admin.service.NavigationService;
import com.xianyu.admin.service.OpenSourceContentService;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class NavigationControllerContentDegradationTest {

    @Test
    void contentFailureIsExplicitButDoesNotHideOtherHomeData() {
        NavigationService navigation = navigationService();
        OpenSourceContentService content = mock(OpenSourceContentService.class);
        when(content.listCommercialHomeCarousels())
                .thenThrow(new BizException(503, "database unavailable"));

        Result<NavigationHomeVO> response = new NavigationController(navigation, content).home(5);

        assertEquals(200, response.getCode());
        assertFalse(response.getData().isContentAvailable());
        assertFalse(response.getData().getContentMessage().isBlank());
        assertTrue(((List<?>) response.getData().getCarousels()).isEmpty());
        assertEquals(0, response.getData().getOverview().getAccountCount());
    }

    @Test
    void contentSuccessIsDistinguishedFromAValidEmptyConfiguration() {
        NavigationService navigation = navigationService();
        OpenSourceContentService content = mock(OpenSourceContentService.class);
        when(content.listCommercialHomeCarousels()).thenReturn(List.of());
        when(content.listCommercialHomeAnnouncements()).thenReturn(List.of(Map.of(
                "id", 1,
                "title", "维护通知",
                "content", "今晚进行例行维护",
                "enabled", true
        )));

        NavigationHomeVO data = new NavigationController(navigation, content).home(5).getData();

        assertTrue(data.isContentAvailable());
        assertTrue(data.getContentMessage().isBlank());
        assertTrue(((List<?>) data.getCarousels()).isEmpty());
        assertEquals(1, ((List<?>) data.getAnnouncements()).size());
    }

    private NavigationService navigationService() {
        NavigationService navigation = mock(NavigationService.class);
        when(navigation.overview(any())).thenReturn(new NavigationOverviewVO());
        when(navigation.recentNotifications(any(), anyInt())).thenReturn(List.of());
        when(navigation.systemStatus()).thenReturn(List.of());
        return navigation;
    }
}
