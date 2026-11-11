-- 컨테이너가 처음 만들어질 때(빈 볼륨일 때) 한 번만 실행된다
CREATE TABLE IF NOT EXISTS system_metrics (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    hostname    VARCHAR(100) NOT NULL,
    cpu_usage   FLOAT        NOT NULL,
    mem_usage   FLOAT        NOT NULL,
    disk_usage  FLOAT        NOT NULL,
    is_alert    TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at),
    INDEX idx_host_created (hostname, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
