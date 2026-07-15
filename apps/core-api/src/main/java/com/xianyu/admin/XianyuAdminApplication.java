package com.xianyu.admin;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class XianyuAdminApplication {
    public static void main(String[] args) {
        SpringApplication.run(XianyuAdminApplication.class, args);
    }
}
