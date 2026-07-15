package com.xianyu.admin.common;

/**
 * Encodes untrusted values as RFC-4180-style CSV cells and neutralizes
 * spreadsheet formula injection. Quoting alone is not sufficient: Excel and
 * similar programs may still execute a quoted cell beginning with =, +, - or
 * @ when an operator opens an exported file.
 */
public final class CsvCellEncoder {
    private static final String FORMULA_PREFIXES = "=+-@";

    private CsvCellEncoder() {}

    public static String encode(Object value) {
        String text = value == null ? "" : String.valueOf(value);
        text = text.replace('\u0000', ' ')
                .replaceAll("[\\r\\n\\t]+", " ");
        if (startsLikeFormula(text)) {
            text = "'" + text;
        }
        return "\"" + text.replace("\"", "\"\"") + "\"";
    }

    private static boolean startsLikeFormula(String value) {
        int index = 0;
        while (index < value.length() && Character.isWhitespace(value.charAt(index))) {
            index++;
        }
        return index < value.length() && FORMULA_PREFIXES.indexOf(value.charAt(index)) >= 0;
    }
}
