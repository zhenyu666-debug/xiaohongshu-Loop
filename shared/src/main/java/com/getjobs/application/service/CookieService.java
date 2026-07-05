package com.getjobs.application.service;

import com.getjobs.application.entity.CookieEntity;
import com.getjobs.application.repository.CookieRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class CookieService {

    private final CookieRepository cookieRepository;

    public CookieEntity getCookieByPlatform(String platform) {
        return cookieRepository.findByPlatform(platform).orElse(null);
    }

    public boolean saveOrUpdateCookie(String platform, String cookieValue, String remark) {
        try {
            Optional<CookieEntity> existing = cookieRepository.findByPlatform(platform);
            if (existing.isPresent()) {
                CookieEntity entity = existing.get();
                entity.setCookieValue(cookieValue);
                entity.setRemark(remark);
                cookieRepository.save(entity);
                log.info("更新 Cookie 成功: platform={}", platform);
            } else {
                CookieEntity entity = new CookieEntity();
                // SQLite 表的 id 列未声明为 INTEGER PRIMARY KEY autoincrement,
                // Hibernate ddl-auto: update 不会修改已有列,这里手动分配下一个 id。
                Long nextId = cookieRepository.findAll().stream()
                        .map(CookieEntity::getId)
                        .filter(java.util.Objects::nonNull)
                        .max(Long::compareTo)
                        .orElse(0L) + 1L;
                entity.setId(nextId);
                entity.setPlatform(platform);
                entity.setCookieValue(cookieValue);
                entity.setRemark(remark);
                cookieRepository.save(entity);
                log.info("新增 Cookie 成功: platform={}, id={}", platform, nextId);
            }
            return true;
        } catch (Exception e) {
            log.error("保存 Cookie 失败: platform={}, error={}", platform, e.getMessage());
            return false;
        }
    }

    @Transactional
    public boolean clearCookieByPlatform(String platform, String remark) {
        try {
            Optional<CookieEntity> existing = cookieRepository.findByPlatform(platform);
            if (existing.isPresent()) {
                CookieEntity entity = existing.get();
                entity.setCookieValue("");
                entity.setRemark(remark);
                cookieRepository.save(entity);
                log.info("清空 Cookie 成功: platform={}", platform);
            }
            return true;
        } catch (Exception e) {
            log.error("清空 Cookie 失败: platform={}, error={}", platform, e.getMessage());
            return false;
        }
    }
}
