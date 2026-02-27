package com.ingush.history.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "societies")
@Data
@NoArgsConstructor
public class Society {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "name_ru", nullable = false)
    private String nameRu;

    @Column(name = "name_ing")
    private String nameIng;

    @Column(name = "description_ru", columnDefinition = "TEXT")
    private String descriptionRu;

    @Column(name = "territory_geojson", columnDefinition = "TEXT")
    private String territoryGeojson;

    @Column(name = "era_from")
    private Integer eraFrom;

    @Column(name = "era_to")
    private Integer eraTo;
}
