# openclaw安装和配置
## 配置文件：/root/.openclaw/openclaw.json
```
{
  "meta": {
    "lastTouchedVersion": "2026.2.9",
    "lastTouchedAt": "2026-02-11T08:23:53.449Z"
  },
  "wizard": {
    "lastRunAt": "2026-02-11T06:58:47.877Z",
    "lastRunVersion": "2026.2.9",
    "lastRunCommand": "onboard",
    "lastRunMode": "local"
  },
  "auth": {
    "profiles": {
      "minimax:default": {
        "provider": "minimax",
        "mode": "api_key"
      }
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "vllm": {
        "baseUrl": "http://10.1.150.105:3000/v1",
        "apiKey": "sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8",
        "api": "openai-completions",
        "models": [
          {
            "id": "jqagent",
            "name": "jqagent",
            "reasoning": false,
            "input": [
              "text"
            ],
            "cost": {
              "input": 0,
              "output": 0,
              "cacheRead": 0,
              "cacheWrite": 0
            },
            "contextWindow": 120000,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "vllm/jqagent"
      },
      "workspace": "/root/.openclaw/workspace",
      "compaction": {
        "mode": "safeguard"
      },
      "maxConcurrent": 4,
      "subagents": {
        "maxConcurrent": 8
      }
    }
  },
  "messages": {
    "ackReactionScope": "group-mentions"
  },
  "commands": {
    "native": "auto",
    "nativeSkills": "auto"
  },
  "gateway": {
    "port": 6090,
    "mode": "local",
    "bind": "lan",
    "controlUi": {
      "allowInsecureAuth": true
    },
    "auth": {
      "mode": "token",
      "token": "08c1551c7ee8ed4532b032519bdf46401a9cb44f9ed071c8",
      "password": "password"
    },
    "tailscale": {
      "mode": "off",
      "resetOnExit": false
    },
    "nodes": {
      "denyCommands": [
        "camera.snap",
        "camera.clip",
        "screen.record",
        "calendar.add",
        "contacts.add",
        "reminders.add"
      ]
    }
  },
  "skills": {
    "install": {
      "nodeManager": "npm"
    }
  },

  "channels": {
    "dingtalk": {
      "enabled": true,
      "clientId": "dinguvp3mbkjt6lghubs",
      "clientSecret": "KdWdrKxNMItShgiwtGlu06ixXT_S-GMuSdroIaE6_Hn_nDJmg5Me0UlCqlSz5fa0",
      "robotCode": "dinguvp3mbkjt6lghubs",
      "corpId": "dingd8b32bfb2b9da7b2",
      "agentId": "4265674907",
      "dmPolicy": "open",
      "groupPolicy": "open",
      "messageType": "markdown",
      "debug": false
    }
  },

  "plugins": {
    "entries": {
      "dingtalk": {
        "enabled": true
      }
    },
    "installs": {
      "dingtalk": {
        "source": "npm",
        "spec": "https://github.com/soimy/clawdbot-channel-dingtalk.git",
        "installPath": "/root/.openclaw/extensions/dingtalk",
        "version": "2.5.1",
        "installedAt": "2026-02-11T08:23:53.441Z"
      }
    }
  }
}

```

# 钉钉机器人开通和配置：https://ecloud.10086.cn/op-help-center/doc/article/98182