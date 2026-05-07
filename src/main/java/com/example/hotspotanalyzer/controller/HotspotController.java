package com.example.hotspotanalyzer.controller;

import com.example.hotspotanalyzer.common.ApiResponse;
import com.example.hotspotanalyzer.entity.Hotspot;
import com.example.hotspotanalyzer.service.HotspotService;
import com.example.hotspotanalyzer.service.HotspotTrendService;
import com.example.hotspotanalyzer.vo.DailyTopHotVO;
import com.example.hotspotanalyzer.vo.HistoryHotVO;
import com.example.hotspotanalyzer.vo.TrendVO;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class HotspotController {

    private final HotspotService hotspotService;
    private final HotspotTrendService hotspotTrendService;

    public HotspotController(HotspotService hotspotService,
                             HotspotTrendService hotspotTrendService) {
        this.hotspotService = hotspotService;
        this.hotspotTrendService = hotspotTrendService;
    }

    @GetMapping("/api/hotspots")
    public ApiResponse<List<Hotspot>> getAllHotspots() {
        return ApiResponse.success(hotspotService.getAllHotspots());
    }

    @GetMapping("/api/hotspots/platform/{platform}")
    public ApiResponse<List<Hotspot>> getHotspotsByPlatform(@PathVariable String platform) {
        return ApiResponse.success(hotspotService.getHotspotsByPlatform(platform));
    }

    @GetMapping("/api/hotspots/{id}")
    public ApiResponse<Hotspot> getHotspotById(@PathVariable Long id) {
        return ApiResponse.success(hotspotService.getHotspotById(id));
    }

    @GetMapping("/api/hotspots/search")
    public ApiResponse<List<Hotspot>> searchHotspots(@RequestParam String keyword) {
        return ApiResponse.success(hotspotService.searchHotspots(keyword));
    }

    @GetMapping("/api/hotspots/{id}/trend")
    public ApiResponse<TrendVO> getTrend(@PathVariable Long id) {
        return ApiResponse.success(hotspotTrendService.getTrendByHotspotId(id));
    }

    @GetMapping("/api/hotspots/platform/{platform}/daily-top")
    public ApiResponse<List<DailyTopHotVO>> getDailyTopByPlatform(
            @PathVariable String platform,
            @RequestParam(required = false) Integer limit) {
        return ApiResponse.success(hotspotService.getDailyTopByPlatform(platform, limit));
    }

    @GetMapping("/api/hotspots/platform/{platform}/history")
    public ApiResponse<List<HistoryHotVO>> getHistoryByPlatformAndDate(
            @PathVariable String platform,
            @RequestParam String date) {
        return ApiResponse.success(hotspotService.getHistoryByPlatformAndDate(platform, date));
    }
}