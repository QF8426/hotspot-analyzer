package com.example.hotspotanalyzer.vo;

public class PlatformStatsVO {

    private String platform;
    private Long count;

    public PlatformStatsVO() {
    }

    public PlatformStatsVO(String platform, Long count) {
        this.platform = platform;
        this.count = count;
    }

    public String getPlatform() {
        return platform;
    }

    public void setPlatform(String platform) {
        this.platform = platform;
    }

    public Long getCount() {
        return count;
    }

    public void setCount(Long count) {
        this.count = count;
    }
}
