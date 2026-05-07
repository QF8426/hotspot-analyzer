package com.example.hotspotanalyzer;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.example.hotspotanalyzer.mapper")
public class HotspotAnalyzerApplication {
    public static void main(String[] args) {
        SpringApplication.run(HotspotAnalyzerApplication.class, args);
    }
}