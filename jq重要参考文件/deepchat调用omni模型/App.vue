<script setup lang="ts">
import { computed, ref, unref } from 'vue'
import 'deep-chat'

const modes = ref(['qwen3', 'qwenvl', 'omni', 'jqagent', 'default'])
const model = ref('default')

const realUrl = ref({
  qwen3: 'http://10.1.150.105:3000/v1/chat/completions',
  qwenvl: 'http://10.1.150.105:3000/v1/chat/completions',
  omni: 'http://10.1.150.105:3000/v1/chat/completions',
  jqagent: 'http://10.1.150.105:3000/v1/chat/completions',
  default: 'http://10.1.150.105:3000/v1/chat/completions',
  // default: 'http://10.1.150.105:8601/v1/chat/completions',
})

const loading = ref(false)

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
const responseInterceptor = (res) => {
  // return res?.choices?.map((r) => {
  //   return { html: r.delta?.content } as Response;
  // });
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
        v-for="item in modes"
        :key="item"
        class="m-2 rounded-full border px-4 py-2 font-bold"
        :class="model === item ? 'bg-blue-500 text-white' : ''"
        @click="model = item"
      >
        {{ item }}
      </button>
    </div>
    <h1 class="!mt-4 py-4">Deep Chat</h1>

    <deep-chat
      v-if="!loading"
      images="true"
      camera="true"
      mixedFiles="false"
      :audio="{
        format: 'wav',
        files: { acceptedFormats: '.wav' },
      }"
      :microphone="{
        format: 'wav',
        button: { position: 'inside-left' },
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
