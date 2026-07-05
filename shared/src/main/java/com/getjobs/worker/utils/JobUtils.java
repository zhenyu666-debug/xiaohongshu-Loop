package com.getjobs.worker.utils;

public class JobUtils {
    public static String extractSalaryNumber(String salary) {
        if (salary == null || salary.isBlank()) return "0";
        String num = salary.replaceAll("[^0-9]", "");
        return num.isEmpty() ? "0" : num;
    }

    public static String appendParam(String key, String value) {
        if (value == null || value.isBlank()) return "";
        return "&" + key + "=" + value;
    }
}
