package com.example.hotspotanalyzer.mapper;

import com.example.hotspotanalyzer.entity.Hotspot;
import com.example.hotspotanalyzer.vo.DailyTopHotVO;
import com.example.hotspotanalyzer.vo.HistoryHotVO;
import com.example.hotspotanalyzer.vo.PlatformStatsVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface HotspotMapper {

    List<Hotspot> findAll();

    List<Hotspot> findByPlatform(@Param("platform") String platform);

    Hotspot findById(@Param("id") Long id);

    List<Hotspot> searchByKeyword(@Param("keyword") String keyword);

    List<PlatformStatsVO> countByPlatform();

    List<DailyTopHotVO> findDailyTopByPlatform(@Param("platform") String platform,
                                               @Param("limit") Integer limit);

    List<HistoryHotVO> findHistoryByPlatformAndDate(@Param("platform") String platform,
                                                    @Param("date") String date);
}