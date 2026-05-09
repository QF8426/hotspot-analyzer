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
        // limit 为空时返回今日全部热点；首页仍可传 limit=10 获取 Top10。
        // 这样平台页“查看今日全部热点”不会再被前端固定 100/200 条截断。
        return hotspotMapper.findDailyTopByPlatform(platform, limit);
    }

    @Override
    public List<HistoryHotVO> getHistoryByPlatformAndDate(String platform, String date) {
        return hotspotMapper.findHistoryByPlatformAndDate(platform, date);
    }
}