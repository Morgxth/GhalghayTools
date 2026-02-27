package com.ingush.history.repository;

import com.ingush.history.model.Toponym;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ToponymRepository extends JpaRepository<Toponym, Long> {
    List<Toponym> findByNameRuContainingIgnoreCase(String search);
}
