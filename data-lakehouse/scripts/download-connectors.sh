#!/bin/bash
# download-connectors.sh
# 下载 Flink Iceberg Connector JAR 和其他依赖
set -e

LIB_DIR="$(cd "$(dirname "$0")/../flink/lib" && pwd)"
mkdir -p "$LIB_DIR"

ICEBERG_VERSION="1.5.2"
FLINK_VERSION="1.18"
JAR_NAME="iceberg-flink-runtime-${FLINK_VERSION}-${ICEBERG_VERSION}.jar"

echo "下载 Flink Iceberg Connector..."
if [ -f "$LIB_DIR/$JAR_NAME" ]; then
    echo "JAR 已存在: $JAR_NAME"
else
    echo "正在下载 $JAR_NAME..."
    curl -L -o "$LIB_DIR/$JAR_NAME" \
        "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime/${FLINK_VERSION}-${ICEBERG_VERSION}/${JAR_NAME}"
    echo "下载完成!"
fi

echo ""
echo "已下载的 JAR 文件:"
ls -lh "$LIB_DIR"/*.jar 2>/dev/null || echo "无 JAR 文件"
echo ""
echo "注意: 将此 JAR 复制到 Flink 容器的 /opt/flink/lib/ 目录"
echo "或者重新构建镜像以包含此 JAR"
