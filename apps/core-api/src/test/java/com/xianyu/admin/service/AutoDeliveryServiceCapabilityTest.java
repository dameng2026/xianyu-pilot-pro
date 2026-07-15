package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.dto.DeliveryRuleDTO;
import com.xianyu.admin.mapper.DeliveryRuleMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

class AutoDeliveryServiceCapabilityTest {
    @Test
    void unsupportedApiDeliveryCannotBePersisted() {
        DeliveryRuleMapper mapper = mock(DeliveryRuleMapper.class);
        AutoDeliveryService service = new AutoDeliveryService(mapper);
        DeliveryRuleDTO request = new DeliveryRuleDTO();
        request.setDeliveryType("api");

        BizException error = assertThrows(BizException.class,
                () -> service.createRule(1L, request));

        assertEquals(422, error.getCode());
        verifyNoInteractions(mapper);
    }
}
