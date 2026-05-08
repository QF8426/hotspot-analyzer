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

    // AI 简介正文
    private String aiSummary;

    // 简介类型：single_platform / cross_platform
    private String analysisType;

    // 跨平台关联热点 ID，例如：1840,1735,1888
    private String relatedHotspotIds;

    // 跨平台关联平台，例如：douyin,bilibili,weibo
    private String relatedPlatforms;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime crawlTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;
}