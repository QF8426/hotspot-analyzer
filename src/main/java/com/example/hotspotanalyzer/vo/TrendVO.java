package com.example.hotspotanalyzer.vo;

import lombok.Data;

import java.util.List;

@Data
public class TrendVO {
    private List<String> times;

    // 热度
    private List<Long> hotValues;

    // 排名
    private List<Integer> rankValues;
}
