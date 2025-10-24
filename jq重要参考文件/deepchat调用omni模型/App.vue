<script setup lang="ts">
import { computed, ref, unref, onMounted, nextTick } from 'vue'
import 'deep-chat'
import 'katex/dist/katex.min.css'
declare global {
  interface Window {
    katex: typeof import('katex').default
  }
}
// 声明 DeepChat 实例类型（可选但推荐）
interface DeepChatInstance {
  refreshMessages(): void
}
const chatRef = ref<DeepChatInstance | null>(null)
onMounted(async () => {
  try {
    const { default: katex } = await import('katex')
    window.katex = katex
    // 等待下一次 tick 确保 DOM 稳定
    await nextTick()
    chatRef.value?.refreshMessages()
  } catch (error) {
    console.warn('KaTeX load failed', error)
  } finally {
    loading.value = false // KaTeX 加载完再显示 chat
  }
})

const models = ref(['qwen3', 'qwenvl', 'omni', 'jqagent', 'default'])
const model = ref('default')

const realUrl = ref({
  qwen3: 'http://10.1.150.105:3000/v1/chat/completions',
  qwenvl: 'http://10.1.150.105:3000/v1/chat/completions',
  omni: 'http://10.1.150.105:3000/v1/chat/completions',
  jqagent: 'http://10.1.150.105:3000/v1/chat/completions',
  default: 'http://10.1.150.105:3000/v1/chat/completions',
  // default: 'http://10.1.150.105:8601/v1/chat/completions',
})

const loading = ref(true) // 初始为 true，隐藏 chat

const connect = computed(() => {
  return {
    url: 'http://10.1.150.105:3000/v1/chat/completions', // http://10.1.150.105:8601/v1/chat/completions
    method: 'post',
    headers: {
      'Content-Type': 'application/json',
      // Authorization: 'Bearer abc123',
    },
    additionalBodyProps: {
      model: unref(model), // 'qwen3' 'qwenvl' || 'default' 'jqagent'
    },
    stream: true,
  }
})

const remarkable = {
  html: true,
  typographer: true,
  math: true,
}

const history = ref([])
const requestInterceptor = (req) => {
  console.log('req 1 原始请求body内容=> ', req.body)
  // console.log('req 1 原始请求body内容=> ')
  console.table(req.body)
  const m = unref(model)
  if (m == 'jqagent') {
    req.body.model = 'default'
  } else {
    req.body.model = m
  }
  req.body.messages = req.body.messages.map((msg) => {
    let { content, role } = msg
    if (Array.isArray(content)) {
      content = content.map((c) => {
        const { type, image_url, ...rest } = c
        if (type == 'image_url' && /^data:audio/.test(image_url.url)) {
          return { type: 'audio_url', audio_url: { url: image_url.url }, ...rest }
        }
        return c
      })
    }
    return { content, role }
  })

  console.log('req 2 => ', req)
}

// 微积分的原理、数学公式及解释【凡涉及数学公式，必须使用Markdown语法,且支持 KaTeX 渲染】
// 正态分布的原理、数学公式及解释【凡涉及数学公式，必须使用Markdown语法,且支持 KaTeX 渲染】

const responseInterceptor = (res) => {
  if (res?.choices?.[0]?.delta?.content) {
    let content = res.choices[0].delta.content
    // --- 核心转换逻辑 ---
    // 将模型输出的块级 LaTeX 公式 \[ ... \] 转换为 Deep Chat 识别的 $$ ... $$
    // 使用 g (global) 和 s (dotall) 标志确保匹配跨行的内容
    content = content.replace(/\\\[(.*?)\\\]/gs, (_, math) => `$$${math.trim()}$$`)
    // 将模型可能误用的行内 LaTeX 公式 ( ... ) 转换为 Deep Chat 识别的 $ ... $
    // 注意：这会将所有独立的 ( ... ) 对转换为数学公式，如果这不是你想要的，需要更复杂的正则
    // 但根据你的例子，这似乎就是模型的意图
    content = content.replace(/\((.*?)\)/gs, (_, math) => `$${math.trim()}$`)
    // --- 更新响应内容 ---
    res.choices[0].delta.content = content
  }
  return res
}

const messageStyles = {
  default: {
    shared: {
      bubble: { maxWidth: '100%', backgroundColor: 'white' },
    },
    // ai: { bubble: { backgroundColor: "#3cbe3c" } },
    user: { bubble: { backgroundColor: '#6767ff' } },
    // bob: { bubble: { backgroundColor: "#ffa500" } },
  },
}
</script>

<style scoped></style>
<template>
  <div class="flex h-screen flex-col items-center border-0 border-dashed border-red-500">
    "Url:"{{ realUrl[model] }} "Model": {{ model }}
    <div class="!space-x-4 px-4 py-2">
      <button
        v-for="item in models"
        :key="item"
        class="m-2 rounded-full border px-4 py-2 font-bold"
        :class="model === item ? 'bg-blue-500 text-white' : ''"
        @click="model = item"
      >
        {{ item }}
      </button>
    </div>
    <!-- <h1 class="!mt-4 py-4">Deep Chat v2.3.0 updated!</h1> -->
    <h1>Deep Chat v2.3.0 updated!</h1>

    <deep-chat
      v-if="!loading"
      ref="chatRef"
      images="true"
      camera="true"
      focusMode="true"
      speechToText='{"audio": {"autoPlay": true}}'
      :audio="{
        format: 'wav',
        files: { acceptedFormats: '.wav' },
      }"
      :microphone="{
        format: 'wav',
        files: { acceptedFormats: '.wav' },
        button: { position: 'inside-left' },
      }"
      :mixedFiles="{
        maxNumberOfFiles: 3,
        files: { acceptedFormats: '.txt, .pdf,.doc,.docx' },
      }"
      :remarkable="remarkable"
      :directconnection="{
        openAI: {
          key: 'sk-0S7bV3oaznhuevN899Db0cDa20Ae4c5485Ce5862A86063C8',
          chat: true,
          speechToText: false,
          textToSpeech: false,
          realtime: false,
          assistant: false,
        },
      }"
      :requestInterceptor="requestInterceptor"
      :responseInterceptor="responseInterceptor"
      :connect="connect"
      :history="history"
      :messageStyles="messageStyles"
      style="
        width: 1200px;
        height: 600px;
        border-radius: 10px;
        border-color: #dcdcdc;
        background-color: #fff;
      "
    />
  </div>
</template>
