package com.example.hotspotanalyzer.service.impl;

import com.example.hotspotanalyzer.mapper.CrossPlatformTopicMapper;
import com.example.hotspotanalyzer.service.CrossPlatformTopicService;
import com.example.hotspotanalyzer.vo.CrossPlatformHotspotVO;
import com.example.hotspotanalyzer.vo.CrossPlatformTopicVO;
import com.example.hotspotanalyzer.vo.PageResponse;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class CrossPlatformTopicServiceImpl implements CrossPlatformTopicService {

    private static final int DEFAULT_PAGE_SIZE = 10;
    private static final int MAX_PAGE_SIZE = 100;

    private final CrossPlatformTopicMapper crossPlatformTopicMapper;

    public CrossPlatformTopicServiceImpl(CrossPlatformTopicMapper crossPlatformTopicMapper) {
        this.crossPlatformTopicMapper = crossPlatformTopicMapper;
    }

    @Override
    public PageResponse<CrossPlatformTopicVO> getTopicsPage(String platformCombo, Integer page, Integer pageSize, Boolean todayOnly) {
        List<String> platforms = parsePlatformCombo(platformCombo);
        int safePage = page == null || page <= 0 ? 1 : page;
        int safePageSize = normalizePageSize(pageSize);
        int offset = (safePage - 1) * safePageSize;

        Long total = crossPlatformTopicMapper.countTopics(platforms, todayOnly);
        List<CrossPlatformTopicVO> records = crossPlatformTopicMapper.findTopicsPage(platforms, offset, safePageSize, todayOnly);
        
        for (CrossPlatformTopicVO topic : records) {
            List<CrossPlatformHotspotVO> hotspots = crossPlatformTopicMapper.findHotspotsByTopicId(topic.getId());
            topic.setHotspots(hotspots);
        }
        
        return new PageResponse<>(records, total, safePage, safePageSize);
    }

    @Override
    public CrossPlatformTopicVO getTopicById(Long id) {
        CrossPlatformTopicVO topic = crossPlatformTopicMapper.findTopicById(id);
        if (topic == null) {
            return null;
        }

        List<CrossPlatformHotspotVO> hotspots = crossPlatformTopicMapper.findHotspotsByTopicId(id);
        topic.setHotspots(hotspots);
        return topic;
    }

    private List<String> parsePlatformCombo(String platformCombo) {
        if (!StringUtils.hasText(platformCombo) || "all".equalsIgnoreCase(platformCombo)) {
            return new ArrayList<>();
        }

        if ("three".equalsIgnoreCase(platformCombo)) {
            return Arrays.asList("weibo", "douyin", "bilibili");
        }

        Set<String> allowed = new LinkedHashSet<>(Arrays.asList("weibo", "douyin", "bilibili"));
        return Arrays.stream(platformCombo.split(","))
                .map(String::trim)
                .filter(StringUtils::hasText)
                .filter(allowed::contains)
                .distinct()
                .collect(Collectors.toList());
    }

    private int normalizePageSize(Integer pageSize) {
        if (pageSize == null || pageSize <= 0) {
            return DEFAULT_PAGE_SIZE;
        }
        return Math.min(pageSize, MAX_PAGE_SIZE);
    }
}
