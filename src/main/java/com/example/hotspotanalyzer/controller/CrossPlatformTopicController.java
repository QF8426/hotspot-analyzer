package com.example.hotspotanalyzer.controller;

import com.example.hotspotanalyzer.common.ApiResponse;
import com.example.hotspotanalyzer.service.CrossPlatformTopicService;
import com.example.hotspotanalyzer.vo.CrossPlatformTopicVO;
import com.example.hotspotanalyzer.vo.PageResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CrossPlatformTopicController {

    private final CrossPlatformTopicService crossPlatformTopicService;

    public CrossPlatformTopicController(CrossPlatformTopicService crossPlatformTopicService) {
        this.crossPlatformTopicService = crossPlatformTopicService;
    }

    @GetMapping("/api/cross-platform/topics")
    public ApiResponse<PageResponse<CrossPlatformTopicVO>> getTopics(
            @RequestParam(required = false) String platformCombo,
            @RequestParam(required = false, defaultValue = "1") Integer page,
            @RequestParam(required = false, defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) Boolean todayOnly) {
        return ApiResponse.success(crossPlatformTopicService.getTopicsPage(platformCombo, page, pageSize, todayOnly));
    }

    @GetMapping("/api/cross-platform/topics/{id}")
    public ApiResponse<CrossPlatformTopicVO> getTopicById(@PathVariable Long id) {
        return ApiResponse.success(crossPlatformTopicService.getTopicById(id));
    }
}
