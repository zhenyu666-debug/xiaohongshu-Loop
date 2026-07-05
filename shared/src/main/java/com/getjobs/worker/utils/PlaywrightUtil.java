package com.getjobs.worker.utils;

public class PlaywrightUtil {
    public static void sleep(int seconds) {
        try {
            Thread.sleep(seconds * 1000L);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public static void sleepMs(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public static void humanizedDelay(int seconds) {
        try {
            Thread.sleep((long) (seconds * 1000 * (0.8 + Math.random() * 0.4)));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public static void humanizedDelay() {
        humanizedDelay(1);
    }
}
