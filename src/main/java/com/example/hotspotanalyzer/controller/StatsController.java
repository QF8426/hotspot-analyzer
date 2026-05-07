package com.example.hotspotanalyzer.controller;

import com.example.hotspotanalyzer.common.ApiResponse;
import com.example.hotspotanalyzer.service.HotspotService;
import com.example.hotspotanalyzer.vo.PlatformStatsVO;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class StatsController {

    private final HotspotService hotspotService;

    public StatsController(HotspotService hotspotService) {
        this.hotspotService = hotspotService;
    }

    @GetMapping("/api/stats/platform")
    public ApiResponse<List<PlatformStatsVO>> getPlatformStats() {
        return ApiResponse.success(hotspotService.getPlatformStats());
    }
}