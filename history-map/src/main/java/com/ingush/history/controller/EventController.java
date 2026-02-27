package com.ingush.history.controller;

import com.ingush.history.model.Event;
import com.ingush.history.repository.EventRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/events")
@RequiredArgsConstructor
public class EventController {

    private final EventRepository eventRepository;

    @GetMapping
    public List<Event> getEvents(
            @RequestParam(required = false) Integer year_from,
            @RequestParam(required = false) Integer year_to,
            @RequestParam(required = false) String category) {

        if (year_from != null && year_to != null && category != null) {
            return eventRepository.findByYearBetweenAndCategory(year_from, year_to, category);
        }
        if (year_from != null && year_to != null) {
            return eventRepository.findByYearBetween(year_from, year_to);
        }
        if (category != null) {
            return eventRepository.findByCategory(category);
        }
        return eventRepository.findAll();
    }

    @GetMapping("/{id}")
    public Event getEvent(@PathVariable Long id) {
        return eventRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Event not found: " + id));
    }
}
