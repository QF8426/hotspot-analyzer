package com.example.hotspotanalyzer.vo;

public class HistoryHotVO {

    private Long hotspotId;
    private String platform;
    private String title;
    private Long maxHotValue;
    private Integer bestRankNum;
    private Integer appearCount;
    private Integer durationMinutes;
    private Boolean isSpecial;
    private String sourceUrl;

    public HistoryHotVO() {
    }

    public Long getHotspotId() {
        return hotspotId;
    }

    public void setHotspotId(Long hotspotId) {
        this.hotspotId = hotspotId;
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

    public Integer getBestRankNum() {
        return bestRankNum;
    }

    public void setBestRankNum(Integer bestRankNum) {
        this.bestRankNum = bestRankNum;
    }

    public Integer getAppearCount() {
        return appearCount;
    }

    public void setAppearCount(Integer appearCount) {
        this.appearCount = appearCount;
    }

    public Integer getDurationMinutes() {
        return durationMinutes;
    }

    public void setDurationMinutes(Integer durationMinutes) {
        this.durationMinutes = durationMinutes;
    }

    public Boolean getIsSpecial() {
        return isSpecial;
    }

    public void setIsSpecial(Boolean isSpecial) {
        this.isSpecial = isSpecial;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
    }
}
