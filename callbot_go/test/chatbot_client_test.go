package test

import (
	"testing"

	"github.com/stretchr/testify/assert"

	"callbot_go/src"
)

func TestNewChatbotClient(t *testing.T) {
	config := src.Config{
		BotType:                "openai",
		OpenAIAPIKey:          "test-api-key",
		GPTModel:              "gpt-3.5-turbo",
		EndConversationKeywords: []string{"bye", "goodbye"},
	}

	client := src.NewChatbotClient(config)
	assert.NotNil(t, client)
	assert.Equal(t, config, client.GetConfig())
	assert.Equal(t, 0, len(client.GetHistory()))
}

func TestNewChatbotClientWithDify(t *testing.T) {
	config := src.Config{
		BotType:                "dify",
		DifyAPIURL:            "https://api.dify.ai/v1/chat-messages",
		DifyAPIKey:            "test-dify-api-key",
		EndConversationKeywords: []string{"bye", "goodbye"},
	}

	client := src.NewChatbotClient(config)
	assert.NotNil(t, client)
	assert.Equal(t, config, client.GetConfig())
	assert.Equal(t, 0, len(client.GetHistory()))
}

func TestShouldEndConversation(t *testing.T) {
	config := src.Config{
		BotType:                "openai",
		OpenAIAPIKey:          "test-api-key",
		GPTModel:              "gpt-3.5-turbo",
		EndConversationKeywords: []string{"bye", "goodbye"},
	}

	client := src.NewChatbotClient(config)
	
	// Test end keywords
	assert.True(t, client.ShouldEndConversation("Bye for now"))
	assert.True(t, client.ShouldEndConversation("I want to say GOODBYE"))
	assert.True(t, client.ShouldEndConversation("##END##"))
	assert.True(t, client.ShouldEndConversation("This is the ##end## of conversation"))
	
	// Test non-end messages
	assert.False(t, client.ShouldEndConversation("Hello there"))
	assert.False(t, client.ShouldEndConversation("How are you?"))
}

func TestAddToHistory(t *testing.T) {
	config := src.Config{
		BotType:                "openai",
		OpenAIAPIKey:          "test-api-key",
		GPTModel:              "gpt-3.5-turbo",
	}

	client := src.NewChatbotClient(config)
	
	// Add messages to history
	client.AddToHistory("user", "Hello")
	client.AddToHistory("assistant", "Hi there")
	client.AddToHistory("user", "How are you?")
	
	// Get history and verify
	history := client.GetHistory()
	assert.Equal(t, 3, len(history))
	assert.Equal(t, "user", history[0].Role)
	assert.Equal(t, "Hello", history[0].Content)
	assert.Equal(t, "assistant", history[1].Role)
	assert.Equal(t, "Hi there", history[1].Content)
	assert.Equal(t, "user", history[2].Role)
	assert.Equal(t, "How are you?", history[2].Content)
}

func TestEndConversation(t *testing.T) {
	config := src.Config{
		BotType:                "openai",
		OpenAIAPIKey:          "test-api-key",
		GPTModel:              "gpt-3.5-turbo",
	}

	client := src.NewChatbotClient(config)
	
	// Add messages to history
	client.AddToHistory("user", "Hello")
	client.AddToHistory("assistant", "Hi there")
	
	// End conversation
	client.EndConversation()
	
	// Verify history is cleared
	history := client.GetHistory()
	assert.Equal(t, 0, len(history))
}

func TestSetUserID(t *testing.T) {
	config := src.Config{
		BotType:                "dify",
		DifyAPIURL:            "https://api.dify.ai/v1/chat-messages",
		DifyAPIKey:            "test-dify-api-key",
	}

	client := src.NewChatbotClient(config)
	client.SetUserID("test-user-123")
	
	// We don't have a getter for userID, but this at least tests
	// that the method exists and doesn't panic
	assert.NotNil(t, client)
}
