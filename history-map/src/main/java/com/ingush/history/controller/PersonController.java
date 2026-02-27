package com.ingush.history.controller;

import com.ingush.history.model.Person;
import com.ingush.history.repository.PersonRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/persons")
@RequiredArgsConstructor
public class PersonController {

    private final PersonRepository personRepository;

    @GetMapping
    public List<Person> getPersons(@RequestParam(required = false) String role) {
        if (role != null) {
            return personRepository.findByRoleRu(role);
        }
        return personRepository.findAll();
    }

    @GetMapping("/{id}")
    public Person getPerson(@PathVariable Long id) {
        return personRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Person not found: " + id));
    }
}
