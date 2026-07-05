package com.getjobs.common.cache;

import lombok.extern.slf4j.Slf4j;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@Slf4j
public class ThreadSafeCache<K, V> {
    private final ConcurrentHashMap<K, CacheEntry<V>> cache = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<K, Object> keyLocks = new ConcurrentHashMap<>();
    private final Duration defaultTtl;
    private final long maxSize;
    private final AtomicLong hits = new AtomicLong(0);
    private final AtomicLong misses = new AtomicLong(0);
    private final String name;

    public ThreadSafeCache(String cacheName, Duration ttl) {
        this(cacheName, ttl, 10000);
    }

    public ThreadSafeCache(String cacheName, Duration ttl, long sizeLimit) {
        this.name = cacheName;
        this.defaultTtl = ttl;
        this.maxSize = sizeLimit;
    }

    public static <K, V> ThreadSafeCache<K, V> of(String cacheName, Duration ttl) {
        return new ThreadSafeCache<>(cacheName, ttl);
    }

    public static <K, V> ThreadSafeCache<K, V> shortLived(String cacheName) {
        return new ThreadSafeCache<>(cacheName, Duration.ofMinutes(5));
    }

    public static <K, V> ThreadSafeCache<K, V> mediumLived(String cacheName) {
        return new ThreadSafeCache<>(cacheName, Duration.ofMinutes(30));
    }

    public static <K, V> ThreadSafeCache<K, V> longLived(String cacheName) {
        return new ThreadSafeCache<>(cacheName, Duration.ofHours(2));
    }

    public V getOrCompute(K key, java.util.function.Supplier<V> computation) {
        return getOrCompute(key, defaultTtl, computation);
    }

    public V getOrCompute(K key, Duration ttl, java.util.function.Supplier<V> computation) {
        CacheEntry<V> entry = cache.get(key);
        if (entry != null && !entry.isExpired()) {
            hits.incrementAndGet();
            return entry.value();
        }
        Object keyLock = keyLocks.computeIfAbsent(key, k -> new Object());
        synchronized (keyLock) {
            // Re-check after acquiring lock
            entry = cache.get(key);
            if (entry != null && !entry.isExpired()) {
                hits.incrementAndGet();
                return entry.value();
            }
            // Remove expired entry if present
            if (entry != null) {
                cache.remove(key, entry);
            }
            // Only evict when at capacity — lazily, not eagerly on every call
            if (cache.size() >= maxSize) {
                List<K> keysToRemove = cache.keySet().stream()
                        .limit(Math.max(1, cache.size() - maxSize + 1))
                        .toList();
                keysToRemove.forEach(k -> {
                    cache.remove(k);
                    keyLocks.remove(k);
                });
            }
            boolean shouldRemoveLock = true;
            try {
                V value = computation.get();
                if (value != null) {
                    cache.put(key, new CacheEntry<>(value, Instant.now().plus(ttl)));
                    shouldRemoveLock = false;
                }
                return value;
            } finally {
                if (shouldRemoveLock) {
                    keyLocks.remove(key, keyLock);
                }
            }
        }
    }

    public V get(K key) {
        CacheEntry<V> entry = cache.get(key);
        if (entry == null) {
            misses.incrementAndGet();
            return null;
        }
        if (entry.isExpired()) {
            cache.remove(key);
            misses.incrementAndGet();
            return null;
        }
        hits.incrementAndGet();
        return entry.value();
    }

    public void put(K key, V value) {
        cache.put(key, new CacheEntry<>(value, Instant.now().plus(defaultTtl)));
    }

    public void put(K key, V value, Duration ttl) {
        cache.put(key, new CacheEntry<>(value, Instant.now().plus(ttl)));
    }

    public void invalidate(K key) {
        cache.remove(key);
    }

    public void clear() {
        cache.clear();
        keyLocks.clear();
        log.info("Cache '{}' cleared", name);
    }

    public void evictExpired() {
        long evicted = 0;
        for (var entry : cache.entrySet()) {
            if (entry.getValue().isExpired()) {
                if (cache.remove(entry.getKey(), entry.getValue())) {
                    evicted++;
                }
            }
        }
        if (evicted > 0) {
            log.debug("Evicted {} expired entries from cache '{}'", evicted, name);
        }
    }

    public Stats getStats() {
        long total = hits.get() + misses.get();
        double hitRate = total > 0 ? (double) hits.get() / total * 100 : 0;
        return new Stats(name, cache.size(), hits.get(), misses.get(), hitRate);
    }

    public record Stats(String name, int size, long hits, long misses, double hitRatePercent) {}

    private record CacheEntry<V>(V value, Instant expiresAt) {
        boolean isExpired() {
            return Instant.now().isAfter(expiresAt);
        }
    }
}
