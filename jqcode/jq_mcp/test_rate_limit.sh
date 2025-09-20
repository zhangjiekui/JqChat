#!/bin/bash

# ========== 配置 ==========
# 临时禁用代理
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
TARGET_HOST="10.1.150.105"
TARGET_PORT="8601"
AUTH_TOKEN="Bearer abc123"
LOG_FILE="/data/projects/JqChatV2/JqChat/jqcode/jq_mcp/full_rate_limit_test_$(date +%Y%m%d_%H%M%S).log"

# 清空日志（可选）
> "$LOG_FILE"

echo "📋 测试目标: http://$TARGET_HOST:$TARGET_PORT"
echo "🔐 认证令牌: $AUTH_TOKEN"
echo "📄 日志文件: $LOG_FILE"
echo

# ========== 测试 1: /v1/chat/completions (1/minute 限流 + 压测) ==========
{
    echo "🚀 开始测试 [1/minute]: POST /v1/chat/completions (压测触发限流)"
    echo "=========================================="
    echo

    # 请求体（stream: "True" 或 "False" 都支持，你后端有处理）
    DATA='{
        "model": "default",
        "messages": [
            {
                "role": "user",
                "content": "Hello, this is rate limit test!"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "stream": "False",
        "metadata": {
            "userInfo": {
                "userName": "rate_test_user",
                "userId": "test_001"
            },
            "memory": "False",
            "rewrite": "False"
        }
    }'

    for i in {1..5}; do
        echo "[$(date '+%H:%M:%S')] 🔁 第 $i 次请求到 /v1/chat/completions"
        echo "----------------------------------------"

        curl -v --noproxy "*" -X POST \
             -H "Authorization: $AUTH_TOKEN" \
             -H "Content-Type: application/json" \
             -d "$DATA" \
             "http://$TARGET_HOST:$TARGET_PORT/v1/chat/completions" \
             2>&1 | tee -a "$LOG_FILE"

        if [ $i -lt 3 ]; then
            sleep 1  # 1分钟限流，3次/3秒 → 必触发限流
        fi
    done

    echo
    echo "✅ /v1/chat/completions 测试完成"
    echo
} | tee -a "$LOG_FILE"


# ========== 测试 2: /v1/models (1/second 限流) ==========
{
    echo "🚀 开始测试 [1/second]: GET /v1/models"
    echo "=========================================="
    echo

    for i in {1..5}; do
        echo "[$(date '+%H:%M:%S')] 🔁 第 $i 次请求到 /v1/models"
        echo "----------------------------------------"

        curl -v --noproxy "*" -H "Authorization: $AUTH_TOKEN" \
             "http://$TARGET_HOST:$TARGET_PORT/v1/models" \
             2>&1 | tee -a "$LOG_FILE"

        if [ $i -lt 3 ]; then
            sleep 0.1
        fi
    done

    echo
    echo "✅ /v1/models 测试完成"
    echo
} | tee -a "$LOG_FILE"

# ========== 汇总报告 ==========
echo "📊 ===== 最终测试报告 =====" | tee -a "$LOG_FILE"
echo "✅ GET /v1/models 测试结果（应看到 429）：" | tee -a "$LOG_FILE"
grep -A 1 "第 [1-3] 次请求到 /v1/models" "$LOG_FILE" | grep "< HTTP" | head -3 | tee -a "$LOG_FILE"

echo | tee -a "$LOG_FILE"
echo "✅ POST /v1/chat/completions 测试结果（应看到 429）：" | tee -a "$LOG_FILE"
grep -A 1 "第 [1-3] 次请求到 /v1/chat/completions" "$LOG_FILE" | grep "< HTTP" | head -3 | tee -a "$LOG_FILE"

echo | tee -a "$LOG_FILE"
echo "✅ 429 触发次数统计：" | tee -a "$LOG_FILE"
grep "< HTTP/1.1 429" "$LOG_FILE" | wc -l | xargs echo "共触发 429 次: " | tee -a "$LOG_FILE"

echo | tee -a "$LOG_FILE"
echo "🎉 全部测试完成！详细日志见：$LOG_FILE" | tee -a "$LOG_FILE"