package com.example.hotspotanalyzer.service;

import com.example.hotspotanalyzer.vo.TrendVO;

public interface HotspotTrendService {

    TrendVO getTrendByHotspotId(Long hotspotId);
}