package com.ingush.history.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "persons")
@Data
@NoArgsConstructor
public class Person {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "name_ru", nullable = false)
    private String nameRu;

    private String years;

    @Column(name = "role_ru")
    private String roleRu;

    @Column(name = "biography_ru", columnDefinition = "TEXT")
    private String biographyRu;
}
