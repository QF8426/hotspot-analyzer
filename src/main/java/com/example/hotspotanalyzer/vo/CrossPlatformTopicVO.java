package com.example.hotspotanalyzer.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Data
public class CrossPlatformTopicVO {
    private Long id;
    private String mainTitle;
    private String summary;
    private String topicStatus;
    private Double confidenceScore;
    private Integer platformCount;
    private Integer hotspotCount;
    private String relatedPlatforms;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime firstSeenTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime lastSeenTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updatedAt;

    private List<CrossPlatformHotspotVO> hotspots = new ArrayList<>();
}
