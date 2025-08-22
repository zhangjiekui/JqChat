import { BaseController } from "@common/base/controllers/base.controller";
import { WebController } from "@common/decorators/controller.decorator";
import { Playground } from "@common/decorators/playground.decorator";
import { HttpExceptionFactory } from "@common/exceptions/http-exception.factory";
import { UserPlayground } from "@common/interfaces/context.interface";
import { validateArrayItems } from "@common/utils/helper.util";
import { ChatRequestDto } from "@modules/console/ai/dto/ai-chat-message.dto";
import {
  MessageRole,
  MessageType,
} from "@modules/console/ai/dto/ai-chat-record.dto";
import { McpToolCall } from "@modules/console/ai/entities/ai-chat-message.entity";
import { AiMcpServer } from "@modules/console/ai/entities/ai-mcp-server.entity";
import { ChatRole } from "@modules/console/ai/interfaces/ai-sdk.interface.js";
import { AiChatRecordService } from "@modules/console/ai/services/ai-chat-record.service";
import { AiMcpServerService } from "@modules/console/ai/services/ai-mcp-server.service";
import { AiModelService } from "@modules/console/ai/services/ai-model.service";
import { Body, Post, Res } from "@nestjs/common";
import { getProvider, TextGenerator } from "@sdk/ai";
import {
  convertMCPToolsToOpenAI,
  McpServer,
  MCPTool,
} from "@sdk/ai/utils/mcp/sse";
import { Response } from "express";
import {
  ChatCompletionFunctionTool,
  ChatCompletionMessageParam,
} from "openai/resources/index";

// import { ChatRole } from 'apps/server/src/modules/console/ai/interfaces/ai-sdk.interface.ts';

/**
 * AI聊天控制器（前台）
 *
 * 提供AI聊天对话功能，支持对话记录保存
 */
@WebController("ai-chat")
export class AiChatMessageController extends BaseController {
  constructor(
    private readonly AiChatRecordService: AiChatRecordService,
    private readonly aiModelService: AiModelService,
    private readonly aiMcpServerService: AiMcpServerService
  ) {
    super();
  }

