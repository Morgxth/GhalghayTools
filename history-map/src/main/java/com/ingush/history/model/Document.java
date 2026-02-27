package com.ingush.history.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "documents")
@Data
@NoArgsConstructor
public class Document {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String title;

    private Integer year;
    private String author;

    @Column(name = "text_ru", columnDefinition = "TEXT")
    private String textRu;

    @Column(name = "archive_ref")
    private String archiveRef;

    @Column(name = "image_url")
    private String imageUrl;
}
