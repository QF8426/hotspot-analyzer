package com.example.hotspotanalyzer.service;

import com.example.hotspotanalyzer.vo.CrossPlatformTopicVO;

import java.util.List;

public interface CrossPlatformTopicService {

    List<CrossPlatformTopicVO> getTopics(String platformCombo, Integer limit, Boolean todayOnly);

    CrossPlatformTopicVO getTopicById(Long id);
}
