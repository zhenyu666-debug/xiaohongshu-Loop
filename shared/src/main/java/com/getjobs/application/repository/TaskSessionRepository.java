package com.getjobs.application.repository;

import com.getjobs.application.entity.TaskSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface TaskSessionRepository extends JpaRepository<TaskSession, Long> {
    Optional<TaskSession> findBySessionId(String sessionId);
    Optional<TaskSession> findTopByStatusOrderByStartedAtDesc(String status);
}
