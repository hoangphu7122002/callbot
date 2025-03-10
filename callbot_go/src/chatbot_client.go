package src

import (
	"context"
	"fmt"
	"strings"
	"sync"
)

type Config struct {
	BotType                string
	LocalLLMURL           string
	DifyAPIURL            string
	DifyAPIKey            string
	OpenAIAPIKey          string
	GPTModel              string
	EndConversationKeywords []string
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatbotClient struct {
	config              Config
	bot                interface{} // Có thể là LocalBotClient hoặc DifyBotClient
	conversationHistory []Message
	conversationStarted bool
	endKeywords        []string
	mu                 sync.Mutex // Mutex để bảo vệ conversationHistory
}

func NewChatbotClient(config Config) *ChatbotClient {
	client := &ChatbotClient{
		config:              config,
		conversationHistory: make([]Message, 0),
		endKeywords:        config.EndConversationKeywords,
	}

	switch config.BotType {
	case "local":
		client.bot = NewLocalBotClient(config.LocalLLMURL)
	case "dify":
		// TODO: Implement DifyBotClient
		// client.bot = NewDifyBotClient(config.DifyAPIURL, config.DifyAPIKey)
	default:
		// OpenAI case - sẽ được xử lý trong GetResponse
	}

	return client
}

// GetResponseAsync là phiên bản không đồng bộ của GetResponse
func (c *ChatbotClient) GetResponseAsync(ctx context.Context, message string) chan ResponseResult {
	resultChan := make(chan ResponseResult, 1)

	go func() {
		defer close(resultChan)

		var response string
		var err error

		switch c.config.BotType {
		case "local":
			if localBot, ok := c.bot.(*LocalBotClient); ok {
				response, err = localBot.GetResponse(message)
			}

		case "dify":
			if !c.conversationStarted {
				// TODO: Implement Dify reset conversation
				c.conversationStarted = true
			}
			fmt.Println("================debug==============")
			// TODO: Implement Dify response

		default:
			// OpenAI case
			c.mu.Lock()
			c.conversationHistory = append(c.conversationHistory, Message{
				Role:    "user",
				Content: message,
			})
			c.mu.Unlock()

			// TODO: Implement OpenAI API call
			response = "OpenAI implementation needed"
		}

		select {
		case <-ctx.Done():
			resultChan <- ResponseResult{
				Response: "",
				Error:    ctx.Err(),
			}
		case resultChan <- ResponseResult{
			Response: response,
			Error:    err,
		}:
		}
	}()

	return resultChan
}

// ResponseResult represents the result of an async operation
type ResponseResult struct {
	Response string
	Error    error
}

// GetResponse is a synchronous wrapper around GetResponseAsync
func (c *ChatbotClient) GetResponse(message string) (string, error) {
	ctx := context.Background()
	resultChan := c.GetResponseAsync(ctx, message)
	result := <-resultChan
	return result.Response, result.Error
}

// SyncGetResponse là phiên bản đồng bộ của GetResponse (giữ lại để tương thích ngược)
func (c *ChatbotClient) SyncGetResponse(message string) string {
	response, err := c.GetResponse(message)
	if err != nil {
		return "Xin lỗi, tôi đang gặp sự cố kỹ thuật."
	}
	return response
}

func (c *ChatbotClient) ShouldEndConversation(text string) bool {
	// Kiểm tra từ khóa kết thúc
	textLower := strings.ToLower(text)
	for _, keyword := range c.endKeywords {
		if strings.Contains(textLower, strings.ToLower(keyword)) {
			return true
		}
	}

	// Kiểm tra marker kết thúc
	if strings.Contains(text, "##END##") || strings.Contains(text, "##end##") {
		return true
	}

	return false
}

func (c *ChatbotClient) EndConversation() {
	switch c.config.BotType {
	case "local":
		if localBot, ok := c.bot.(*LocalBotClient); ok {
			localBot.EndConversation()
		}
	case "dify":
		// TODO: Implement Dify end conversation
	default:
		fmt.Println("not implementation for openai")
	}

	// Reset conversation history
	c.mu.Lock()
	c.conversationHistory = make([]Message, 0)
	c.mu.Unlock()
}

// AddToHistory adds a message to conversation history thread-safely
func (c *ChatbotClient) AddToHistory(role, content string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.conversationHistory = append(c.conversationHistory, Message{
		Role:    role,
		Content: content,
	})
}

// GetHistory returns the conversation history thread-safely
func (c *ChatbotClient) GetHistory() []Message {
	c.mu.Lock()
	defer c.mu.Unlock()
	history := make([]Message, len(c.conversationHistory))
	copy(history, c.conversationHistory)
	return history
}
