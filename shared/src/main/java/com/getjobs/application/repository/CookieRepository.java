package com.getjobs.application.repository;

import com.getjobs.application.entity.CookieEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface CookieRepository extends JpaRepository<CookieEntity, Long> {
    Optional<CookieEntity> findByPlatform(String platform);
}
