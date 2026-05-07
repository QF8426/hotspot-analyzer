package com.example.hotspotanalyzer.service.impl;

import com.example.hotspotanalyzer.entity.HotspotTrend;
import com.example.hotspotanalyzer.mapper.HotspotTrendMapper;
import com.example.hotspotanalyzer.service.HotspotTrendService;
import com.example.hotspotanalyzer.vo.TrendVO;
import org.springframework.stereotype.Service;

import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Service
public class HotspotTrendServiceImpl implements HotspotTrendService {

    private final HotspotTrendMapper hotspotTrendMapper;

    public HotspotTrendServiceImpl(HotspotTrendMapper hotspotTrendMapper) {
        this.hotspotTrendMapper = hotspotTrendMapper;
    }

    @Override
    public TrendVO getTrendByHotspotId(Long hotspotId) {
        List<HotspotTrend> list = hotspotTrendMapper.findByHotspotId(hotspotId);

        List<String> times = new ArrayList<>();
        List<Long> hotValues = new ArrayList<>();
        List<Integer> rankValues = new ArrayList<>();

        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("HH:mm:ss");

        for (HotspotTrend item : list) {
            String time = item.getRecordTime().format(formatter);
            times.add(time);
            hotValues.add(item.getHotValue());
            rankValues.add(item.getRankNum());
        }

        TrendVO vo = new TrendVO();
        vo.setTimes(times);
        vo.setHotValues(hotValues);
        vo.setRankValues(rankValues);

        return vo;
    }
}