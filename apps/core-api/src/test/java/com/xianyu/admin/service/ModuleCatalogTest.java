package com.xianyu.admin.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ModuleCatalogTest {

    @Test
    void shouldExposeImagePromptCategoryModule() {
        ModuleCatalog.ModuleMeta meta = new ModuleCatalog().get("model-config-image-prompts");

        assertEquals("model-config-image-prompts", meta.key());
        assertTrue(
                meta.columns().stream().anyMatch(column -> "promptTemplate".equals(String.valueOf(column.get("prop")))),
                "image prompt module should expose promptTemplate column"
        );
    }
}
