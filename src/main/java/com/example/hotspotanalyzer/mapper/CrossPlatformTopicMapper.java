package com.example.hotspotanalyzer.mapper;

import com.example.hotspotanalyzer.vo.CrossPlatformHotspotVO;
import com.example.hotspotanalyzer.vo.CrossPlatformTopicVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface CrossPlatformTopicMapper {

    List<CrossPlatformTopicVO> findTopics(@Param("platforms") List<String> platforms,
                                          @Param("limit") Integer limit,
                                          @Param("todayOnly") Boolean todayOnly);

    CrossPlatformTopicVO findTopicById(@Param("id") Long id);

    List<CrossPlatformHotspotVO> findHotspotsByTopicId(@Param("topicId") Long topicId);
}
