package com.example.hotspotanalyzer.service.impl;

import com.example.hotspotanalyzer.entity.Hotspot;
import com.example.hotspotanalyzer.mapper.HotspotMapper;
import com.example.hotspotanalyzer.service.HotspotService;
import com.example.hotspotanalyzer.vo.DailyTopHotVO;
import com.example.hotspotanalyzer.vo.HistoryHotVO;
import com.example.hotspotanalyzer.vo.PlatformStatsVO;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class HotspotServiceImpl implements HotspotService {

    private final HotspotMapper hotspotMapper;

    public HotspotServiceImpl(HotspotMapper hotspotMapper) {
        this.hotspotMapper = hotspotMapper;
    }

    @Override
    public List<Hotspot> getAllHotspots() {
        return hotspotMapper.findAll();
    }

    @Override
    public List<Hotspot> getHotspotsByPlatform(String platform) {
        return hotspotMapper.findByPlatform(platform);
    }

    @Override
    public Hotspot getHotspotById(Long id) {
        return hotspotMapper.findById(id);
    }

    @Override
    public List<Hotspot> searchHotspots(String keyword) {
        return hotspotMapper.searchByKeyword(keyword);
    }

    @Override
    public List<PlatformStatsVO> getPlatformStats() {
        return hotspotMapper.countByPlatform();
    }

    @Override
    public List<DailyTopHotVO> getDailyTopByPlatform(String platform, Integer limit) {
        if (limit == null || limit <= 0) {
            limit = 10;
        }
        return hotspotMapper.findDailyTopByPlatform(platform, limit);
    }

    @Override
    public List<HistoryHotVO> getHistoryByPlatformAndDate(String platform, String date) {
        return hotspotMapper.findHistoryByPlatformAndDate(platform, date);
    }
}