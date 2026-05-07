package com.example.hotspotanalyzer.service;

import com.example.hotspotanalyzer.entity.Hotspot;
import com.example.hotspotanalyzer.vo.DailyTopHotVO;
import com.example.hotspotanalyzer.vo.HistoryHotVO;
import com.example.hotspotanalyzer.vo.PlatformStatsVO;

import java.util.List;

public interface HotspotService {

    List<Hotspot> getAllHotspots();

    List<Hotspot> getHotspotsByPlatform(String platform);

    Hotspot getHotspotById(Long id);

    List<Hotspot> searchHotspots(String keyword);

    List<PlatformStatsVO> getPlatformStats();

    List<DailyTopHotVO> getDailyTopByPlatform(String platform, Integer limit);

    List<HistoryHotVO> getHistoryByPlatformAndDate(String platform, String date);
}