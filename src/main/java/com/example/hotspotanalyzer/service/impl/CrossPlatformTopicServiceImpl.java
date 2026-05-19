package com.example.hotspotanalyzer.service.impl;

import com.example.hotspotanalyzer.mapper.CrossPlatformTopicMapper;
import com.example.hotspotanalyzer.service.CrossPlatformTopicService;
import com.example.hotspotanalyzer.vo.CrossPlatformHotspotVO;
import com.example.hotspotanalyzer.vo.CrossPlatformTopicVO;
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

    private static final int DEFAULT_LIMIT = 50;
    private static final int MAX_LIMIT = 200;

    private final CrossPlatformTopicMapper crossPlatformTopicMapper;

    public CrossPlatformTopicServiceImpl(CrossPlatformTopicMapper crossPlatformTopicMapper) {
        this.crossPlatformTopicMapper = crossPlatformTopicMapper;
    }

    @Override
    public List<CrossPlatformTopicVO> getTopics(String platformCombo, Integer limit, Boolean todayOnly) {
        List<String> platforms = parsePlatformCombo(platformCombo);
        int safeLimit = normalizeLimit(limit);

        List<CrossPlatformTopicVO> topics = crossPlatformTopicMapper.findTopics(platforms, safeLimit, todayOnly);
        for (CrossPlatformTopicVO topic : topics) {
            List<CrossPlatformHotspotVO> hotspots = crossPlatformTopicMapper.findHotspotsByTopicId(topic.getId());
            topic.setHotspots(hotspots);
        }
        return topics;
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

    private int normalizeLimit(Integer limit) {
        if (limit == null || limit <= 0) {
            return DEFAULT_LIMIT;
        }
        return Math.min(limit, MAX_LIMIT);
    }
}
