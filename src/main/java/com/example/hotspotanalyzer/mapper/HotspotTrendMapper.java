package com.example.hotspotanalyzer.mapper;

import com.example.hotspotanalyzer.entity.HotspotTrend;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface HotspotTrendMapper {

    List<HotspotTrend> findByHotspotId(@Param("hotspotId") Long hotspotId);
}