  /**
   * 发起聊天对话
   * 支持对话记录保存（通过saveConversation参数控制）
   */
  @Post()
  async chat(
    @Body() dto: ChatRequestDto,
    @Playground() playground: UserPlayground
  ) {
    try {
      let conversationId = dto.conversationId;

      // 如果需要保存对话记录（默认保存，除非明确设置为false）
      if (dto.saveConversation !== false) {
        // 如果没有提供对话ID，创建新对话
        if (!conversationId) {
          const conversation =
            await this.AiChatRecordService.createConversation(playground.id, {
              title: dto.title || null,
            });
          conversationId = conversation.id;
        }

        // 保存用户消息
        const userMessage = dto.messages[dto.messages.length - 1];
        if (userMessage) {
          await this.AiChatRecordService.createMessage({
            conversationId,
            modelId: dto.modelId,
            role: this.mapChatRoleToMessageRole(userMessage.role),
            content: userMessage.content,
            messageType: MessageType.TEXT,
          });
        }
      }

      const model = await this.aiModelService.findOne({
        where: { id: dto.modelId },
        relations: ["provider"],
      });

      const provider = getProvider(model.provider.provider, {
        apiKey: model.provider.apiKey,
        baseURL: model.provider.baseUrl,
      });

      // 初始化MCP服务器和工具（静默处理）
      const mcpServers: McpServer[] = [];
      const tools: ChatCompletionFunctionTool[] = [];
      const toolToServerMap = new Map<
        string,
        { server: AiMcpServer; tool: MCPTool; mcpServer: McpServer }
      >();
      const usedTools = new Set<string>(); // 跟踪实际使用的工具
      const mcpToolCalls: McpToolCall[] = []; // 收集MCP工具调用记录

      if (dto.mcpServers && dto.mcpServers.length > 0) {
        for (const mcpServerId of dto.mcpServers) {
          try {
            const server = await this.aiMcpServerService.findOne({
              where: { id: mcpServerId },
            });

            if (server && server.url) {
              const mcpServer = new McpServer({
                url: server.url,
                name: server.name,
                description: server.description,
              });
              await mcpServer.connect();
              mcpServers.push(mcpServer);

              // 获取工具列表（仅一次）
              const mcpTools = await mcpServer.getToolsList();
              const openAITools = convertMCPToolsToOpenAI(mcpTools);
              tools.push(...openAITools);

              // 建立工具名称到服务器的映射
              for (const tool of mcpTools) {
                toolToServerMap.set(tool.name, {
                  server: server as AiMcpServer,
                  tool: tool,
                  mcpServer: mcpServer,
                });
              }

              console.log(
                `MCP服务连接成功: ${server.name || server.url}, 获取到 ${
                  mcpTools.length
                } 个工具`
              );
            }
          } catch (error) {
            // 静默处理MCP连接失败，不影响正常聊天流程
            console.warn(`MCP服务连接失败，将跳过该服务: ${error.message}`);
          }
        }
      }

      const fields = Object.keys(model.modelConfig).filter(
        (item) => model.modelConfig[item].enable
      );

      const opts = fields.map((item) => {
        return {
          [item]: model.modelConfig[item].value,
        };
      });

      const client = new TextGenerator(provider);
      // 在 chat() 和 chatStream() 方法中，构建消息时添加用户信息
      // 构建易于解析的用户信息字典格式
      const userInfo = {
        userId: playground.id,
        userName: playground.username || "匿名用户",
      };
      // const newSystemMessageContent = `用户信息: ${JSON.stringify(userInfo)}`;

      // // 构建新的系统消息
      // const systemMessage = {
      //   role: ChatRole.SYSTEM,
      //   content: newSystemMessageContent,
      // };

      // let messagesWithSystem = [...dto.messages];

      // // 查找是否已有系统消息
      // const existingSystemIndex = messagesWithSystem.findIndex(
      //   (msg) => msg.role === "system"
      // );

      // if (existingSystemIndex !== -1) {
      //   // 如果存在系统消息，则合并内容：新内容 + 分隔符 + 原内容
      //   const originalSystemMessage = messagesWithSystem[existingSystemIndex];
      //   const separator = "\n=== 原始系统消息 ===\n";

      //   const mergedContent =
      //     newSystemMessageContent + separator + originalSystemMessage.content;

      //   messagesWithSystem[existingSystemIndex] = {
      //     ...originalSystemMessage,
      //     content: mergedContent,
      //   };
      // } else {
      //   // 如果不存在系统消息，则添加到开头
      //   messagesWithSystem.unshift(systemMessage);
      // }

      // // 根据模型的maxContext限制上下文数量
      // let limitedMessages = [
      //   ...messagesWithSystem,
      // ] as Array<ChatCompletionMessageParam>;

      let limitedMessages = [
        ...dto.messages,
      ] as Array<ChatCompletionMessageParam>;
      if (
        model.maxContext &&
        model.maxContext > 0 &&
        limitedMessages.length > model.maxContext
      ) {
        // 查找系统消息
        const systemMessageIndex = limitedMessages.findIndex(
          (msg) => msg.role === "system"
        );

        if (systemMessageIndex !== -1) {
          // 如果有系统消息，保留第一条系统消息
          const systemMessage = limitedMessages[systemMessageIndex];
          // 移除系统消息
          limitedMessages.splice(systemMessageIndex, 1);

          // 取最后的 (maxContext - 1) 条消息
          const remainingCount = model.maxContext - 1;
          if (limitedMessages.length > remainingCount) {
            limitedMessages = limitedMessages.slice(-remainingCount);
          }

          // 将系统消息放在最前面
          limitedMessages.unshift(systemMessage);
        } else {
          // 如果没有系统消息，直接取最后的 maxContext 条消息
          limitedMessages = limitedMessages.slice(-model.maxContext);
        }

        this.logger.warn(
          `🔄 上下文限制: 原始消息数 ${dto.messages.length}, 限制后消息数 ${limitedMessages.length}, 最大上下文 ${model.maxContext}`
        );
      }

      // 初始化消息列表，用于处理工具调用
      let currentMessages = limitedMessages;
      let finalResponse: any = null;
      let hasToolCalls = false;

      do {
        hasToolCalls = false;

        // 调用AI服务获取响应
        const response = await client.chat.create({
          model: model.model,
          messages: currentMessages,
          user: `${JSON.stringify(userInfo)}`, // 添加用户ID作为user参数
          tools: tools.length > 0 ? tools : [],
          tool_choice: tools.length > 0 ? "auto" : "none",
          ...opts,
        });

        finalResponse = response;

        // 检查是否有工具调用
        const assistantMessage = response.choices[0].message;
        if (
          assistantMessage.tool_calls &&
          assistantMessage.tool_calls.length > 0
        ) {
          hasToolCalls = true;

          // 将AI的回复添加到消息列表
          currentMessages.push(assistantMessage);

          // 处理每个工具调用
          for (const toolCall of assistantMessage.tool_calls) {
            try {
              // 检查工具调用类型
              if (toolCall.type !== "function") continue;

              // 使用映射表快速查找对应的MCP服务器
              const mcpServerUsed = toolToServerMap.get(toolCall.function.name);
              let toolResult = null;

              if (mcpServerUsed) {
                // 解析工具参数
                const toolArgs = JSON.parse(
                  toolCall.function.arguments || "{}"
                );
                const startTime = Date.now();

                // 调用MCP工具
                toolResult = await mcpServerUsed.mcpServer.callTool(
                  toolCall.function.name,
                  toolArgs
                );

                const endTime = Date.now();
                const duration = endTime - startTime;

                // 记录使用的工具
                usedTools.add(toolCall.function.name);

                mcpToolCalls.push({
                  mcpServer: mcpServerUsed.server,
                  tool: mcpServerUsed.tool,
                  input: toolArgs,
                  output: toolResult,
                  timestamp: startTime,
                  status: "success",
                  duration: duration,
                });

                console.log(`工具 ${toolCall.function.name} 执行完成`);
              } else {
                toolResult = { error: `未找到工具: ${toolCall.function.name}` };
                console.warn(`工具未找到: ${toolCall.function.name}`);
              }

              // 将工具结果添加到消息列表
              currentMessages.push({
                role: "tool",
                content: JSON.stringify(toolResult),
                tool_call_id: toolCall.id,
              });
            } catch (error) {
              console.error(`工具调用失败:`, error);

              // 检查工具调用类型
              if (toolCall.type !== "function") return;

              // 记录MCP工具调用错误
              const mcpServerUsed = toolToServerMap.get(toolCall.function.name);
              if (mcpServerUsed) {
                const toolArgs = JSON.parse(
                  toolCall.function.arguments || "{}"
                );

                mcpToolCalls.push({
                  mcpServer: mcpServerUsed.server,
                  tool: mcpServerUsed.tool,
                  input: toolArgs,
                  output: { error: error.message },
                  timestamp: Date.now(),
                  status: "error",
                  error: error.message,
                });
              }

              // 添加错误信息
              currentMessages.push({
                role: "tool",
                content: JSON.stringify({ error: error.message }),
                tool_call_id: toolCall.id,
              });
            }
          }
        }
      } while (hasToolCalls); // 继续循环直到没有更多工具调用

      // 如果需要保存对话记录，保存AI响应
      if (
        dto.saveConversation !== false &&
        conversationId &&
        finalResponse.choices[0].message
      ) {
        await this.AiChatRecordService.createMessage({
          conversationId,
          modelId: dto.modelId,
          role: MessageRole.ASSISTANT,
          content: finalResponse.choices[0].message.content,
          messageType: MessageType.TEXT,
          tokens: {
            prompt_tokens: finalResponse.usage?.prompt_tokens,
            completion_tokens: finalResponse.usage?.completion_tokens,
            total_tokens: finalResponse.usage?.total_tokens,
          },
          rawResponse: finalResponse,
          mcpToolCalls: mcpToolCalls.length > 0 ? mcpToolCalls : null,
        });
      }

      const exists = await this.AiChatRecordService.findOneById(conversationId);

      if (!exists.title) {
        const title = await this.aiGenerateTitle(
          client,
          model,
          dto.messages as Array<ChatCompletionMessageParam>
        );

        await this.AiChatRecordService.updateConversation(
          conversationId,
          playground.id,
          {
            title,
          }
        );
      }

      // 清理MCP连接资源
      try {
        for (const mcpServer of mcpServers) {
          await mcpServer.disconnect();
        }
      } catch (error) {
        console.warn(`MCP连接清理失败: ${error.message}`);
      }

      // 准备MCP信息返回（仅返回实际使用的工具）
      let mcpInfo = null;
      if (usedTools.size > 0) {
        // 获取实际使用的工具信息
        const usedToolsInfo = tools.filter((tool) =>
          usedTools.has(tool.function.name)
        );

        // 获取使用的服务器信息
        const usedServers = new Set<McpServer>();
        usedTools.forEach((toolName) => {
          const server = toolToServerMap.get(toolName);
          if (server) {
            usedServers.add(server.mcpServer);
          }
        });

        mcpInfo = {
          servers: Array.from(usedServers).map((server) => ({
            url: server.options.url,
            connected: true,
          })),
          tools: usedToolsInfo.map((tool) => ({
            name: tool.function.name,
            description: tool.function.description,
            parameters: tool.function.parameters,
          })),
          totalTools: usedToolsInfo.length,
        };
      }

      return {
        ...finalResponse,
        conversationId, // 返回对话 ID给前端
        mcpInfo, // 返回MCP信息
      };
    } catch (error) {
      this.logger.error(`聊天对话失败: ${error.message}`, error.stack);
      throw HttpExceptionFactory.badRequest("Chat request failed.");
    }
  }

