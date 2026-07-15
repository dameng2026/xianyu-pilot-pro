package com.xianyu.admin.common;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CsvCellEncoderTest {

    @Test
    void neutralizesSpreadsheetFormulaPrefixesIncludingLeadingWhitespace() {
        assertEquals("\"'=HYPERLINK(\"\"https://evil.invalid\"\")\"",
                CsvCellEncoder.encode("=HYPERLINK(\"https://evil.invalid\")"));
        assertEquals("\"'  +cmd\"", CsvCellEncoder.encode("  +cmd"));
        assertEquals("\"'-2\"", CsvCellEncoder.encode("-2"));
        assertEquals("\"'@SUM(A1:A2)\"", CsvCellEncoder.encode("@SUM(A1:A2)"));
    }

    @Test
    void quotesDoubleQuotesAndFlattensRecordBreakingControls() {
        assertEquals("\"safe \"\"value\"\" next line\"",
                CsvCellEncoder.encode("safe \"value\"\r\nnext\tline"));
    }
}
