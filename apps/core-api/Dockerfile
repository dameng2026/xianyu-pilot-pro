FROM maven:3.9.16-eclipse-temurin-17 AS build
WORKDIR /app
# 配置阿里云 Maven 镜像源加速依赖下载
RUN mkdir -p /root/.m2 && cat > /root/.m2/settings.xml <<'EOF'
<settings>
  <mirrors>
    <mirror>
      <id>aliyun</id>
      <mirrorOf>central</mirrorOf>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
EOF
COPY pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
COPY src ./src
RUN mvn -q -Dmaven.test.skip=true package

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
COPY --from=build --chown=app:app /app/target/xianyu-assistant-admin-backend-*.jar app.jar
USER 10001:10001
EXPOSE 18080
ENTRYPOINT ["java", "-jar", "app.jar"]
