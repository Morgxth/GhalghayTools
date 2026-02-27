package com.ingush.history.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "toponyms")
@Data
@NoArgsConstructor
public class Toponym {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "name_ru", nullable = false)
    private String nameRu;

    @Column(name = "name_ing")
    private String nameIng;

    @Column(name = "etymology_ru", columnDefinition = "TEXT")
    private String etymologyRu;

    @Column(name = "modern_name")
    private String modernName;

    private Double lat;
    private Double lon;
}
