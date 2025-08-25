<!--
 * ProMarkdown组件
 * 一个高度可定制的Markdown渲染组件，支持表格、配图、流程图、时序图、状态图、UML图、数学公式等
 * 使用方式: <ProMarkdown :content="content" />
 * @author FastbuildAI
-->

<script setup lang="ts">
import "katex/dist/katex.min.css";

import { watch, ref, onMounted, onBeforeUnmount } from "vue";

import { useMarkdown } from "./composables/useMarkdown";

interface Props {
    /** 内容 */
    content?: string;
    /** 是否保持 details 元素的展开状态 */
    preserveDetailsState?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    content: "",
    preserveDetailsState: true, // 默认开启保持状态
});

const { result, render, handleClick } = useMarkdown();

// 存储 details 元素的展开状态
const detailsStates = ref<Record<string, boolean>>({});
let timeoutId: number | null = null; // 用于存储定时器ID

/** 保存当前 details 状态 */
const saveDetailsStates = () => {
    if (!props.preserveDetailsState) return;
    
    const container = document.querySelector('.pro-markdown > div');
    if (container) {
        const detailsElements = container.querySelectorAll('details');
        detailsElements.forEach((detail, index) => {
            detailsStates.value[`detail-${index}`] = detail.hasAttribute('open');
        });
    }
};

/** 恢复 details 状态并根据内容和新逻辑智能控制展开/折叠 */
const restoreDetailsStates = () => {
    if (!props.preserveDetailsState) return;
    
    // 清除之前的定时器，防止重复折叠
    if (timeoutId !== null) {
        clearTimeout(timeoutId);
        timeoutId = null;
    }

    setTimeout(() => {
        const container = document.querySelector('.pro-markdown > div');
        if (container) {
            const detailsElements = container.querySelectorAll('details');
            let foundDone = false; // 标志位，用于追踪是否已找到包含DONE的<details>

            detailsElements.forEach((detail) => {
                const summary = detail.querySelector('summary');
                const summaryText = summary ? summary.textContent || '' : '';
                const content = detail.textContent || '';

                // 检查是否是“整体执行过程”块
                if (summaryText.includes('整体执行过程')) {
                    detail.setAttribute('open', ''); // 默认展开 "整体执行过程"
                    // 检查内容是否包含 DONE
                    if (content.includes('DONE')) {
                        foundDone = true;
                    }
                } else {
                    detail.removeAttribute('open'); // 其他 details 默认折叠
                }

                // 移除之前可能添加的事件监听器，防止重复绑定
                detail.removeEventListener('dblclick', handleDetailsDoubleClick);
                // 为每个 details 添加双击事件监听器
                detail.addEventListener('dblclick', handleDetailsDoubleClick);
            });

            // 如果找到了包含 DONE 的块，则设置定时器，在3秒后折叠所有 details
            if (foundDone) {
                timeoutId = window.setTimeout(() => {
                    detailsElements.forEach(detail => {
                        detail.removeAttribute('open');
                    });
                }, 3000); // 3秒延迟
            }
        }
    }, 0);
};

/** 处理 details 元素双击事件的函数 */
const handleDetailsDoubleClick = (event: Event) => {
    const target = event.currentTarget as HTMLDetailsElement | null;
    if (target) {
        if (target.hasAttribute('open')) {
            target.removeAttribute('open');
        } else {
            target.setAttribute('open', '');
        }
    }
};

/** 初始渲染 */
render(props.content);

/** 监听内容变化渲染 */
watch(
    () => props.content,
    (newContent) => {
        saveDetailsStates(); // 保存当前状态
        render(newContent);
        restoreDetailsStates(); // 恢复状态并智能控制
    },
);

// 在组件卸载前清除定时器和事件监听器
onBeforeUnmount(() => {
    if (timeoutId !== null) {
        clearTimeout(timeoutId);
    }
    // 清理所有添加的事件监听器
    const container = document.querySelector('.pro-markdown > div');
    if (container) {
        const detailsElements = container.querySelectorAll('details');
        detailsElements.forEach(detail => {
            detail.removeEventListener('dblclick', handleDetailsDoubleClick);
        });
    }
});

defineExpose({
    /** 手动重新渲染 */
    refresh: () => {
        saveDetailsStates();
        render(props.content);
        restoreDetailsStates();
    },
});
</script>

<template>
    <!--
        SSR 回退：
        1. 在服务端渲染阶段，v-dompurify-html 指令不会执行，因此先用插值方式渲染纯文本内容。
        2. 客户端挂载完成后，v-dompurify-html 指令会将 innerHTML 覆盖为已消毒的 Markdown 渲染结果。
        这样即可避免 SSR 阶段页面为空的问题。
    -->
    <ClientOnly>
        <div class="pro-markdown">
            <slot name="before" />
            <div @click="handleClick($event)" v-dompurify-html:markdown="result" />
            <slot name="after" />
        </div>

        <template #placeholder>
            <pre class="whitespace-pre-line">{{ props.content }}</pre>
        </template>
    </ClientOnly>
</template>

<style>
/* 导入样式 */
@import "./styles/markdown.css";
</style>