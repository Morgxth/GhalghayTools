package com.ingush.history.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "events")
@Data
@NoArgsConstructor
public class Event {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Integer year;

    @Column(name = "title_ru", nullable = false)
    private String titleRu;

    @Column(name = "description_ru", columnDefinition = "TEXT")
    private String descriptionRu;

    private String category;

    private Double lat;
    private Double lon;

    @Column(name = "source_ref")
    private String sourceRef;
}
