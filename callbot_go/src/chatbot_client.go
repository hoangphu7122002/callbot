package src

import (
	"bytes"
	// "context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"
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

// OpenAI API request structure
type OpenAIRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
}

// OpenAI API response structure
type OpenAIResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

type ChatbotClient struct {
	config              Config
	bot                interface{} // Có thể là LocalBotClient hoặc DifyBotClient
	conversationHistory []Message
	conversationStarted bool
	endKeywords        []string
	httpClient         *http.Client
	userID             string // User ID for Dify
}

func NewChatbotClient(config Config) *ChatbotClient {
	client := &ChatbotClient{
		config:              config,
		conversationHistory: make([]Message, 0),
		endKeywords:        config.EndConversationKeywords,
		httpClient:         &http.Client{},
		userID:             "default-user",
	}

	switch config.BotType {
	case "local":
		client.bot = NewLocalBotClient(config.LocalLLMURL)
	case "dify":
		// Initialize Dify client
		client.bot = NewDifyBotClient(config.DifyAPIURL, config.DifyAPIKey)
	default:
		// OpenAI case - sẽ được xử lý trong GetResponse
	}

	return client
}

// NewDifyBotClient creates a new Dify bot client
// func NewDifyBotClient(apiURL, apiKey string) *DifyBotClient {
// 	return &DifyBotClient{
// 		apiURL: apiURL,
// 		apiKey: apiKey,
// 		headers: map[string]string{
// 			"Authorization": fmt.Sprintf("Bearer %s", apiKey),
// 			"Content-Type":  "application/json",
// 		},
// 	}
// }

// ResponseResult represents the result of an operation
type ResponseResult struct {
	Response string
	Error    error
}

// GetResponse gets a response from the chatbot based on the bot type
func (c *ChatbotClient) GetResponse(message string) (string, error) {
	switch c.config.BotType {
	case "local":
		if localBot, ok := c.bot.(*LocalBotClient); ok {
			return localBot.GetResponse(message)
		}
		return "", fmt.Errorf("invalid local bot client")

	case "dify":
		if !c.conversationStarted {
			// Reset conversation when starting a new conversation
			if difyBot, ok := c.bot.(*DifyBotClient); ok {
				difyBot.ResetConversation()
				c.conversationStarted = true
			}
		}
		fmt.Println("================debug==============")
		
		// Call Dify bot client to get response
		if difyBot, ok := c.bot.(*DifyBotClient); ok {
			return difyBot.GetResponse(message, c.userID)
		}
		return "", fmt.Errorf("invalid dify bot client")

	default:
		// OpenAI case
		c.conversationHistory = append(c.conversationHistory, Message{
			Role:    "user",
			Content: message,
		})
		
		history := make([]Message, len(c.conversationHistory))
		copy(history, c.conversationHistory)

		// Implement OpenAI API call
		openaiReq := OpenAIRequest{
			Model:    c.config.GPTModel,
			Messages: history,
		}

		reqBody, err := json.Marshal(openaiReq)
		if err != nil {
			return "", fmt.Errorf("error marshaling request: %v", err)
		}

		req, err := http.NewRequest("POST", "https://api.openai.com/v1/chat/completions", bytes.NewBuffer(reqBody))
		if err != nil {
			return "", fmt.Errorf("error creating request: %v", err)
		}

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+c.config.OpenAIAPIKey)

		resp, err := c.httpClient.Do(req)
		if err != nil {
			return "", fmt.Errorf("error making request: %v", err)
		}
		defer resp.Body.Close()

		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return "", fmt.Errorf("error reading response: %v", err)
		}

		var openaiResp OpenAIResponse
		if err := json.Unmarshal(body, &openaiResp); err != nil {
			return "", fmt.Errorf("error unmarshaling response: %v", err)
		}

		if openaiResp.Error != nil {
			return "", fmt.Errorf("OpenAI API error: %s", openaiResp.Error.Message)
		}

		if len(openaiResp.Choices) == 0 {
			return "", fmt.Errorf("no response from OpenAI API")
		}

		botResponse := openaiResp.Choices[0].Message.Content

		c.conversationHistory = append(c.conversationHistory, Message{
			Role:    "assistant",
			Content: botResponse,
		})

		return botResponse, nil
	}
}

// SyncGetResponse is the synchronous version of GetResponse for backward compatibility
func (c *ChatbotClient) SyncGetResponse(message string) string {
	response, err := c.GetResponse(message)
	if err != nil {
		fmt.Printf("Error getting response: %v\n", err)
		return "Xin lỗi, tôi đang gặp sự cố kỹ thuật."
	}
	return response
}

// GetResponseAsync is an asynchronous version of GetResponse (left for future use)
// func (c *ChatbotClient) GetResponseAsync(ctx context.Context, message string) chan ResponseResult {
// 	resultChan := make(chan ResponseResult, 1)

// 	go func() {
// 		defer close(resultChan)
// 		response, err := c.GetResponse(message)
		
// 		select {
// 		case <-ctx.Done():
// 			resultChan <- ResponseResult{
// 				Response: "",
// 				Error:    ctx.Err(),
// 			}
// 		case resultChan <- ResponseResult{
// 			Response: response,
// 			Error:    err,
// 		}:
// 		}
// 	}()

// 	return resultChan
// }

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
		// End Dify conversation
		if difyBot, ok := c.bot.(*DifyBotClient); ok {
			err := difyBot.EndConversation(c.userID)
			if err != nil {
				fmt.Printf("Error ending Dify conversation: %v\n", err)
			}
		}
	default:
		fmt.Println("not implementation for openai")
	}

	// Reset conversation history
	c.conversationHistory = make([]Message, 0)
	c.conversationStarted = false
}

// AddToHistory adds a message to conversation history
func (c *ChatbotClient) AddToHistory(role, content string) {
	c.conversationHistory = append(c.conversationHistory, Message{
		Role:    role,
		Content: content,
	})
}

// GetHistory returns the conversation history
func (c *ChatbotClient) GetHistory() []Message {
	history := make([]Message, len(c.conversationHistory))
	copy(history, c.conversationHistory)
	return history
}

// GetConfig returns the client configuration
func (c *ChatbotClient) GetConfig() Config {
	return c.config
}

// SetUserID sets the user ID for Dify
func (c *ChatbotClient) SetUserID(userID string) {
	c.userID = userID
}
