package com.ingush.history.repository;

import com.ingush.history.model.Event;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface EventRepository extends JpaRepository<Event, Long> {
    List<Event> findByYearBetween(Integer yearFrom, Integer yearTo);
    List<Event> findByCategory(String category);
    List<Event> findByYearBetweenAndCategory(Integer yearFrom, Integer yearTo, String category);
}
