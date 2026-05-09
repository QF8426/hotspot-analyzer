package com.example.hotspotanalyzer.controller;

import com.example.hotspotanalyzer.common.ApiResponse;
import com.example.hotspotanalyzer.service.CrossPlatformTopicService;
import com.example.hotspotanalyzer.vo.CrossPlatformTopicVO;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class CrossPlatformTopicController {

    private final CrossPlatformTopicService crossPlatformTopicService;

    public CrossPlatformTopicController(CrossPlatformTopicService crossPlatformTopicService) {
        this.crossPlatformTopicService = crossPlatformTopicService;
    }

    @GetMapping("/api/cross-platform/topics")
    public ApiResponse<List<CrossPlatformTopicVO>> getTopics(
            @RequestParam(required = false) String platformCombo,
            @RequestParam(required = false) Integer limit) {
        return ApiResponse.success(crossPlatformTopicService.getTopics(platformCombo, limit));
    }

    @GetMapping("/api/cross-platform/topics/{id}")
    public ApiResponse<CrossPlatformTopicVO> getTopicById(@PathVariable Long id) {
        return ApiResponse.success(crossPlatformTopicService.getTopicById(id));
    }
}
