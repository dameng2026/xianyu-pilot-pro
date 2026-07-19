FROM mcr.microsoft.com/playwright:v1.61.1-noble AS build

WORKDIR /app

COPY package*.json ./
RUN node -e "const v=process.versions.node.split('.')[0]; if(v!=='24') process.exit(1)" \
    && npm ci --no-audit --no-fund --strict-allow-scripts

COPY tsconfig.json ./
COPY src ./src
COPY migrations ./migrations

RUN npm run build && npm prune --omit=dev --no-audit --strict-allow-scripts

FROM mcr.microsoft.com/playwright:v1.61.1-noble

WORKDIR /app

RUN node -e "const v=process.versions.node.split('.')[0]; if(v!=='24') process.exit(1)"

# 安装 Xvfb：让线上 Linux Docker 也能运行有头 Chrome（复用本地 Windows 已验证有效的滑块求解路径）
# headless 模式下 Baxia 风控识别率极高，必须用有头模式 + 虚拟显示器
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        xauth \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build --chown=pwuser:pwuser /app/package.json /app/package-lock.json ./
COPY --from=build --chown=pwuser:pwuser /app/node_modules ./node_modules
COPY --from=build --chown=pwuser:pwuser /app/dist ./dist
COPY --from=build --chown=pwuser:pwuser /app/migrations ./migrations

ENV NODE_ENV=production
# 仍保留 HEADLESS=true 作为默认值，由 sliderSolver.ts 根据 DISPLAY 环境变量决定实际是否使用有头模式
ENV HEADLESS=true
ENV PORT=3001
USER pwuser

# 用 xvfb-run 包装启动命令，自动启动 Xvfb 虚拟显示器并设置 DISPLAY 环境变量
# -a: 自动选择可用的 display number，避免冲突
# -s: 传给 Xvfb 的参数，-screen 0 1280x800x24 提供足够分辨率供 Chrome 渲染
CMD ["xvfb-run", "-a", "-s", "-screen 0 1280x800x24 -ac", "node", "dist/server.js"]
