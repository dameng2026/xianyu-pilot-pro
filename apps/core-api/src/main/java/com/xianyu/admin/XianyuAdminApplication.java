package com.xianyu.admin;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

@SpringBootApplication
@EnableScheduling
public class XianyuAdminApplication {
    public static void main(String[] args) {
        SpringApplication.run(XianyuAdminApplication.class, args);
    }

    /**
     * 多线程调度池：默认单线程会导致 @Scheduled 任务串行执行，
     * autoSyncOrdersFromXianyu 的串行 HTTP 会阻塞 processPendingDeliveries 发货任务。
     * 配置 4 线程确保定时任务并行、不互相阻塞。
     */
    @Bean
    public ThreadPoolTaskScheduler taskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(4);
        scheduler.setThreadNamePrefix("scheduled-");
        scheduler.setWaitForTasksToCompleteOnShutdown(true);
        scheduler.setAwaitTerminationSeconds(30);
        return scheduler;
    }
}
