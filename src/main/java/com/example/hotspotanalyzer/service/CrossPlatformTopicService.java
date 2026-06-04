package com.example.hotspotanalyzer.service;

import com.example.hotspotanalyzer.vo.CrossPlatformTopicVO;
import com.example.hotspotanalyzer.vo.PageResponse;

public interface CrossPlatformTopicService {

    PageResponse<CrossPlatformTopicVO> getTopicsPage(String platformCombo, Integer page, Integer pageSize, Boolean todayOnly);

    CrossPlatformTopicVO getTopicById(Long id);
}
