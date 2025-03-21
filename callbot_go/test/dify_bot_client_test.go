package test

import (
	"testing"
	"callbot_go/src"
	"fmt"
	"callbot_go/config"
)

func TestDifyBotClient(t *testing.T) {
	config := config.GetConfig()
	client := src.NewDifyBotClient(config.DifyAPIURL, config.DifyAPIKey)

	// Test GetResponse
	t.Run("Test GetResponse", func(t *testing.T) {
		response, err := client.GetResponse("bạn có thể giúp gì được cho tôi", "test-user")
		if err != nil {
			t.Errorf("GetResponse failed: %v", err)
		}
		if response == "" {
			t.Error("Expected non-empty response")
		}
		fmt.Println(response)
	})

	// Test conversation flow
	t.Run("Test Conversation Flow", func(t *testing.T) {
		// First message
		response1, err := client.GetResponse("Tôi muốn hỏi về dịch vụ chuyển khoản tại quầy", "test-user")
		if err != nil {
			t.Errorf("First message failed: %v", err)
		}
		if response1 == "" {
			t.Error("Expected non-empty response for first message")
		}

		// Second message in same conversation
		response2, err := client.GetResponse("vậy trực tiếp thì sao", "test-user")
		if err != nil {
			t.Errorf("Second message failed: %v", err)
		}
		if response2 == "" {
			t.Error("Expected non-empty response for second message")
		}

		// End conversation
		err = client.EndConversation("test-user")
		if err != nil {
			t.Errorf("EndConversation failed: %v", err)
		}

		fmt.Println(response1)
		fmt.Println(response2)
	})

	// Test ResetConversation
	t.Run("Test ResetConversation", func(t *testing.T) {
		client.ResetConversation()
		response, err := client.GetResponse("New conversation", "test-user")
		if err != nil {
			t.Errorf("GetResponse after reset failed: %v", err)
		}
		if response == "" {
			t.Error("Expected non-empty response after reset")
		}
		fmt.Println(response)
	})
}
