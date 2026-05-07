package com.example.hotspotanalyzer.entity;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class Hotspot {
    private Long id;
    private String platform;
    private String title;
    private Integer rankNum;
    private Long hotValue;
    private String tags;
    private Boolean isRanked;
    private Boolean isSpecial;
    private String sourceUrl;

    // ✅ 新增：AI 简介
    private String aiSummary;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime crawlTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;
}