  /**
   * 流式聊天对话
   * 支持对话记录保存（通过saveConversation参数控制）
   */
  @Post("stream")
  async chatStream(
    @Body() dto: ChatRequestDto,
    @Playground() playground: UserPlayground,
    @Res() res: Response
  ) {
    // 设置SSE响应头
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "Cache-Control");

    let conversationId = dto.conversationId;
    let fullResponse = "";
    const tools: ChatCompletionFunctionTool[] = [];
    const mcpServers: McpServer[] = [];
    const toolToServerMap = new Map<
      string,
      { server: AiMcpServer; tool: MCPTool; mcpServer: McpServer }
    >();
    const usedTools = new Set<string>(); // 跟踪实际使用的工具
    const mcpToolCalls: McpToolCall[] = []; // 收集MCP工具调用记录

    try {
      // 如果需要保存对话记录（默认保存，除非明确设置为false）
      if (dto.saveConversation !== false) {
        // 如果没有提供对话ID，创建新对话
        if (!conversationId) {
          const conversation =
            await this.AiChatRecordService.createConversation(playground.id, {
              title: dto.title || null,
            });
          conversationId = conversation.id;

          // 发送对话ID给前端
          res.write(
            `data: ${JSON.stringify({
              type: "conversation_id",
              data: conversationId,
            })}\n\n`
          );
        }

        // 保存用户消息
        const userMessage = dto.messages[dto.messages.length - 1];
        if (userMessage) {
          // 打印用户问题
          this.logger.debug(`🙋 用户问题: ${userMessage.content}`);

          await this.AiChatRecordService.createMessage({
            conversationId,
            modelId: dto.modelId,
            role: this.mapChatRoleToMessageRole(userMessage.role),
            content: userMessage.content,
            messageType: MessageType.TEXT,
          });
        }
      } else if (conversationId) {
        // 如果不保存对话记录但有对话ID，发送给前端
        res.write(
          `data: ${JSON.stringify({
            type: "conversation_id",
            data: conversationId,
          })}\n\n`
        );
      }

      // 如果不保存对话记录，仍然打印用户问题
      if (dto.saveConversation === false) {
        const userMessage = dto.messages[dto.messages.length - 1];
        if (userMessage) {
          this.logger.debug(`🙋 用户问题 (不保存): ${userMessage.content}`);
        }
      }

      const model = await this.aiModelService.findOne({
        where: { id: dto.modelId },
        relations: ["provider"],
      });

      if (!model) {
        throw HttpExceptionFactory.notFound("Model not found.");
      }

      const provider = getProvider(model.provider.provider, {
        apiKey: model.provider.apiKey,
        baseURL: model.provider.baseUrl,
      });

      // 初始化MCP服务器和工具（静默处理）
      if (
        dto.mcpServers &&
        dto.mcpServers.length > 0 &&
        validateArrayItems<string>(
          dto.mcpServers,
          (item) => typeof item === "string"
        )
      ) {
        for (const mcpServerId of dto.mcpServers) {
          try {
            const server = await this.aiMcpServerService.findOne({
              where: { id: mcpServerId },
            });

            if (server && server.url) {
              const mcpServer = new McpServer({
                url: server.url,
                name: server.name,
                description: server.description,
              });

              await mcpServer.connect();

              // 获取工具列表（仅一次）
              const mcpTools = await mcpServer.getToolsList();

              mcpServers.push(mcpServer);

              const openAITools = convertMCPToolsToOpenAI(mcpTools);

              tools.push(...openAITools);

              // 建立工具名称到服务器的映射
              for (const tool of mcpTools) {
                toolToServerMap.set(tool.name, {
                  server: server as AiMcpServer,
                  tool: tool,
                  mcpServer,
                });
              }

              console.log(
                `MCP服务连接成功: ${server.name || server.url}, 获取到 ${
                  mcpTools.length
                } 个工具`
              );
            }
          } catch (error) {
            // 静默处理MCP连接失败，不影响正常聊天流程
            console.warn(`MCP服务连接失败，将跳过该服务: ${error.message}`);
          }
        }
      }

      const client = new TextGenerator(provider);

      const fields = Object.keys(model.modelConfig).filter(
        (item) => model.modelConfig[item].enable
      );

      const opts = fields.map((item) => {
        return {
          [item]: model.modelConfig[item].value,
        };
      });
      const userInfo = {
        userId: playground.id,
        userName: playground.username,
      };
      // const newSystemMessageContent = `用户信息: ${JSON.stringify(userInfo)}`;

      // // 构建新的系统消息
      // const systemMessage = {
      //   role: ChatRole.SYSTEM,
      //   content: newSystemMessageContent,
      // };

      // let messagesWithSystem = [...dto.messages];

      // // 查找是否已有系统消息
      // const existingSystemIndex = messagesWithSystem.findIndex(
      //   (msg) => msg.role === "system"
      // );

      // if (existingSystemIndex !== -1) {
      //   // 如果存在系统消息，则合并内容：新内容 + 分隔符 + 原内容
      //   const originalSystemMessage = messagesWithSystem[existingSystemIndex];
      //   const separator = "\n=== 原始系统消息 ===\n";

      //   const mergedContent =
      //     newSystemMessageContent + separator + originalSystemMessage.content;

      //   messagesWithSystem[existingSystemIndex] = {
      //     ...originalSystemMessage,
      //     content: mergedContent,
      //   };
      // } else {
      //   // 如果不存在系统消息，则添加到开头
      //   messagesWithSystem.unshift(systemMessage);
      // }

      // // 根据模型的maxContext限制上下文数量
      // let limitedMessages = [
      //   ...messagesWithSystem,
      // ] as Array<ChatCompletionMessageParam>;

      let limitedMessages = [
        ...dto.messages,
      ] as Array<ChatCompletionMessageParam>;
      if (
        model.maxContext &&
        model.maxContext > 0 &&
        limitedMessages.length > model.maxContext
      ) {
        // 查找系统消息
        const systemMessageIndex = limitedMessages.findIndex(
          (msg) => msg.role === "system"
        );

        if (systemMessageIndex !== -1) {
          // 如果有系统消息，保留第一条系统消息
          const systemMessage = limitedMessages[systemMessageIndex];
          // 移除系统消息
          limitedMessages.splice(systemMessageIndex, 1);

          // 取最后的 (maxContext - 1) 条消息
          const remainingCount = model.maxContext - 1;
          if (limitedMessages.length > remainingCount) {
            limitedMessages = limitedMessages.slice(-remainingCount);
          }

          // 将系统消息放在最前面
          limitedMessages.unshift(systemMessage);
        } else {
          // 如果没有系统消息，直接取最后的 maxContext 条消息
          limitedMessages = limitedMessages.slice(-model.maxContext);
        }

        this.logger.debug(
          `🔄 上下文限制: 原始消息数 ${dto.messages.length}, 限制后消息数 ${limitedMessages.length}, 最大上下文 ${model.maxContext}`
        );
      }

      // 初始化消息列表，用于处理工具调用
      let currentMessages = limitedMessages;
      let finalChatCompletion: any = null;
      let hasToolCalls = false;

      do {
        hasToolCalls = false;
        const stream = await client.chat.stream({
          model: model.model,
          messages: currentMessages,
          user: `${JSON.stringify(userInfo)}`, // 添加用户ID作为user参数
          tools: tools.length > 0 ? tools : [],
          tool_choice: tools.length > 0 ? "auto" : "none",
          ...opts,
        });

        // 收集流式响应
        for await (const chunk of stream) {
          // 发送SSE格式的数据
          if (chunk.choices[0].delta.content) {
            res.write(
              `data: ${JSON.stringify({
                type: "chunk",
                data: chunk.choices[0].delta.content,
              })}\n\n`
            );
            fullResponse += chunk.choices[0].delta.content;
          }

          // 处理工具调用（流式提示）
          if (chunk.choices[0].delta.tool_calls) {
            // 获取工具调用信息
            const toolCalls = chunk.choices[0].delta.tool_calls;
            for (const toolCall of toolCalls) {
              // 检查工具调用类型
              if (toolCall.type !== "function") continue;

              if (toolCall.function?.name) {
                const mcpServerUsed = toolToServerMap.get(
                  toolCall.function.name
                );

                res.write(
                  `data: ${JSON.stringify({
                    type: "mcp_tool_detected",
                    data: {
                      id: toolCall.id,
                      mcpServer: mcpServerUsed.server,
                      tool: mcpServerUsed.tool,
                      error: null,
                      input: null,
                      output: null,
                      timestamp: null,
                      status: "success",
                      duration: null,
                    },
                  })}\n\n`
                );
              }
            }
          }
        }

        finalChatCompletion = await stream.finalChatCompletion();

        // 检查是否有工具调用
        const assistantMessage = finalChatCompletion.choices[0].message;
        if (
          assistantMessage.tool_calls &&
          assistantMessage.tool_calls.length > 0
        ) {
          hasToolCalls = true;

          // 将AI的回复添加到消息列表
          currentMessages.push(assistantMessage);

          // 处理每个工具调用
          for (const toolCall of assistantMessage.tool_calls) {
            try {
              // 检查工具调用类型
              if (toolCall.type !== "function") continue;

              const mcpServerUsed = toolToServerMap.get(toolCall.function.name);
              const toolArgs = JSON.parse(toolCall.function.arguments || "{}");

              // 发送工具调用开始状态
              res.write(
                `data: ${JSON.stringify({
                  type: "mcp_tool_start",
                  data: {
                    id: toolCall.id,
                    mcpServer: mcpServerUsed.server,
                    tool: mcpServerUsed.tool,
                    error: null,
                    input: toolArgs,
                    output: null,
                    timestamp: null,
                    status: "success",
                    duration: null,
                  },
                })}\n\n`
              );

              // 使用映射表快速查找对应的MCP服务器
              let toolResult = null;

              if (mcpServerUsed) {
                // 解析工具参数
                const startTime = Date.now();

                // 调用MCP工具
                toolResult = await mcpServerUsed.mcpServer.callTool(
                  toolCall.function.name,
                  toolArgs
                );

                const endTime = Date.now();
                const duration = endTime - startTime;

                // 记录使用的工具
                usedTools.add(toolCall.function.name);

                // 记录MCP工具调用
                mcpToolCalls.push({
                  mcpServer: mcpServerUsed.server,
                  tool: mcpServerUsed.tool,
                  error: null,
                  input: toolArgs,
                  output: toolResult,
                  timestamp: startTime,
                  status: "success",
                  duration: duration,
                });

                // 返回工具执行结果
                res.write(
                  `data: ${JSON.stringify({
                    type: "mcp_tool_result",
                    data: {
                      id: toolCall.id,
                      mcpServer: mcpServerUsed.server,
                      tool: mcpServerUsed.tool,
                      error: null,
                      input: toolArgs,
                      output: toolResult,
                      timestamp: startTime,
                      status: "success",
                      duration: duration,
                    },
                  })}\n\n`
                );
              } else {
                toolResult = { error: `未找到工具: ${toolCall.function.name}` };
                res.write(
                  `data: ${JSON.stringify({
                    type: "mcp_tool_error",
                    data: {
                      id: toolCall.id,
                      mcpServer: mcpServerUsed.server,
                      tool: mcpServerUsed.tool,
                      error: `工具未找到: ${toolCall.function.name}`,
                      input: null,
                      output: null,
                      timestamp: null,
                      status: "error",
                      duration: null,
                    },
                  })}\n\n`
                );
              }

              // 将工具结果添加到消息列表
              currentMessages.push({
                role: "tool",
                content: JSON.stringify(toolResult),
                tool_call_id: toolCall.id,
              });
            } catch (error) {
              console.error(`工具调用失败:`, error);

              // 记录MCP工具调用错误
              const mcpServerUsed = toolToServerMap.get(toolCall.function.name);
              const toolArgs = JSON.parse(toolCall.function.arguments || "{}");
              if (mcpServerUsed) {
                mcpToolCalls.push({
                  id: toolCall.id,
                  mcpServer: mcpServerUsed.server,
                  tool: mcpServerUsed.tool,
                  input: toolArgs,
                  output: { error: error.message },
                  timestamp: Date.now(),
                  status: "error",
                  error: error.message,
                });
              }

              // 发送工具错误状态
              res.write(
                `data: ${JSON.stringify({
                  type: "mcp_tool_error",
                  data: {
                    id: toolCall.id,
                    name: toolCall.function.name,
                    mcpServer: mcpServerUsed.server,
                    tool: mcpServerUsed.tool,
                    error: error.message,
                    input: toolArgs,
                    output: null,
                    timestamp: Date.now(),
                    status: "error",
                    duration: null,
                  },
                })}\n\n`
              );

              // 添加错误信息
              currentMessages.push({
                role: "tool",
                content: JSON.stringify({ error: error.message }),
                tool_call_id: toolCall.id,
              });
            }
          }
        }
      } while (hasToolCalls); // 继续循环直到没有更多工具调用

      // 如果需要保存对话记录，保存AI完整响应
      if (dto.saveConversation !== false && conversationId && fullResponse) {
        // 打印AI完整回复
        this.logger.debug(`🤖 AI回复: ${fullResponse}`);

        await this.AiChatRecordService.createMessage({
          conversationId,
          modelId: dto.modelId,
          role: MessageRole.ASSISTANT,
          content: fullResponse,
          messageType: MessageType.TEXT,
          tokens: {
            prompt_tokens: finalChatCompletion.usage?.prompt_tokens,
            completion_tokens: finalChatCompletion.usage?.completion_tokens,
            total_tokens: finalChatCompletion.usage?.total_tokens,
          },
          rawResponse: finalChatCompletion,
          mcpToolCalls: mcpToolCalls.length > 0 ? mcpToolCalls : null,
        });
      }

      // 如果不保存对话记录但有完整回复，也打印出来
      if (dto.saveConversation === false && fullResponse) {
        this.logger.debug(`🤖 AI回复 (不保存): ${fullResponse}`);
      }

      const exists = await this.AiChatRecordService.findOneById(conversationId);

      if (!exists.title) {
        const title = await this.aiGenerateTitle(
          client,
          model,
          dto.messages as Array<ChatCompletionMessageParam>
        );

        await this.AiChatRecordService.updateConversation(
          conversationId,
          playground.id,
          {
            title,
          }
        );
      }

      // 清理MCP连接
      for (const mcpServer of mcpServers) {
        try {
          await mcpServer.disconnect();
        } catch (error) {
          console.error("断开MCP连接失败:", error);
        }
      }

      // 发送结束标记
      res.write("data: [DONE]\n\n");
      res.end();
    } catch (error) {
      this.logger.error(`流式聊天对话失败: ${error.message}`, error.stack);

      // 清理MCP连接
      for (const mcpServer of mcpServers) {
        try {
          await mcpServer.disconnect();
        } catch (disconnectError) {
          console.error("断开MCP连接失败:", disconnectError);
        }
      }

      await this.AiChatRecordService.createMessage({
        conversationId,
        modelId: dto.modelId,
        role: MessageRole.ASSISTANT,
        content: error.message,
        messageType: MessageType.TEXT,
        errorMessage: error?.message,
        tokens: {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        },
        rawResponse: error,
        mcpToolCalls: mcpToolCalls.length > 0 ? mcpToolCalls : null,
      });

      // 通过SSE流发送错误信息，而不是抛出异常
      try {
        res.write(
          `data: ${JSON.stringify({
            type: "error",
            data: {
              message: error.message,
              code: error.code || "INTERNAL_ERROR",
            },
          })}\n\n`
        );
        res.write("data: [DONE]\n\n");
        res.end();
      } catch (writeError) {
        this.logger.error("发送错误信息失败:", writeError);
        // 如果无法发送SSE错误，再抛出异常
        throw HttpExceptionFactory.badRequest(error.message);
      }
    }
  }

  private async aiGenerateTitle(
    client: TextGenerator,
    model,
    messages: ChatCompletionMessageParam[]
  ): Promise<string> {
    return "晶灵智能体对话";
    // const content = messages.find((item) => item.role === "user")?.content as string;
    // try {
    //     if (!content) {
    //         return "new Chat";
    //     }

    //     const response = await client.chat.create({
    //         model: model.model,
    //         messages: [
    //             {
    //                 role: "system",
    //                 content:
    //                     "你是一个专门生成标题的AI助手。请根据用户提供的内容，先判断用户的问题主要使用的语言（中文或英文），然后用该语言生成标题。请提炼出一个<chat-title></chat-title>除外的**20个字以内**（若为英文，控制在5个单词以内）的简洁标题，准确概括用户的问题。只输出标题，不要回答任何无关内容，并用<chat-title></chat-title>标签包裹，格式严格如下：<chat-title>生成的标题</chat-title>",
    //             },
    //             {
    //                 role: "user",
    //                 content: content.slice(0, 1000),
    //             },
    //         ],
    //     });

    //     const result = response.choices[0].message.content;

    //     if (!result) return "";

    //     const match = result.match(/<chat-title>([\s\S]*?)<\/chat-title>/);

    //     if (match && match[1]) {
    //         return match[1].trim();
    //     }

    //     return "";
    // } catch (error) {
    //     this.logger.error(`生成对话标题失败: ${error.message}`, error.stack);
    //     return content ? content.slice(0, 20) : "new Chat";
    // }
  }

  /**
   * 映射ChatRole到MessageRole
   */
  private mapChatRoleToMessageRole(chatRole: string): MessageRole {
    switch (chatRole) {
      case "user":
        return MessageRole.USER;
      case "assistant":
        return MessageRole.ASSISTANT;
      case "system":
        return MessageRole.SYSTEM;
      default:
        return MessageRole.USER;
    }
  }
}
