package com.example.hotspotanalyzer.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class CrossPlatformHotspotVO {
    private Long topicId;
    private Long hotspotId;
    private String platform;
    private String title;
    private Double matchScore;
    private Boolean primary;
    private Integer rankNum;
    private Long hotValue;
    private String sourceUrl;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime crawlTime;
}
