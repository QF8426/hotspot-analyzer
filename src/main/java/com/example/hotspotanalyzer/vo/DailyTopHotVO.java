package com.example.hotspotanalyzer.vo;

public class DailyTopHotVO {

    private Long id;
    private String platform;
    private String title;
    private Long maxHotValue;
    private String sourceUrl;

    public DailyTopHotVO() {
    }

    public DailyTopHotVO(Long id, String platform, String title, Long maxHotValue, String sourceUrl) {
        this.id = id;
        this.platform = platform;
        this.title = title;
        this.maxHotValue = maxHotValue;
        this.sourceUrl = sourceUrl;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getPlatform() {
        return platform;
    }

    public void setPlatform(String platform) {
        this.platform = platform;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public Long getMaxHotValue() {
        return maxHotValue;
    }

    public void setMaxHotValue(Long maxHotValue) {
        this.maxHotValue = maxHotValue;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
    }
}