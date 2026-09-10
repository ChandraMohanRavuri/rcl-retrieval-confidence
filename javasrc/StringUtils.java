package com.acmecorp.common;

public class StringUtils {

    public static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }

    public static String truncate(String s, int max) {
        if (s == null) return null;
        return s.length() > max ? s.substring(0, max) : s;
    }
}
