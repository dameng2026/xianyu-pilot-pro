package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.entity.CardGroup;
import com.xianyu.admin.mapper.CardGroupMapper;
import com.xianyu.admin.mapper.CardItemMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class CardServiceSecurityTest {

    @Test
    void createRejectsRecordBreakingControlCharactersBeforeDatabaseWork() {
        CardGroupMapper groupMapper = mock(CardGroupMapper.class);
        CardItemMapper itemMapper = mock(CardItemMapper.class);
        CardService service = new CardService(groupMapper, itemMapper);

        BizException error = assertThrows(BizException.class,
                () -> service.createItem(7L, 9L, "first\nsecond"));

        assertEquals(400, error.getCode());
        verifyNoInteractions(groupMapper, itemMapper);
    }

    @Test
    void exportRejectsExcessiveRowCountBeforeLoadingAllSecretsIntoMemory() {
        CardGroupMapper groupMapper = mock(CardGroupMapper.class);
        CardItemMapper itemMapper = mock(CardItemMapper.class);
        CardService service = new CardService(groupMapper, itemMapper);
        CardGroup group = new CardGroup();
        group.setId(9L);
        group.setTenantId(7L);
        when(groupMapper.findById(7L, 9L)).thenReturn(group);
        when(itemMapper.countByGroupIdAndStatus(7L, 9L, null)).thenReturn(20_001);
        when(itemMapper.estimateExportBytes(7L, 9L)).thenReturn(1L);

        BizException error = assertThrows(BizException.class,
                () -> service.exportItems(7L, 9L));

        assertEquals(413, error.getCode());
        verify(itemMapper, never()).listAllByGroup(7L, 9L);
    }
}
